const { execSync, spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const http = require("http");

const BACKEND_PORT = 8099;
const DB_PATH = path.resolve(__dirname, "test_e2e.db");
const PID_FILE = path.resolve(__dirname, "helpers", ".backend.pid");
const BACKEND_DIR = path.resolve(__dirname, "../../backend");

// Python executable inside the backend venv
function findPython() {
  const win = path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");
  const unix = path.join(BACKEND_DIR, ".venv", "bin", "python");
  if (fs.existsSync(win)) return win;
  if (fs.existsSync(unix)) return unix;
  return "python3";
}

function waitForBackend(port, timeoutMs = 30_000) {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeoutMs;
    const check = () => {
      const req = http.get(`http://127.0.0.1:${port}/api/results?limit=1`, (res) => {
        if (res.statusCode === 200) return resolve();
        setTimeout(check, 1000);
      });
      req.on("error", () => {
        if (Date.now() > deadline) return reject(new Error(`Backend on port ${port} did not start in time`));
        setTimeout(check, 1000);
      });
      req.end();
    };
    check();
  });
}

module.exports = async function globalSetup() {
  console.log("\n[setup] Starting test backend (SQLite, port 8099)…");

  // Remove stale test DB
  if (fs.existsSync(DB_PATH)) {
    fs.unlinkSync(DB_PATH);
    console.log("[setup] Removed stale test_e2e.db");
  }

  const python = findPython();

  const proc = spawn(
    python,
    ["-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", String(BACKEND_PORT)],
    {
      cwd: BACKEND_DIR,
      env: { ...process.env, DATABASE_URL: `sqlite:///${DB_PATH}` },
      stdio: ["ignore", "pipe", "pipe"],
      detached: false,
    }
  );

  proc.stdout.on("data", (d) => process.stdout.write(`[backend] ${d}`));
  proc.stderr.on("data", (d) => process.stderr.write(`[backend] ${d}`));

  fs.mkdirSync(path.dirname(PID_FILE), { recursive: true });
  fs.writeFileSync(PID_FILE, String(proc.pid));

  try {
    await waitForBackend(BACKEND_PORT, 30_000);
    console.log("[setup] Backend ready.");
  } catch (err) {
    proc.kill();
    throw err;
  }

  // Store process ref for teardown
  process.env._TEST_BACKEND_PID = String(proc.pid);
};
