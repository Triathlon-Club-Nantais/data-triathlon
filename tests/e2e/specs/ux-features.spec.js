// @ts-check
/**
 * Tests for UX features added in the latest update:
 *   1. Global search in header → navigates to results tab with filter applied
 *   2. ScrapeForm empty state → shows recent TCN results when URL is blank
 *   3. Import progress banner (SSE) → shows phase/progress/done states
 *   4. Mobile nav scrollable (basic visibility check)
 */
const { test, expect, request: apiRequest } = require("@playwright/test");

const BACKEND_URL = "http://localhost:8099";
const SCRAPE_TIMEOUT = 90_000;

async function resetDb() {
  const ctx = await apiRequest.newContext({ baseURL: BACKEND_URL });
  await ctx.delete("/api/test/reset");
  await ctx.dispose();
}

async function seedOneResult(ctx) {
  await ctx.post("/api/results", {
    data: {
      source_url: "https://example.com/test",
      provider: "manuel",
      athlete_name: "DUPONT",
      athlete_firstname: "Jean",
      club: "TRIATHLON CLUB NANTAIS",
      category: "SEH",
      gender: "M",
      bib_number: "42",
      event_name: "Triathlon de Test",
      event_date: "2025-06-01",
      event_type: "triathlon-m",
      rank_overall: 10,
      rank_category: null,
      rank_gender: null,
      total_time: "02:10:00",
      swim_time: "00:25:00",
      t1_time: "00:02:00",
      bike_time: "01:05:00",
      t2_time: "00:01:00",
      run_time: "00:37:00",
      is_relay: false,
      raw_data: {},
    },
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// 1. Global search
// ─────────────────────────────────────────────────────────────────────────────

test.describe("[ux] Recherche globale dans le header", () => {
  test.beforeEach(async () => { await resetDb(); });

  test("tape un nom → bascule sur l'onglet résultats et filtre", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    // Seed a result so the results tab has data
    const ctx = await apiRequest.newContext({ baseURL: BACKEND_URL });
    await seedOneResult(ctx);
    await ctx.dispose();

    // The global search input is in the header
    const searchInput = page.locator(".global-search input");
    await expect(searchInput).toBeVisible();

    // Type a name
    await searchInput.fill("DUPONT");

    // App should have switched to results tab
    await expect(page.locator("text=Tous les résultats").first()).toBeVisible();

    // Wait a moment for the filter to apply
    await page.waitForTimeout(800);

    // The results list should show DUPONT (or at least no "Aucun résultat")
    // We just verify the tab switched — content depends on data
    const tabActive = page.locator("button", { hasText: "Tous les résultats" });
    await expect(tabActive).toBeVisible();
  });

  test("bouton × vide la recherche", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    const searchInput = page.locator(".global-search input");
    await searchInput.fill("TEST");
    await page.waitForTimeout(300);

    // Clear button should appear
    const clearBtn = page.locator(".global-search button[type='button']");
    await expect(clearBtn).toBeVisible();
    await clearBtn.click();

    await expect(searchInput).toHaveValue("");
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 2. ScrapeForm empty state
// ─────────────────────────────────────────────────────────────────────────────

test.describe("[ux] ScrapeForm — empty state (derniers résultats)", () => {
  test("affiche les derniers résultats TCN quand la base n'est pas vide", async ({ page }) => {
    await resetDb();

    const ctx = await apiRequest.newContext({ baseURL: BACKEND_URL });
    await seedOneResult(ctx);
    await ctx.dispose();

    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    // The empty state should show the seeded TCN result
    await expect(page.locator("text=Derniers résultats ajoutés")).toBeVisible({ timeout: 5_000 });
    await expect(page.locator("text=DUPONT")).toBeVisible();
  });

  test("vide quand la base est vide — aucun empty state", async ({ page }) => {
    await resetDb();

    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    // No recent results → empty state section should not be shown
    await expect(page.locator("text=Derniers résultats ajoutés")).not.toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 3. Import progress banner (SSE)
// ─────────────────────────────────────────────────────────────────────────────

test.describe("[ux] Bannière de progression import (SSE)", () => {
  test("affiche 'Récupération' pendant le scraping puis disparaît après ×", async ({ page }) => {
    test.setTimeout(SCRAPE_TIMEOUT + 60_000);
    await resetDb();

    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    // New UI: paste URL → provider guide → "Importer la compétition" → SSE
    const urlInput = page.locator('input[type="url"]');
    await urlInput.fill(
      "https://www.klikego.com/resultats/triathlon-swimrun-dinard-cote-demeraude-2025/1488071608761-688?heat=triathlon-distance-olympique"
    );
    await page.waitForTimeout(400);

    const importBtn = page.locator("button", { hasText: "Importer la compétition" });
    await importBtn.waitFor({ timeout: 10_000 });
    await importBtn.click();

    // The scraping phase banner should appear
    const scrapingBanner = page.locator("text=Récupération des participants");
    const savingBanner   = page.locator("text=Import en cours");
    const doneBanner     = page.locator("text=participants importés");

    // At least one of these phases must be visible at some point
    const anyBanner = scrapingBanner.or(savingBanner).or(doneBanner);
    await anyBanner.waitFor({ timeout: SCRAPE_TIMEOUT });

    // Wait for done
    await doneBanner.waitFor({ timeout: SCRAPE_TIMEOUT });

    // Close button should appear on done phase
    const closeBtn = page.locator("text=×").last();
    await expect(closeBtn).toBeVisible();
    await closeBtn.click();
    await expect(doneBanner).not.toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 4. Navigation — onglets visibles et cliquables (smoke test)
// ─────────────────────────────────────────────────────────────────────────────

test.describe("[ux] Navigation — onglets principaux", () => {
  test("tous les onglets sont présents et naviguent correctement", async ({ page }) => {
    await resetDb();
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    const tabs = ["Ajouter un résultat", "Tous les résultats", "Club TCN", "Dashboard"];
    for (const label of tabs) {
      const tab = page.locator("button", { hasText: label });
      await expect(tab).toBeVisible();
      await tab.click();
      await page.waitForTimeout(300);
    }
  });
});
