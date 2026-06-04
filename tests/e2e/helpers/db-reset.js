/**
 * Resets the test SQLite database between tests by calling a dedicated
 * backend endpoint that truncates the results table.
 *
 * The backend exposes DELETE /api/test/reset (only when DATABASE_URL is sqlite).
 * Call resetDb(request) in a beforeEach or afterEach fixture.
 */

const BACKEND_URL = "http://localhost:8099";

/**
 * @param {import('@playwright/test').APIRequestContext} request
 */
async function resetDb(request) {
  const resp = await request.delete(`${BACKEND_URL}/api/test/reset`);
  if (!resp.ok()) {
    console.warn(`[db-reset] Reset endpoint returned ${resp.status()} — DB not cleaned.`);
  }
}

module.exports = { resetDb };
