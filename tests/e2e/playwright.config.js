// @ts-check
const { defineConfig, devices } = require("@playwright/test");
const path = require("path");

const BACKEND_PORT = 8099;
const FRONTEND_PORT = 3100;
const FRONTEND_URL = `http://localhost:${FRONTEND_PORT}`;
const BACKEND_URL = `http://localhost:${BACKEND_PORT}`;

/**
 * Playwright E2E test config.
 *
 * Tests run against:
 *  - Backend  : port 8099  (SQLite — never touches Supabase)
 *  - Frontend : port 3100  (VITE_API_URL=http://localhost:8099)
 *
 * Your normal dev stack (port 8001 / 3002) is untouched.
 */
module.exports = defineConfig({
  testDir: "./specs",
  timeout: 180_000,        // each test: 3min (scrapers make real HTTP calls on slow external servers)
  retries: 1,              // retry once on flaky network
  workers: 1,              // serial — scrapers are rate-sensitive, DB reset between tests
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],

  use: {
    baseURL: FRONTEND_URL,
    headless: true,
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },

  // ── Global setup/teardown (start/stop the SQLite backend) ──────────────────
  globalSetup: "./global-setup.js",
  globalTeardown: "./global-teardown.js",

  // ── Spin up the Vite dev server for tests ─────────────────────────────────
  webServer: {
    command: `npx cross-env VITE_API_URL=${BACKEND_URL} npx vite --port ${FRONTEND_PORT} --config vite.config.js`,
    cwd: path.resolve(__dirname, "../../frontend"),
    port: FRONTEND_PORT,
    reuseExistingServer: false,
    timeout: 30_000,
    env: {
      VITE_API_URL: BACKEND_URL,
    },
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
