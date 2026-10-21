#!/usr/bin/env python3
"""Stop hook: run targeted tests when a turn ends with changed code.

Fails open: any internal error or timeout warns on stderr and never blocks.
"""
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

BUDGET_SECONDS = 180
TAIL_LINES = 40
# Decision of the sondage (section testmon): testmon_retenu: oui.
TESTMON_RETENU = True
FRONTEND_EXT = (".ts", ".tsx", ".js", ".jsx")
TESTMON_CMD = ["uv", "run", "pytest", "--testmon", "--testmon-forceselect",
               "-m", "not integration", "-n", "0", "-q"]
BACKEND_CONFIG = ("backend/pyproject.toml", "backend/uv.lock")
_child = None


def _git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)
    return result.stdout


def changed_files(repo):
    tracked = _git(repo, "diff", "--name-only", "HEAD").splitlines()
    untracked = _git(repo, "ls-files", "--others", "--exclude-standard").splitlines()
    return sorted(set(tracked + untracked))


def fingerprint(repo, files):
    digest = hashlib.sha256()
    for name in sorted(files):
        digest.update(name.encode() + b"\0")
        path = Path(repo) / name
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def frontend_targets(files):
    return [f[len("frontend/"):] for f in files if f.startswith("frontend/") and f.endswith(FRONTEND_EXT)]


def backend_inputs(files):
    """Changed files that feed the backend command (fingerprint scope)."""
    return [f for f in files if f.startswith(("backend/app/", "backend/tests/")) or f in BACKEND_CONFIG
            or (f.startswith("backend/") and f.endswith(".py"))]


def backend_targets(files, tests_root):
    """Direct tests and tests importing a changed module (direct imports only)."""
    backend = Path(tests_root).parent
    targets = set()
    for name in files:
        if not (name.startswith("backend/") and name.endswith(".py")):
            continue
        rel = name[len("backend/"):]
        if rel.startswith("tests/"):
            if Path(rel).name.startswith("test_"):
                targets.add(rel)
            continue
        module = rel[:-3].replace("/", ".")
        pattern = re.compile(rf"^\s*(?:from|import)\s+{re.escape(module)}\b", re.MULTILINE)
        for test in Path(tests_root).rglob("test_*.py"):
            if pattern.search(test.read_text(errors="ignore")):
                targets.add(str(test.relative_to(backend)))
    return sorted(targets)


def default_runner(argv, cwd, timeout):
    global _child
    # Own session so a timeout can kill the whole tree (npx, uv spawn workers).
    proc = _child = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, start_new_session=True)
    try:
        output, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise
    finally:
        _child = None
    return proc.returncode, output


def _on_signal(signum, _frame):
    if _child is not None:
        try:
            os.killpg(_child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    os._exit(128 + signum)


def install_signal_handlers():
    """A killed hook takes its test process group down with it."""
    for signum in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, _on_signal)


def _backend_argv(repo, files, err):
    if TESTMON_RETENU and (repo / "backend" / ".testmondata").is_file():
        return TESTMON_CMD
    if TESTMON_RETENU:
        err.write("targeted_tests: backend/.testmondata missing, running the tests that import "
                  "the changed modules (one `uv run pytest --testmon --testmon-forceselect "
                  "-m \"not integration\"` builds it)\n")
    backend = [f for f in files if f.startswith("backend/") and f.endswith(".py")]
    targets = backend_targets(backend, repo / "backend" / "tests")
    return ["uv", "run", "pytest", *targets, "-n", "0", "-q"] if targets else None


def _sides(repo, files, err):
    """(name, argv, fingerprint inputs) for each side with changed sources."""
    sides = []
    if any(f.startswith("backend/") and f.endswith(".py") for f in files):
        argv = _backend_argv(repo, files, err)
        if argv:
            sides.append(("backend", argv, backend_inputs(files)))
    front = frontend_targets(files)
    if front:
        sides.append(("frontend", ["npx", "vitest", "related", "--run", *front],
                      [f"frontend/{f}" for f in front]))
    return sides


def _missing_tool(repo, side):
    if side == "backend":
        return None if shutil.which("uv") else "uv not on PATH"
    if not shutil.which("npx"):
        return "npx not on PATH"
    if not (repo / "frontend" / "node_modules" / ".bin" / "vitest").exists():
        return "frontend/node_modules/.bin/vitest missing, run npm ci"
    return None


def main(stdin_text, repo, runner, out, err):
    try:
        if json.loads(stdin_text or "{}").get("stop_hook_active"):
            return 0
        repo = Path(repo)
        sides = _sides(repo, changed_files(repo), err)
        if not sides:
            return 0
        git_dir = Path(_git(repo, "rev-parse", "--absolute-git-dir").strip())
        pending = []
        for side, argv, inputs in sides:
            cache = git_dir / f"claude-targeted-tests-{side}.sha"
            current = fingerprint(repo, inputs)
            if cache.is_file() and cache.read_text().strip() == current:
                continue
            missing = _missing_tool(repo, side)
            if missing:
                err.write(f"targeted_tests: {side} skipped ({missing})\n")
                continue
            pending.append((side, argv, cache, current))
        deadline = time.monotonic() + BUDGET_SECONDS
        for index, (side, argv, cache, current) in enumerate(pending):
            remaining = deadline - time.monotonic()
            try:
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(argv, BUDGET_SECONDS)
                code, output = runner(argv, repo / side, remaining)
            except subprocess.TimeoutExpired:
                skipped = ", ".join(s for s, *_ in pending[index + 1:]) or "none"
                err.write(f"targeted_tests: timeout after {BUDGET_SECONDS}s in {side}, "
                          f"tests not verified (skipped: {skipped})\n")
                cache.write_text(current)  # no retry until the content changes
                return 0
            # Red included: a red state blocks once, not on every later turn.
            cache.write_text(current)
            if code != 0:
                tail = "\n".join(output.splitlines()[-TAIL_LINES:])
                reason = f"Targeted tests failed ({' '.join(argv)}):\n{tail}"
                out.write(json.dumps({"decision": "block", "reason": reason}))
                return 0
    except Exception as exc:  # fail open
        err.write(f"targeted_tests: skipped ({exc})\n")
    return 0


if __name__ == "__main__":
    try:
        repo_root = _git(Path.cwd(), "rev-parse", "--show-toplevel").strip()
    except Exception:
        sys.exit(0)
    install_signal_handlers()
    sys.exit(main(sys.stdin.read(), repo_root, default_runner, sys.stdout, sys.stderr))
