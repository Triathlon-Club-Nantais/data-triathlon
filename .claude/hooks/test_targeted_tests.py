import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))
import targeted_tests as tt  # noqa: E402


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


class Runner:
    def __init__(self, code=0, output="", exc=None):
        self.calls, self.code, self.output, self.exc = [], code, output, exc

    def __call__(self, argv, cwd, timeout):
        self.calls.append((argv, cwd))
        if self.exc:
            raise self.exc
        return self.code, self.output


class TargetedTestsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "t@t")
        git(self.repo, "config", "user.name", "t")
        self.write("backend/app/services/foo.py", "x = 1\n")
        self.write("docs/a.md", "a\n")
        self.write(".gitignore", "node_modules/\n.testmondata\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "init")
        self.write("frontend/node_modules/.bin/vitest", "")
        self.write("backend/.testmondata", "")
        which = mock.patch.object(tt.shutil, "which", side_effect=lambda name: f"/bin/{name}")
        self.which = which.start()
        self.addCleanup(which.stop)

    def write(self, rel, text):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def run_hook(self, runner, stdin="{}"):
        out, err = io.StringIO(), io.StringIO()
        code = tt.main(stdin, self.repo, runner, out, err)
        return code, out.getvalue(), err.getvalue()

    def test_stop_hook_active_noop(self):
        self.write("backend/app/services/foo.py", "x = 2\n")
        runner = Runner()
        code, out, _ = self.run_hook(runner, json.dumps({"stop_hook_active": True}))
        self.assertEqual((code, out, runner.calls), (0, "", []))

    def test_unchanged_fingerprint_noop(self):
        self.write("backend/app/services/foo.py", "x = 2\n")
        first = Runner()
        self.run_hook(first)
        self.assertEqual(len(first.calls), 1)
        second = Runner()
        self.run_hook(second)
        self.assertEqual(second.calls, [])

    def test_no_source_change_noop(self):
        self.write("docs/a.md", "changed\n")
        runner = Runner()
        self.assertEqual(self.run_hook(runner)[0], 0)
        self.assertEqual(runner.calls, [])

    def test_frontend_targets(self):
        self.assertEqual(
            tt.frontend_targets(["frontend/components/A.tsx", "frontend/lib/b.ts", "docs/a.md"]),
            ["components/A.tsx", "lib/b.ts"],
        )

    def test_frontend_change_runs_vitest_related(self):
        self.write("frontend/lib/b.ts", "export const b = 1\n")
        runner = Runner()
        self.run_hook(runner)
        argv, cwd = runner.calls[0]
        self.assertEqual(argv, ["npx", "vitest", "related", "--run", "lib/b.ts"])
        self.assertEqual(cwd, self.repo / "frontend")

    def test_backend_targets_direct_test(self):
        self.assertEqual(
            tt.backend_targets(["backend/tests/test_x.py"], self.repo / "backend/tests"),
            ["tests/test_x.py"],
        )

    def test_backend_targets_import(self):
        self.write("backend/tests/test_a.py", "from app.services.foo import x\n")
        self.write("backend/tests/sub/test_b.py", "import app.services.foo\n")
        self.write("backend/tests/test_c.py", "from app.services.foo_bar import y\n")
        self.assertEqual(
            sorted(tt.backend_targets(["backend/app/services/foo.py"], self.repo / "backend/tests")),
            ["tests/sub/test_b.py", "tests/test_a.py"],
        )

    def test_backend_command_uses_testmon_when_retained(self):
        self.write("backend/app/services/foo.py", "x = 2\n")
        runner = Runner()
        self.run_hook(runner)
        argv, cwd = runner.calls[0]
        self.assertEqual(argv[:3], ["uv", "run", "pytest"])
        self.assertIn("--testmon-forceselect", argv)
        self.assertEqual(cwd, self.repo / "backend")

    def test_red_blocks(self):
        self.write("backend/app/services/foo.py", "x = 2\n")
        output = "\n".join(f"line{i}" for i in range(100))
        code, out, _ = self.run_hook(Runner(code=1, output=output))
        payload = json.loads(out)
        self.assertEqual((code, payload["decision"]), (0, "block"))
        self.assertIn("line99", payload["reason"])
        self.assertIn("line60", payload["reason"])
        self.assertNotIn("line59\n", payload["reason"])
        follow_up = Runner(code=1, output=output)
        self.assertEqual(self.run_hook(follow_up)[1], "")
        self.assertEqual(follow_up.calls, [])  # blocks once per content state

    def test_red_then_new_content_reruns(self):
        self.write("backend/app/services/foo.py", "x = 2\n")
        self.run_hook(Runner(code=1))
        self.write("backend/app/services/foo.py", "x = 3\n")
        follow_up = Runner()
        self.run_hook(follow_up)
        self.assertEqual(len(follow_up.calls), 1)

    def test_docs_and_coverage_changes_do_not_rerun(self):
        self.write("backend/app/services/foo.py", "x = 2\n")
        self.run_hook(Runner())
        self.write("docs/a.md", "changed\n")
        self.write("backend/.coverage", "data")
        follow_up = Runner()
        self.run_hook(follow_up)
        self.assertEqual(follow_up.calls, [])

    def test_each_side_keeps_its_own_fingerprint(self):
        self.write("backend/app/services/foo.py", "x = 2\n")
        self.run_hook(Runner())
        self.write("frontend/lib/b.ts", "export const b = 1\n")
        follow_up = Runner()
        self.run_hook(follow_up)
        self.assertEqual([cwd for _, cwd in follow_up.calls], [self.repo / "frontend"])

    def test_missing_vitest_skips_frontend_without_blocking(self):
        (self.repo / "frontend/node_modules/.bin/vitest").unlink()
        self.write("frontend/lib/b.ts", "export const b = 1\n")
        runner = Runner(code=1)
        code, out, err = self.run_hook(runner)
        self.assertEqual((code, out, runner.calls), (0, "", []))
        self.assertIn("node_modules/.bin/vitest", err)
        self.write("frontend/node_modules/.bin/vitest", "")
        follow_up = Runner()
        self.run_hook(follow_up)
        self.assertEqual(len(follow_up.calls), 1)  # no fingerprint for a side that did not run

    def test_missing_tool_on_path_skips_that_side(self):
        self.which.side_effect = lambda name: None if name == "uv" else f"/bin/{name}"
        self.write("backend/app/services/foo.py", "x = 2\n")
        self.write("frontend/lib/b.ts", "export const b = 1\n")
        runner = Runner()
        code, out, err = self.run_hook(runner)
        self.assertEqual((code, out), (0, ""))
        self.assertEqual([cwd for _, cwd in runner.calls], [self.repo / "frontend"])
        self.assertIn("uv", err)

    def test_missing_testmondata_runs_importing_tests(self):
        (self.repo / "backend/.testmondata").unlink()
        self.write("backend/tests/test_a.py", "from app.services.foo import x\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "test")
        self.write("backend/app/services/foo.py", "x = 2\n")
        runner = Runner()
        _, _, err = self.run_hook(runner)
        self.assertEqual(runner.calls, [(["uv", "run", "pytest", "tests/test_a.py", "-n", "0", "-q"],
                                         self.repo / "backend")])
        self.assertIn(".testmondata", err)

    def test_timeout_warns(self):
        self.write("backend/app/services/foo.py", "x = 2\n")
        runner = Runner(exc=subprocess.TimeoutExpired("uv", 1))
        code, out, err = self.run_hook(runner)
        self.assertEqual((code, out), (0, ""))
        self.assertIn("timeout", err.lower())

    def test_timeout_records_fingerprint(self):
        self.write("backend/app/services/foo.py", "x = 2\n")
        self.run_hook(Runner(exc=subprocess.TimeoutExpired("uv", 1)))
        follow_up = Runner()
        self.run_hook(follow_up)
        self.assertEqual(follow_up.calls, [])

    def test_timeout_warning_names_skipped_step(self):
        self.write("backend/app/services/foo.py", "x = 2\n")
        self.write("frontend/lib/b.ts", "export const b = 1\n")
        runner = Runner(exc=subprocess.TimeoutExpired("uv", 1))
        _, _, err = self.run_hook(runner)
        self.assertEqual(len(runner.calls), 1)
        self.assertIn("backend", err)
        self.assertIn("skipped: frontend", err)

    def test_default_runner_kills_grandchildren_on_timeout(self):
        pidfile = Path(self._tmp.name) / "grandchild.pid"
        script = f"sleep 30 & echo $! > {pidfile}; sleep 30"
        started = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            tt.default_runner(["sh", "-c", script], self.repo, 1)
        self.assertLess(time.monotonic() - started, 3)
        grandchild = int(pidfile.read_text())
        for _ in range(20):
            try:
                os.kill(grandchild, 0)
            except ProcessLookupError:
                return
            time.sleep(0.1)
        os.kill(grandchild, 9)
        self.fail("grandchild survived the timeout")

    def test_sigterm_kills_the_test_process_group(self):
        pidfile = Path(self._tmp.name) / "grandchild.pid"
        script = f"sleep 30 & echo $! > {pidfile}; sleep 30"
        hook = subprocess.Popen([sys.executable, "-c", (
            "import sys; sys.path.insert(0, sys.argv[1]); import targeted_tests as tt; "
            "tt.install_signal_handlers(); tt.default_runner(['sh', '-c', sys.argv[2]], '.', 60)"
        ), str(Path(__file__).parent), script])
        for _ in range(50):
            if pidfile.is_file() and pidfile.read_text().strip():
                break
            time.sleep(0.1)
        hook.terminate()
        hook.wait(timeout=5)
        grandchild = int(pidfile.read_text())
        for _ in range(20):
            try:
                os.kill(grandchild, 0)
            except ProcessLookupError:
                return
            time.sleep(0.1)
        os.kill(grandchild, 9)
        self.fail("grandchild survived SIGTERM")


if __name__ == "__main__":
    unittest.main()
