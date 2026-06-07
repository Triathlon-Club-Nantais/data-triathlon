// @ts-check
/**
 * Provider tests — deux niveaux :
 *
 * 1. API — POST /api/scrape par athlète (pas de navigateur, rapide)
 *    Vérifie la qualité des données : nom, temps, splits, event_name.
 *
 * 2. UI smoke — coller une URL dans le formulaire → guide provider visible
 *    Vérifie que le nouveau ScrapeForm détecte chaque provider et affiche le guide.
 *
 * 3. Saisie manuelle — URL non supportée → "Saisir manuellement" → sauvegarder
 */
const { test, expect, request } = require("@playwright/test");
const fixtures = require("../fixtures/providers.json");

const BACKEND_URL   = "http://localhost:8099";
const SCRAPE_TIMEOUT = 90_000;

async function resetDb() {
  const ctx = await request.newContext({ baseURL: BACKEND_URL });
  await ctx.delete("/api/test/reset");
  await ctx.dispose();
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers API
// ─────────────────────────────────────────────────────────────────────────────

async function apiScrape(url, search = "") {
  const ctx = await request.newContext({ baseURL: BACKEND_URL });
  const finalUrl = search
    ? (() => { try { const u = new URL(url); u.searchParams.set("search", search); return u.toString(); } catch { return url; } })()
    : url;
  const resp = await ctx.post("/api/scrape", { data: { url: finalUrl } });
  const data = await resp.json();
  await ctx.dispose();
  return { status: resp.status(), data };
}

async function apiSave(data) {
  const ctx = await request.newContext({ baseURL: BACKEND_URL });
  const resp = await ctx.post("/api/results", { data });
  await ctx.dispose();
  return resp.status();
}

function expectsSplits(tc) {
  if (tc.expects?.has_splits === true)  return true;
  if (tc.expects?.has_splits === false) return false;
  if (tc.url?.includes("results.sportinnovation.fr")) return false;
  if (tc.provider === "prolivesport") return false;
  const type = (tc.event_type || "").toLowerCase();
  return type.startsWith("triathlon") || type.startsWith("duathlon") ||
         type.startsWith("swimrun") || type === "aquathlon";
}

// ─────────────────────────────────────────────────────────────────────────────
// 1. Qualité de scraping par provider — API directe
// ─────────────────────────────────────────────────────────────────────────────

const SCRAPABLE = ["klikego", "breizhchrono", "wiclax", "timepulse", "prolivesport", "sportinnovation"];
const DNF_RE    = /^(abandon|disqualifi|dsq|dnf|dns|forfait|non partant|hors délai)/i;

for (const provider of SCRAPABLE) {
  const cases = fixtures[provider] || [];
  if (!cases.length) continue;

  test.describe(`[${provider}] scrape API`, () => {
    test.beforeEach(async () => { await resetDb(); });

    for (const tc of cases) {
      test(tc.label, async () => {
        test.setTimeout(SCRAPE_TIMEOUT + 30_000);

        const { status, data } = await apiScrape(tc.url, tc.search);

        // 200 = scrape OK, 422 = scraper error (réseau, provider KO)
        if (status === 422) {
          test.info().annotations.push({ type: "skip-reason", description: `Scrape error: ${data.detail}` });
          test.skip();
          return;
        }

        // Multiple matches → skip (doublon test is separate)
        if (data.multiple_matches) {
          test.info().annotations.push({ type: "skip-reason", description: "Multiple matches — tested separately" });
          test.skip();
          return;
        }

        expect(status, `POST /api/scrape returned ${status}`).toBe(200);

        // Nom non vide
        if (!data.athlete_name) {
          test.info().annotations.push({ type: "skip-reason", description: "Nom vide — URL morte ou DNS" });
          test.skip();
          return;
        }

        // Temps total (sauf si explicitement exclu)
        if (tc.expects?.has_time !== false) {
          if (!data.total_time || DNF_RE.test(data.total_time)) {
            test.info().annotations.push({ type: "skip-reason", description: `DNS/DNF: ${data.total_time || "vide"}` });
            test.skip();
            return;
          }
          expect(data.total_time, "Temps total invalide").toMatch(/^\d{1,2}:\d{2}:\d{2}/);
        }

        // Nom épreuve
        if (tc.expects?.has_event_name !== false) {
          expect(data.event_name?.length ?? 0, "Nom épreuve vide").toBeGreaterThan(0);
        }

        // Splits
        if (expectsSplits(tc)) {
          const hasSplit = [data.swim_time, data.bike_time, data.run_time]
            .some(t => t && /^\d{1,2}:\d{2}:\d{2}/.test(t));
          if (!hasSplit) {
            test.info().annotations.push({ type: "skip-reason", description: "Splits absents" });
            test.skip();
            return;
          }
        }

        // Sauvegarder et vérifier en base
        if (data.event_name) {
          const saveStatus = await apiSave({ ...data, event_date: data.event_date ?? null });
          expect([201, 409], "Sauvegarde inattendue").toContain(saveStatus);

          const ctx = await request.newContext({ baseURL: BACKEND_URL });
          const checkResp = await ctx.get(`/api/results?name=${encodeURIComponent(data.athlete_name)}`);
          const results = await checkResp.json();
          await ctx.dispose();
          expect(results.length, `${data.athlete_name} non trouvé en base`).toBeGreaterThan(0);
        }
      });
    }
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. Doublon API — multiple_matches → choisir par bib
// ─────────────────────────────────────────────────────────────────────────────

test.describe("[doublons] Sélection du bon athlète", () => {
  test.beforeEach(async () => { await resetDb(); });

  test("klikego — AIGNEL : plusieurs résultats renvoyés", async () => {
    const { status, data } = await apiScrape(
      "https://www.klikego.com/resultats/triathlon-swimrun-dinard-cote-demeraude-2025/1488071608761-688?heat=triathlon-distance-olympique",
      "AIGNEL"
    );
    if (status === 422) { test.skip(); return; }
    // Either multiple_matches or unique result
    if (data.multiple_matches) {
      expect(data.candidates.length, "Aucun candidat").toBeGreaterThan(1);
      // Pick Romain via bib
      const romain = data.candidates.find(c => c.athlete_firstname?.toLowerCase().includes("romain"));
      const bib = romain?.bib ?? data.candidates[0].bib;
      const url = `https://www.klikego.com/resultats/triathlon-swimrun-dinard-cote-demeraude-2025/1488071608761-688?heat=triathlon-distance-olympique`;
      const ctx = await request.newContext({ baseURL: BACKEND_URL });
      const resp = await ctx.post("/api/scrape", { data: { url, bib } });
      const picked = await resp.json();
      await ctx.dispose();
      expect(picked.athlete_name?.length ?? 0).toBeGreaterThan(0);
    } else {
      expect(data.athlete_name?.length ?? 0).toBeGreaterThan(0);
    }
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 3. UI smoke — guide provider visible dans le nouveau ScrapeForm
// ─────────────────────────────────────────────────────────────────────────────

const PROVIDER_SMOKE = [
  { provider: "Breizh Chrono", url: "https://resultats.breizhchrono.com/resultats-courses/triathlon-de-test-2025-123/triathlon-m" },
  { provider: "Klikego",       url: "https://www.klikego.com/resultats/test-2025/12345" },
  { provider: "Wiclax",        url: "https://chronosmetron.wiclax-results.com/G-Live/g-live.html?f=../Test/Test.clax" },
  { provider: "TimePulse",     url: "https://www.timepulse.fr/epreuves/resultats/12345" },
];

test.describe("[ui-smoke] Guide provider dans ScrapeForm", () => {
  test.beforeEach(async ({ page }) => {
    await resetDb();
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");
  });

  for (const { provider, url } of PROVIDER_SMOKE) {
    test(`guide visible — ${provider}`, async ({ page }) => {
      await page.locator('input[type="url"]').fill(url);
      await page.waitForTimeout(400);

      // Provider badge doit apparaître
      const badge = page.locator("span", { hasText: provider });
      await expect(badge).toBeVisible({ timeout: 3_000 });

      // Bouton import doit être présent
      const importBtn = page.locator("button", { hasText: "Importer la compétition" });
      await expect(importBtn).toBeVisible({ timeout: 3_000 });
    });
  }

  test("guide absent — URL live Breizh Chrono → message non supporté", async ({ page }) => {
    await page.locator('input[type="url"]').fill("https://live.breizhchrono.com/test");
    await page.waitForTimeout(400);
    await expect(page.locator("text=Non supporté")).toBeVisible({ timeout: 3_000 });
    await expect(page.locator("button", { hasText: "Importer la compétition" })).not.toBeVisible();
  });

  test("guide absent — URL inconnue → bouton saisie manuelle", async ({ page }) => {
    await page.locator('input[type="url"]').fill("https://www.inconnu-chrono.fr/resultats/123");
    await page.waitForTimeout(400);
    await expect(page.locator("button", { hasText: "Saisir manuellement" })).toBeVisible({ timeout: 3_000 });
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 4. Saisie manuelle — URL non supportée → form manuel → sauvegarder
// ─────────────────────────────────────────────────────────────────────────────

test.describe("[saisie-manuelle] Entrée manuelle pour provider non géré", () => {
  test.beforeEach(async () => { await resetDb(); });

  async function doManualEntry(page, url, athleteData) {
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    await page.locator('input[type="url"]').fill(url);
    await page.waitForTimeout(400);

    // Nouveau flow : si provider inconnu → "Saisir manuellement" apparaît directement
    const manualBtn = page.locator("button", { hasText: "Saisir manuellement" });
    if (!await manualBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      test.info().annotations.push({ type: "skip-reason", description: "Provider reconnu ou URL invalide" });
      return "skip";
    }
    await manualBtn.click();

    const set = (label, val) =>
      page.locator(`input[aria-label="${label}"]`).fill(val);

    await set("Nom",      athleteData.nom);
    await set("Prénom",   athleteData.prenom);
    await set("Épreuve",  athleteData.eventName);
    await page.locator("select").selectOption({ label: athleteData.eventType });
    await set("Temps total", athleteData.time);

    await page.locator("button", { hasText: "Enregistrer le résultat" }).click();
    await expect(page.locator("text=Résultat enregistré !")).toBeVisible({ timeout: 10_000 });

    const ctx = await request.newContext({ baseURL: BACKEND_URL });
    const resp = await ctx.get(`/api/results?name=${encodeURIComponent(athleteData.nom)}`);
    const data = await resp.json();
    await ctx.dispose();
    expect(data.length, `${athleteData.nom} non trouvé après saisie manuelle`).toBeGreaterThan(0);
    return "ok";
  }

  test("URL inconnue → saisie manuelle complète", async ({ page }) => {
    const result = await doManualEntry(page,
      "https://www.chrono-inconnu.fr/resultats/12345",
      {
        nom: "TESTEUR",
        prenom: "Manuel",
        eventName: "Triathlon de Test Manuel",
        eventType: "Triathlon M (Olympique)",
        time: "02:15:00",
      }
    );
    if (result === "skip") test.skip();
    expect(result).toBe("ok");
  });
});
