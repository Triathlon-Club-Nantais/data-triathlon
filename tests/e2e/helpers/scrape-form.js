/**
 * Page-object helpers for the ScrapeForm component.
 * Wraps Playwright locators so specs stay readable.
 */

const TIMEOUT_SCRAPE = 45_000; // real HTTP scraper calls can be slow

/**
 * Paste a URL, optionally fill the athlete name, then click "Récupérer".
 * Waits for the result card OR an error OR a multiple-matches dialog.
 *
 * Returns one of:
 *   { status: 'ok',       result: Locator }
 *   { status: 'multiple', candidates: Locator }
 *   { status: 'error',    message: string }
 *   { status: 'warning',  kind: 'live_bc' | 'dead_bc' }
 */
async function scrape(page, { url, search = "" }) {
  await page.goto("/");
  await page.waitForLoadState("networkidle");

  const urlInput = page.locator('input[type="url"]');
  await urlInput.fill(url);
  await page.waitForTimeout(300);

  // Check if a blocking warning banner appeared (live/dead BC)
  const liveWarning  = page.locator("text=page live de Breizh Chrono");
  const deadWarning  = page.locator("text=résultats ne sont pas encore disponibles");
  if (await liveWarning.count() > 0) return { status: "warning", kind: "live_bc" };
  if (await deadWarning.count() > 0) return { status: "warning", kind: "dead_bc" };

  // Fill athlete name if needed
  const nameField = page.locator('input[placeholder*="ARNOUX"]');
  if (search && (await nameField.isVisible())) {
    await nameField.fill(search);
  }

  const btn = page.locator('button[type="submit"]');
  if (await btn.isDisabled()) {
    return { status: "warning", kind: "button_disabled" };
  }

  await btn.click();

  // Wait for one of: result card | multiple matches | error
  const resultCard    = page.locator('[data-testid="result-card"], .result-preview, text=Enregistrer');
  const multipleCard  = page.locator('text=Plusieurs athlètes');
  const errorBlock    = page.locator('[style*="color: rgb(229, 62, 62)"], [style*="#e53e3e"]');

  try {
    await Promise.race([
      resultCard.first().waitFor({ timeout: TIMEOUT_SCRAPE }),
      multipleCard.waitFor({ timeout: TIMEOUT_SCRAPE }),
      errorBlock.waitFor({ timeout: TIMEOUT_SCRAPE }),
    ]);
  } catch {
    return { status: "error", message: "Timeout waiting for result" };
  }

  if (await multipleCard.count() > 0) {
    return { status: "multiple", candidates: page.locator("button.candidate, [data-bib]") };
  }
  if (await errorBlock.count() > 0 && !(await resultCard.first().isVisible())) {
    const msg = await errorBlock.first().innerText();
    return { status: "error", message: msg };
  }

  return { status: "ok", result: resultCard.first() };
}

/**
 * After a successful scrape, check that key fields are filled.
 * Returns { time, hasSplits }.
 */
async function assertResultFields(page, { expectTime = true, expectSplits = false } = {}) {
  const fields = {};

  // Total time field
  const timeInput = page.locator('input[placeholder*="00:"], input[name*="time"], input').filter({ hasText: /\d{2}:\d{2}:\d{2}/ }).first();
  // Actually look for value in inputs
  const allInputs = page.locator("input");
  const count = await allInputs.count();

  let foundTime = false;
  let foundSplits = false;

  for (let i = 0; i < count; i++) {
    const val = await allInputs.nth(i).inputValue().catch(() => "");
    if (/^\d{2}:\d{2}:\d{2}/.test(val)) {
      foundTime = true;
      if (foundSplits) break; // found both
    }
  }

  // Look for split time inputs (swim, bike, run)
  const swimLabel = page.locator("label, span").filter({ hasText: /natation|swim/i }).first();
  if (await swimLabel.count() > 0) {
    // Find the sibling/following input
    const splitInput = page.locator("input").nth(7); // rough index — splits start around index 6-8
    const splitVal = await splitInput.inputValue().catch(() => "");
    foundSplits = /^\d{2}:\d{2}:\d{2}/.test(splitVal);
  }

  fields.time = foundTime;
  fields.splits = foundSplits;
  return fields;
}

module.exports = { scrape, assertResultFields };
