"""Stops the test backend started by start-backend.py."""
import os
import signal
import sys
from pathlib import Path

PID_FILE = Path(__file__).parent / ".backend.pid"


def main():
    if not PID_FILE.exists():
        print("[test-backend] No PID file found, nothing to stop.")
        return
    pid = int(PID_FILE.read_text().strip())
    try:
        if sys.platform == "win32":
            import subprocess
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=True,
                           capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
        print(f"[test-backend] Stopped PID={pid}")
    except Exception as e:
        print(f"[test-backend] Could not stop PID={pid}: {e}")
    finally:
        PID_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
