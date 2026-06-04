const fs = require("fs");
const path = require("path");

const PID_FILE = path.resolve(__dirname, "helpers", ".backend.pid");

module.exports = async function globalTeardown() {
  const pid = parseInt(process.env._TEST_BACKEND_PID || "0");
  if (!pid) {
    if (fs.existsSync(PID_FILE)) {
      const savedPid = parseInt(fs.readFileSync(PID_FILE, "utf8").trim());
      if (savedPid) killProcess(savedPid);
    }
    return;
  }
  killProcess(pid);
  if (fs.existsSync(PID_FILE)) fs.unlinkSync(PID_FILE);
  console.log("[teardown] Test backend stopped.");
};

function killProcess(pid) {
  try {
    if (process.platform === "win32") {
      require("child_process").execSync(`taskkill /F /PID ${pid} /T`, { stdio: "ignore" });
    } else {
      process.kill(pid, "SIGTERM");
    }
  } catch (_) {}
}
