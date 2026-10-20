import json
import subprocess
import sys
import unittest
from pathlib import Path

HOOK = Path(__file__).with_name("test_gate.py")
sys.path.insert(0, str(HOOK.parent))
from test_gate import is_full_suite  # noqa: E402

FULL = [
    "uv run pytest",
    'uv run pytest -m "not integration"',
    "uv run pytest tests",
    "uv run pytest tests/ -q",
    'rtk uv run pytest -m "not integration"',
    "cd backend && uv run python -m pytest -q",
    "npm test",
    "npm test -- --reporter=dot",
    "npx vitest run",
    "rtk npx vitest run",
    "FULL_SUITE=0 npm test",
    "npm run test",
    "npm --prefix frontend test",
    "python3 -m pytest",
    "pytest",
    "vitest run",
    "uv run pytest -q 2>&1 | tail -5",
    "npm test -- --run 2>&1",
    "uv run pytest > out.txt",
    "uv run pytest 2> /dev/null",
    "time uv run pytest",
    "uv run --directory backend pytest",
    "env CI=1 npm test",
]
TARGETED = [
    "FULL_SUITE=1 uv run pytest",
    "uv run pytest tests/test_api -n 0",
    "uv run pytest tests/test_x.py::test_y",
    "uv run pytest -k raceresult",
    "uv run pytest --lf",
    "uv run pytest --sw",
    "uv run pytest -m integration -n 0",
    "npx vitest run components/AppNav.test.tsx",
    "npm test -- components/x",
    "npx vitest related --run lib/a.ts",
    "npx vitest --changed origin/main",
    "git status && ls",
    "npm run build",
    "env FULL_SUITE=1 uv run pytest",
    "uv run pytest tests/test_api 2>&1 | tail",
]


def run_hook(stdin):
    return subprocess.run([sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True)


class IsFullSuiteTest(unittest.TestCase):
    def test_full(self):
        for command in FULL:
            with self.subTest(command=command):
                self.assertTrue(is_full_suite(command))

    def test_targeted(self):
        for command in TARGETED:
            with self.subTest(command=command):
                self.assertFalse(is_full_suite(command))


class MainTest(unittest.TestCase):
    def test_main_denies_full_suite(self):
        result = run_hook(json.dumps({"tool_input": {"command": "npm test"}}))
        self.assertEqual(result.returncode, 0)
        output = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")

    def test_main_silent_otherwise(self):
        result = run_hook(json.dumps({"tool_input": {"command": "ls"}}))
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_main_fails_open_on_malformed_stdin(self):
        for stdin in ("not json", "", json.dumps({"tool_input": {"command": "echo 'x"}})):
            with self.subTest(stdin=stdin):
                result = run_hook(stdin)
                self.assertEqual((result.returncode, result.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
