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

async function doImportEvent(page, url) {
  await page.goto("/");
  await page.waitForLoadState("domcontentloaded");

  await page.locator('input[type="url"]').fill(url);
  await page.waitForTimeout(400);

  // New UI: provider guide appears → click "Importer la compétition"
  const importBtn = page.locator("button", { hasText: "Importer la compétition" });
  await importBtn.waitFor({ timeout: 10_000 });
  await importBtn.click();

  // Wait for SSE done banner
  const doneBanner = page.locator("text=participants importés");
  await doneBanner.waitFor({ timeout: SCRAPE_TIMEOUT });
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
    label: "BreizhChrono — Swimrun Dinard 2025 Triathlon M",
    url: "https://resultats.breizhchrono.com/resultats-courses/triathlon-swimrun-dinard-cote-demeraude-2025-1488071608761-688/triathlon-distance-olympique",
    search: "AIGNEL",
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

      // 1. Import the whole event (new UI: provider guide → "Importer la compétition")
      await doImportEvent(page, tc.url);

      // 2. Banner already shows done at this point (waited in doImportEvent)

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
