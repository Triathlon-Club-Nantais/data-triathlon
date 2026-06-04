"""
Test backend launcher.
Starts a FastAPI backend on port 8099 with a fresh SQLite database.
Called by Playwright globalSetup — do not use in production.

Usage:
  python start-backend.py [--port 8099] [--db-path ./test_e2e.db]

Writes the PID to .backend.pid so globalTeardown can stop it.
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[3] / "backend"
VENV_PYTHON = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
if not VENV_PYTHON.exists():
    # Linux/Mac path
    VENV_PYTHON = BACKEND_DIR / ".venv" / "bin" / "python"

PID_FILE = Path(__file__).parent / ".backend.pid"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument("--db-path", default="./test_e2e.db")
    args = parser.parse_args()

    db_path = Path(args.db_path).resolve()
    # Remove stale test DB
    if db_path.exists():
        db_path.unlink()
        print(f"[test-backend] Removed stale DB: {db_path}")

    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}

    proc = subprocess.Popen(
        [str(VENV_PYTHON), "-m", "uvicorn", "main:app",
         "--host", "127.0.0.1", "--port", str(args.port)],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    PID_FILE.write_text(str(proc.pid))
    print(f"[test-backend] Started PID={proc.pid} port={args.port} db={db_path}")

    # Wait until the backend responds
    import urllib.request
    url = f"http://127.0.0.1:{args.port}/api/results?limit=1"
    for attempt in range(30):
        time.sleep(1)
        try:
            urllib.request.urlopen(url, timeout=2)
            print(f"[test-backend] Ready after {attempt + 1}s")
            break
        except Exception:
            pass
    else:
        proc.kill()
        sys.exit(1)


if __name__ == "__main__":
    main()
