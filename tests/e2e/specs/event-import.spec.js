// @ts-check
/**
 * Tests the "import all event participants" flow:
 *   1. User scrapes & saves an individual result
 *   2. The app automatically imports all participants from the same event
 *   3. Club TCN tab shows multiple TCN members from that event
 */
const { test, expect, request: apiRequest } = require("@playwright/test");

const BACKEND_URL    = "http://localhost:8099";
const SCRAPE_TIMEOUT = 90_000;

async function resetDb() {
  const ctx = await apiRequest.newContext({ baseURL: BACKEND_URL });
  await ctx.delete("/api/test/reset");
  await ctx.dispose();
}

async function doScrapeAndSave(page, url, search) {
  await page.goto("/");
  await page.waitForLoadState("domcontentloaded"); // faster than "load" — avoid networkidle blocking

  await page.locator('input[type="url"]').fill(url);
  await page.waitForTimeout(400);

  const nameField = page.locator('input[placeholder*="ARNOUX"]');
  if (search && await nameField.isVisible({ timeout: 1_000 }).catch(() => false)) {
    await nameField.fill(search);
  }

  await page.locator('button[type="submit"]').click();

  // Handle multiple matches → pick first matching name
  const multiMatch = page.locator("text=Plusieurs athlètes trouvés");
  const preview    = page.locator("text=Enregistrer le résultat");
  const outcome = await Promise.race([
    preview.waitFor({ timeout: SCRAPE_TIMEOUT }).then(() => "ok"),
    multiMatch.waitFor({ timeout: SCRAPE_TIMEOUT }).then(() => "multiple"),
  ]).catch(() => "timeout");

  if (outcome === "timeout") {
    throw new Error(`Scrape timed out for ${url}`);
  }

  if (outcome === "multiple") {
    const nameBtn = page.locator("button").filter({ hasText: new RegExp(search, "i") });
    if (await nameBtn.count() > 0) {
      await nameBtn.first().click();
    } else {
      await page.locator("button").filter({ hasText: /Dossard/ }).first().click();
    }
    await preview.waitFor({ timeout: SCRAPE_TIMEOUT });
  }

  // Save
  await page.locator("text=Enregistrer le résultat").click();
  await expect(page.locator("text=Résultat enregistré !")).toBeVisible({ timeout: 10_000 });
}

// ─────────────────────────────────────────────────────────────────────────────
// Test cases: events known to have multiple TCN members
// ─────────────────────────────────────────────────────────────────────────────

const MULTI_TCN_EVENTS = [
  {
    label: "Klikego — Swimrun Dinard 2025 (TCN multiple)",
    url: "https://www.klikego.com/resultats/triathlon-swimrun-dinard-cote-demeraude-2025/1488071608761-688?heat=triathlon-distance-olympique",
    search: "AIGNEL",
    // At least AIGNEL Romain + Maeva should be imported
    minTcnResults: 2,
  },
  {
    label: "BreizhChrono — Châtelaillon 2026",
    url: "https://resultats.breizhchrono.com/resultats-courses/triathlon-chatelaillon-plage-2026-1360808403296-12/triathlon-l",
    search: "AUBERGEON",
    minTcnResults: 1,
  },
  {
    label: "SportInnovation — Vertou M 2026",
    url: "https://www.sportinnovation.fr/Evenements/Resultats/6452",
    search: "ASSEMAT",
    minTcnResults: 0,  // sportinnovation doesn't populate club field → club filter unreliable
  },
  {
    // Wiclax ChronoSmetron E/R format — validates scrape_event_all handles <E>/<R> elements
    label: "Wiclax ChronoSmetron — Triathlon de Vertou 2026 (format E/R)",
    url: "https://www.chronosmetron.com/754-triathlon-de-vertou-2026",
    search: "AUBERGEON",
    minTcnResults: 1,
  },
];

test.describe("Import événement → section Club TCN", () => {
  for (const tc of MULTI_TCN_EVENTS) {
    test(tc.label, async ({ page }) => {
      test.setTimeout(180_000);

      await resetDb();

      // 1. Scrape & save individual result (triggers importEvent in background)
      await doScrapeAndSave(page, tc.url, tc.search);

      // 2. Wait for the import banner to indicate progress or completion
      // New SSE banner: shows "importé" (saving phase counter) or "participants importés" (done)
      const importBanner = page.locator("text=importé").or(page.locator("text=déjà présent"));
      await importBanner.waitFor({ timeout: SCRAPE_TIMEOUT }).catch(() => {});

      // 3. Check via API: the saved athlete must appear by name
      const ctx = await apiRequest.newContext({ baseURL: BACKEND_URL });

      const nameResp = await ctx.get(`/api/results?name=${encodeURIComponent(tc.search)}`);
      const nameData = await nameResp.json();
      expect(
        nameData.length,
        `L'athlète ${tc.search} doit être présent après save (import individuel)`
      ).toBeGreaterThanOrEqual(1);

      // 4. Check via API: TCN club filter must return at least minTcnResults
      //    (requires club data populated — either from Phase 1 club column or Phase 2 city filter)
      const clubResp = await ctx.get("/api/results?page_size=200&club=nantais%7CTCN");
      const clubData = await clubResp.json();
      await ctx.dispose();

      expect(
        clubData.length,
        `Attendu ≥ ${tc.minTcnResults} résultats TCN après import de ${tc.label}, obtenu ${clubData.length}`
      ).toBeGreaterThanOrEqual(tc.minTcnResults);

      // 5. Navigate to Club TCN tab and verify it shows results
      const clubTab = page.locator("text=Club TCN");
      if (await clubTab.isVisible()) {
        await clubTab.click();
        await page.waitForLoadState("load");
        await page.waitForTimeout(1_000);
      }
      const noResults = page.locator("text=Aucun résultat");
      const noResultsVisible = await noResults.isVisible().catch(() => false);
      expect(
        noResultsVisible,
        `Club TCN affiche 'Aucun résultat' alors que ${clubData.length} résultats TCN existent`
      ).toBe(false);
    });
  }
});
