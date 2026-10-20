#!/usr/bin/env python3
"""Stop hook: run targeted tests when a turn ends with changed code.

Fails open: any internal error or timeout warns on stderr and never blocks.
"""
import hashlib
import json
import re
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
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return result.returncode, result.stdout + result.stderr


def _commands(repo, files):
    backend = [f for f in files if f.startswith("backend/") and f.endswith(".py")]
    commands = []
    if backend:
        if TESTMON_RETENU:
            commands.append((TESTMON_CMD, repo / "backend"))
        else:
            targets = backend_targets(backend, repo / "backend" / "tests")
            if targets:
                commands.append((["uv", "run", "pytest", *targets, "-n", "0", "-q"], repo / "backend"))
    front = frontend_targets(files)
    if front:
        commands.append((["npx", "vitest", "related", "--run", *front], repo / "frontend"))
    return commands


def main(stdin_text, repo, runner, out, err):
    try:
        if json.loads(stdin_text or "{}").get("stop_hook_active"):
            return 0
        repo = Path(repo)
        files = changed_files(repo)
        commands = _commands(repo, files)
        if not commands:
            return 0
        cache = Path(_git(repo, "rev-parse", "--absolute-git-dir").strip()) / "claude-targeted-tests.sha"
        current = fingerprint(repo, files)
        if cache.is_file() and cache.read_text().strip() == current:
            return 0
        deadline = time.monotonic() + BUDGET_SECONDS
        for argv, cwd in commands:
            remaining = deadline - time.monotonic()
            try:
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(argv, BUDGET_SECONDS)
                code, output = runner(argv, cwd, remaining)
            except subprocess.TimeoutExpired:
                err.write(f"targeted_tests: timeout after {BUDGET_SECONDS}s, tests not verified\n")
                return 0
            if code != 0:
                tail = "\n".join(output.splitlines()[-TAIL_LINES:])
                reason = f"Targeted tests failed ({' '.join(argv)}):\n{tail}"
                out.write(json.dumps({"decision": "block", "reason": reason}))
                return 0
        cache.write_text(current)
    except Exception as exc:  # fail open
        err.write(f"targeted_tests: skipped ({exc})\n")
    return 0


if __name__ == "__main__":
    try:
        repo_root = _git(Path.cwd(), "rev-parse", "--show-toplevel").strip()
    except Exception:
        sys.exit(0)
    sys.exit(main(sys.stdin.read(), repo_root, default_runner, sys.stdout, sys.stderr))
