// @ts-check
/**
 * Regression test — Breizh Chrono pagination completeness.
 *
 * BC exposes a "default" page (page="") that contains athletes not present
 * on numbered pages (page=1,2,3…). This suite verifies that scrape_event_all
 * captures ALL athletes, including those only on page="".
 *
 * For each BC URL in the fixture:
 *   1. Fetch BC page="" directly → collect "hidden" bib set
 *   2. Call POST /api/scrape/event → collect imported bib set
 *   3. Assert every hidden bib is present in the import
 *
 * Data: tests/e2e/fixtures/reliability_urls.json (gitignored)
 * This file must be generated locally via generate_test_fixtures.py.
 */
const { test, expect, request } = require("@playwright/test");
const fs  = require("fs");
const path = require("path");

const BACKEND_URL = "http://localhost:8099";
const BC_BASE     = "https://resultats.breizhchrono.com";
const SCRAPE_TIMEOUT = 120_000;

// ── Load fixture ──────────────────────────────────────────────────────────────
const FIXTURE_PATH = path.join(__dirname, "../fixtures/reliability_urls.json");
const allCases = fs.existsSync(FIXTURE_PATH)
  ? JSON.parse(fs.readFileSync(FIXTURE_PATH, "utf-8"))
  : [];
const BC_CASES = allCases.filter(c => c.provider === "breizhchrono");

// ── Helpers ───────────────────────────────────────────────────────────────────

function parseBcUrl(url) {
  // Extract event_id and heat from BC URL path
  // /resultats-courses/{slug}-{event_id}/{heat}
  try {
    const { pathname } = new URL(url);
    const parts = pathname.split("/").filter(Boolean);
    // parts[0] = "resultats-courses", parts[1] = "{slug}-{event_id}", parts[2] = "{heat}"
    if (parts.length < 3) return null;
    const slugWithId = parts[1];
    const heat = parts[2];
    const m = slugWithId.match(/(\d{10,}-\d+)$/);
    if (!m) return null;
    return { eventId: m[1], heat };
  } catch {
    return null;
  }
}

async function fetchBcPageEmptyBibs(eventId, heat) {
  /** Fetch BC page='' and return set of bib numbers (the "hidden" athletes). */
  const searchUrl =
    `${BC_BASE}/v8/evenement/resultats-search.jsp` +
    `?event=${eventId}&heat=${heat}&search=&city=&category=&sexe=&page=`;
  try {
    const resp = await fetch(searchUrl, {
      headers: { "User-Agent": "Mozilla/5.0 Chrome/124.0", Referer: BC_BASE },
    });
    if (!resp.ok) return new Set();
    const html = await resp.text();
    const bibs = new Set();
    // Parse data-dossard attributes from result rows
    const re = /data-dossard="([^"]+)"/g;
    let m;
    while ((m = re.exec(html)) !== null) bibs.add(m[1]);
    return bibs;
  } catch {
    return new Set();
  }
}

async function resetDb() {
  const ctx = await request.newContext({ baseURL: BACKEND_URL });
  await ctx.delete("/api/test/reset");
  await ctx.dispose();
}

async function importEvent(url) {
  const ctx = await request.newContext({ baseURL: BACKEND_URL });
  const resp = await ctx.post("/api/scrape/event", { data: { url } });
  const data = await resp.json();
  await ctx.dispose();
  return data; // { imported, skipped }
}

async function getImportedBibs(eventName) {
  const ctx = await request.newContext({ baseURL: BACKEND_URL });
  const resp = await ctx.get(
    `/api/results?event_name=${encodeURIComponent(eventName)}&page_size=2000`
  );
  const results = await resp.json();
  await ctx.dispose();
  return new Set(results.map(r => r.bib_number).filter(Boolean));
}

// ── Tests ─────────────────────────────────────────────────────────────────────

test.describe("BC pagination — page='' athletes inclus dans l'import", () => {

  // Smoke test toujours présent (pas de fixture requise)
  test("swimrun-court-solo Dinard 2025 — bib 244 (DUPONT) présent", async () => {
    test.setTimeout(SCRAPE_TIMEOUT);
    await resetDb();

    const url =
      "https://resultats.breizhchrono.com/resultats-courses/" +
      "triathlon-swimrun-dinard-cote-demeraude-2025-1488071608761-688/swimrun-court-solo";

    const parsed = parseBcUrl(url);
    if (!parsed) test.skip();

    // page="" bibs
    const hiddenBibs = await fetchBcPageEmptyBibs(parsed.eventId, parsed.heat);
    expect(hiddenBibs.size, "BC page='' doit retourner des résultats").toBeGreaterThan(0);
    expect(hiddenBibs.has("244"), "Bib 244 (DUPONT) doit être sur page=''").toBe(true);

    // Import via API
    await importEvent(url);
    const importedBibs = await getImportedBibs("Triathlon Swimrun Dinard Cote Demeraude 2025");

    // Tous les bibs de page="" doivent être importés
    const missing = [...hiddenBibs].filter(b => !importedBibs.has(b));
    expect(
      missing.length,
      `${missing.length} bib(s) de page='' manquants: ${missing.slice(0,5).join(", ")}`
    ).toBe(0);

    expect(importedBibs.size, "164 participants attendus").toBe(164);
  });

  // Tests dynamiques sur toutes les URLs BC du fixture
  for (const tc of BC_CASES) {
    test(`pagination complète — ${tc.url.replace(BC_BASE, "")}`, async () => {
      test.setTimeout(SCRAPE_TIMEOUT);
      await resetDb();

      const parsed = parseBcUrl(tc.url);
      if (!parsed) {
        test.info().annotations.push({ type: "skip-reason", description: "URL BC non parseable" });
        test.skip();
        return;
      }

      // Récupère les bibs de page="" (les "hidden athletes")
      const hiddenBibs = await fetchBcPageEmptyBibs(parsed.eventId, parsed.heat);
      if (hiddenBibs.size === 0) {
        test.info().annotations.push({ type: "skip-reason", description: "page='' vide — événement probablement expiré" });
        test.skip();
        return;
      }

      // Import via API backend
      const importResult = await importEvent(tc.url);
      if (importResult.imported === 0 && importResult.skipped === 0) {
        test.info().annotations.push({ type: "skip-reason", description: "Import vide — événement expiré" });
        test.skip();
        return;
      }

      // Récupère les bibs importés
      const importedBibs = await getImportedBibs(
        // L'event_name vient du slug (approximatif, suffisant pour ce test)
        parsed.heat
      );

      // Méthode alternative : chercher via l'API sans filtre event_name
      // puisqu'on vient de reset + import un seul événement
      const ctx = await request.newContext({ baseURL: BACKEND_URL });
      const resp = await ctx.get("/api/results?page_size=2000");
      const allResults = await resp.json();
      await ctx.dispose();
      const allBibs = new Set(allResults.map(r => r.bib_number).filter(Boolean));

      const missing = [...hiddenBibs].filter(b => !allBibs.has(b));
      expect(
        missing.length,
        `${missing.length} bib(s) de page='' absents de l'import: ${missing.slice(0,5).join(", ")}`
      ).toBe(0);
    });
  }
});
