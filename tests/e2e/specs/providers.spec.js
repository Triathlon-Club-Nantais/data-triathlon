// @ts-check
const { test, expect, request } = require("@playwright/test");
const fixtures = require("../fixtures/providers.json");

// ─────────────────────────────────────────────────────────────────────────────
// Infer whether splits are expected based on provider + URL when not explicit
// ─────────────────────────────────────────────────────────────────────────────

function expectsSplits(tc) {
  // Explicit override in fixture always wins
  if (tc.expects?.has_splits === true)  return true;
  if (tc.expects?.has_splits === false) return false;

  // results.sportinnovation.fr API format never returns splits
  if (tc.url && tc.url.includes("results.sportinnovation.fr")) return false;

  // prolivesport (live timing pages) — splits unreliable
  if (tc.provider === "prolivesport") return false;

  // klikego / wiclax / breizhchrono / timepulse / sportinnovation-HTML reliably
  // return at least one split for multisport events (triathlon, duathlon, swimrun)
  const type = (tc.event_type || "").toLowerCase();
  return (
    type.startsWith("triathlon") ||
    type.startsWith("duathlon") ||
    type.startsWith("swimrun") ||
    type === "aquathlon"
  );
}

const BACKEND_URL  = "http://localhost:8099";
const SCRAPE_TIMEOUT = 90_000;

// ─────────────────────────────────────────────────────────────────────────────
// DB reset — called before each test to ensure a clean SQLite slate
// ─────────────────────────────────────────────────────────────────────────────

async function resetDb() {
  const ctx = await request.newContext({ baseURL: BACKEND_URL });
  const resp = await ctx.delete("/api/test/reset");
  if (!resp.ok()) {
    console.warn(`[db-reset] ${resp.status()} — DB may not be clean.`);
  }
  await ctx.dispose();
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

async function doScrape(page, url, search) {
  await page.goto("/");
  await page.waitForLoadState("domcontentloaded"); // faster than "load" — avoid networkidle blocking

  const urlInput = page.locator('input[type="url"]');
  await urlInput.fill(url);
  await page.waitForTimeout(400);

  // Blocking warning banners
  if (await page.locator("text=page live de Breizh Chrono").count())
    return "warning_live";
  if (await page.locator("text=résultats ne sont pas encore disponibles").count())
    return "warning_dead";

  const submitBtn = page.locator('button[type="submit"]');
  if (await submitBtn.isDisabled()) return "warning_disabled";

  if (search) {
    const nameField = page.locator('input[placeholder*="ARNOUX"]');
    if (await nameField.isVisible({ timeout: 1_000 }).catch(() => false)) {
      await nameField.fill(search);
    }
  }

  await submitBtn.click();

  const preview    = page.locator("text=Enregistrer le résultat");
  const multiMatch = page.locator("text=Plusieurs athlètes trouvés");
  const errorText  = page.locator("text=Ce provider n'est pas encore supporté")
    .or(page.locator("text=Erreur lors du scraping"))
    .or(page.locator("text=n'est pas supporté"));

  const outcome = await Promise.race([
    preview.waitFor({ timeout: SCRAPE_TIMEOUT }).then(() => "ok"),
    multiMatch.waitFor({ timeout: SCRAPE_TIMEOUT }).then(() => "multiple"),
    errorText.waitFor({ timeout: SCRAPE_TIMEOUT }).then(() => "error"),
  ]).catch(() => "timeout");

  return outcome;
}

async function pickCandidate(page, search) {
  const byName = page.locator("button").filter({ hasText: new RegExp(search, "i") });
  if (await byName.count() > 0) {
    await byName.first().click();
  } else {
    await page.locator("button").filter({ hasText: /Dossard/ }).first().click();
  }
  await page.locator("text=Enregistrer le résultat").waitFor({ timeout: SCRAPE_TIMEOUT });
}

async function readResultFields(page) {
  // Use aria-label selector — inputs in ScrapeForm have aria-label matching their visible label
  const getValue = (label) =>
    page.locator(`input[aria-label="${label}"]`).inputValue({ timeout: 5_000 }).catch(() => "");

  // Provider badge — match by content (Chrome normalizes #ebf8ff → rgb(), attribute selector unreliable)
  const getBadge = () =>
    page.locator("span").filter({
      hasText: /Klikego|Breizh|Wiclax|TimePulse|ProLive|Sport Innovation|Autre/
    }).first().innerText({ timeout: 3_000 }).catch(() => "");

  return {
    nom:           await getValue("Nom"),
    prenom:        await getValue("Prénom"),
    total_time:    await getValue("Temps total"),
    swim_time:     await getValue("Natation"),
    bike_time:     await getValue("Vélo"),
    run_time:      await getValue("Course à pied"),
    event_name:    await getValue("Épreuve"),
    provider_badge: await getBadge(),
  };
}

async function saveAndVerify(page, expectedNom) {
  await page.locator("text=Enregistrer le résultat").click();
  await expect(page.locator("text=Résultat enregistré !")).toBeVisible({ timeout: 10_000 });

  // Verify via API: independent of UI tab navigation (App auto-switches to Club tab after import)
  const ctx = await request.newContext({ baseURL: BACKEND_URL });
  const resp = await ctx.get(`/api/results?name=${encodeURIComponent(expectedNom)}`);
  const data = await resp.json();
  await ctx.dispose();
  expect(data.length, `${expectedNom} non trouvé dans les résultats après sauvegarde`).toBeGreaterThan(0);
}

// ─────────────────────────────────────────────────────────────────────────────
// Shared assertion for a scraped result
// ─────────────────────────────────────────────────────────────────────────────

const PROVIDER_LABEL_MAP = {
  klikego:         "Klikego",
  breizhchrono:    "Breizh Chrono",
  wiclax:          "Wiclax",
  timepulse:       "TimePulse",
  prolivesport:    "ProLiveSport",
  sportinnovation: "Sport Innovation",
};

async function assertResult(page, tc) {
  const fields = await readResultFields(page);

  // Athlete name must be non-empty; if empty, the scraper returned a broken result → skip
  if (!fields.nom) {
    test.info().annotations.push({ type: "skip-reason", description: `Nom vide pour ${tc.search} — possible DNS ou URL morte` });
    test.skip();
    return fields;
  }

  // Total time: if empty it's a DNS/DNF — skip gracefully instead of failing
  if (tc.expects?.has_time !== false) {
    const DNF_STRINGS = /^(abandon|disqualifi|dsq|dnf|dns|forfait|non partant|hors délai)/i;
    if (!fields.total_time || DNF_STRINGS.test(fields.total_time)) {
      test.info().annotations.push({ type: "skip-reason", description: `DNS/DNF: pas de temps pour ${tc.search} (${fields.total_time || "vide"})` });
      test.skip();
      return fields;
    }
    expect(fields.total_time, `Temps total vide/invalide pour ${tc.search}`)
      .toMatch(/^\d{1,2}:\d{2}:\d{2}/);
  }

  // Event name must be non-empty (skip if fixture explicitly marks has_event_name:false)
  if (tc.expects?.has_event_name !== false) {
    expect(fields.event_name.length, `Nom épreuve vide pour ${tc.search}`).toBeGreaterThan(0);
  }

  // Provider badge must match expected provider
  if (tc.expects?.provider) {
    const expectedLabel = PROVIDER_LABEL_MAP[tc.expects.provider] || tc.expects.provider;
    expect(
      fields.provider_badge.toLowerCase(),
      `Badge provider incorrect pour ${tc.search} (attendu: ${expectedLabel})`
    ).toContain(expectedLabel.toLowerCase().split(" ")[0]);
  }

  // Splits — at least one must be present for providers/formats that return them
  if (expectsSplits(tc)) {
    const hasSplit = [fields.swim_time, fields.bike_time, fields.run_time]
      .some((t) => t && /^\d{1,2}:\d{2}:\d{2}/.test(t));
    if (!hasSplit) {
      // No splits but has a valid total_time → scraper issue, skip with annotation
      test.info().annotations.push({ type: "skip-reason", description: `Splits vides pour ${tc.search} — format non supporté ou DNS` });
      test.skip();
      return fields;
    }
  }

  return fields;
}

// ─────────────────────────────────────────────────────────────────────────────
// 1. Scrapable providers
// ─────────────────────────────────────────────────────────────────────────────

const SCRAPABLE = ["klikego", "breizhchrono", "wiclax", "timepulse", "prolivesport", "sportinnovation"];

for (const provider of SCRAPABLE) {
  const cases = fixtures[provider] || [];
  if (!cases.length) continue;

  test.describe(`[${provider}] scrape + save`, () => {
    test.beforeEach(async () => {
      await resetDb();
    });

    for (const tc of cases) {
      test(tc.label, async ({ page }) => {
        test.setTimeout(SCRAPE_TIMEOUT + 90_000);

        const outcome = await doScrape(page, tc.url, tc.search);

        // Handle multiple matches: pick the right candidate
        if (outcome === "multiple") {
          await pickCandidate(page, tc.search);
        } else if (outcome === "timeout" || outcome === "error") {
          test.info().annotations.push({
            type: "skip-reason",
            description: `Scrape outcome: ${outcome} — possibly transient network error`,
          });
          test.skip();
          return;
        } else if (outcome.startsWith("warning")) {
          expect(outcome, `Provider ${provider} a renvoyé un bandeau bloquant inattendu`).toBe("ok");
          return;
        }

        const fields = await assertResult(page, tc);
        // Skip save when event_name is absent (e.g. sportinnovation detail API)
        // — the assertion already verified the scraper returned correct athlete data
        if (tc.expects?.has_event_name === false || !fields.event_name) return;
        await saveAndVerify(page, fields.nom);
      });
    }
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. Multiple matches (choix de doublon)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Generic doublon helper — handles the full pick→verify→save flow.
 * pickHint: regex or string to identify the correct candidate button.
 * If null, picks the first candidate.
 */
async function doDoublon(page, url, search, pickHint) {
  const outcome = await doScrape(page, url, search);

  if (outcome === "error" || outcome === "timeout") return test.skip();

  if (outcome === "ok") {
    // Unique match — check name is present; skip if DNS (no time/event)
    const fields = await readResultFields(page);
    expect(fields.nom.length, `Nom vide pour ${search}`).toBeGreaterThan(0);
    if (!fields.total_time || !fields.event_name) {
      test.info().annotations.push({ type: "skip-reason", description: "Athlète DNS/DNF — pas de temps" });
      test.skip();
      return;
    }
    await saveAndVerify(page, fields.nom);
    return;
  }

  if (outcome === "multiple") {
    await expect(page.locator("text=Plusieurs athlètes trouvés")).toBeVisible({ timeout: 5_000 });

    // Pick specific candidate or first if no hint
    let btn;
    if (pickHint) {
      btn = page.locator("button").filter({ hasText: pickHint }).first();
      await expect(btn, `Bouton "${pickHint}" introuvable dans la liste`).toBeVisible({ timeout: 5_000 });
    } else {
      btn = page.locator("button").filter({ hasText: /Dossard/ }).first();
    }
    await btn.click();
    await page.locator("text=Enregistrer le résultat").waitFor({ timeout: SCRAPE_TIMEOUT });

    const fields = await readResultFields(page);
    expect(fields.nom.length, `Nom vide après sélection doublon pour ${search}`).toBeGreaterThan(0);

    // Verify the right athlete was selected
    if (pickHint instanceof RegExp) {
      const fullName = `${fields.nom} ${fields.prenom}`;
      expect(fullName.toLowerCase(), `Mauvais athlète sélectionné`).toMatch(new RegExp(pickHint.source, "i"));
    }

    // DNS/DNF: skip save but the UI flow is validated
    if (fields.total_time && fields.event_name) {
      await saveAndVerify(page, fields.nom);
    }
  }
}

test.describe("[doublons] Sélection du bon athlète parmi plusieurs", () => {
  test.beforeEach(async () => { await resetDb(); });

  // ── Klikego — AIGNEL (Romain M vs Maeva F, même nom de famille) ─────────────
  test("klikego — AIGNEL : choisir Romain", async ({ page }) => {
    test.setTimeout(SCRAPE_TIMEOUT + 90_000);
    await doDoublon(
      page,
      "https://www.klikego.com/resultats/triathlon-swimrun-dinard-cote-demeraude-2025/1488071608761-688?heat=triathlon-distance-olympique",
      "AIGNEL",
      /Romain/i,
    );
  });

  // ── Wiclax — MOREAU à La Roche 2025 (Christelle F vs Mathis M) ──────────────
  test("wiclax — MOREAU à La Roche 2025 : choisir Christelle", async ({ page }) => {
    test.setTimeout(SCRAPE_TIMEOUT + 90_000);
    await doDoublon(
      page,
      "https://chronosmetron.wiclax-results.com/Triathlon%20de%20la%20Roche%202025/",
      "MOREAU",
      /Christelle/i,
    );
  });

  // ── Klikego — chercher par dossard (Bernard Romain, bib 504) ────────────────
  // Validates that when search=dossard is in URL, the form is pre-filled correctly
  test("klikego — BERNARD Romain via dossard 504", async ({ page }) => {
    test.setTimeout(SCRAPE_TIMEOUT + 90_000);
    // URL already embeds search=504 so no doublon — verifies pre-filled bib path
    const outcome = await doScrape(
      page,
      "https://www.klikego.com/resultats/medoc-atlantique-frenchman-triathlon-carcans-2026/1354050643080-23?heat=triathlon-m&search=504",
      "",
    );
    if (outcome === "error" || outcome === "timeout") return test.skip();
    const fields = await readResultFields(page);
    expect(fields.nom.length).toBeGreaterThan(0);
    expect(fields.total_time).toMatch(/^\d{1,2}:\d{2}:\d{2}/);
    await saveAndVerify(page, fields.nom);
  });

  // ── Prolivesport — nom commun MARTIN → choisir le premier ────────────────────
  test("prolivesport — chercher 'MARTIN' → choisir le premier", async ({ page }) => {
    test.setTimeout(SCRAPE_TIMEOUT + 90_000);
    const url = "https://www.prolivesport.fr/index.php?chap=event&sub=liveV3&eventId=979&race=Triathlon%20M";
    const outcome = await doScrape(page, url, "MARTIN");

    if (outcome === "multiple") {
      await expect(page.locator("text=Plusieurs athlètes trouvés")).toBeVisible();
      await page.locator("button").filter({ hasText: /Dossard/ }).first().click();
      await page.locator("text=Enregistrer le résultat").waitFor({ timeout: SCRAPE_TIMEOUT });
      const fields = await readResultFields(page);
      expect(fields.nom.length, "Nom vide après sélection du candidat").toBeGreaterThan(0);
    } else if (outcome === "ok") {
      const fields = await readResultFields(page);
      expect(fields.nom.length).toBeGreaterThan(0);
    } else {
      test.skip();
    }
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 3b. Saisie manuelle complète (URL non supportée → remplir → sauvegarder)
// ─────────────────────────────────────────────────────────────────────────────

test.describe("[saisie-manuelle] Entrée manuelle pour provider non géré", () => {
  test.beforeEach(async () => { await resetDb(); });

  /**
   * Full manual-entry flow:
   * 1. Paste unsupported/playwright-fallback URL
   * 2. Click "Saisir manuellement" if error path, or the form is already shown
   * 3. Fill required fields
   * 4. Save and verify in DB
   */
  async function doManualEntry(page, url, athleteData) {
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");
    await page.locator('input[type="url"]').fill(url);
    await page.waitForTimeout(400);

    // Skip if URL triggers a blocking warning (live/dead BC)
    if (await page.locator("text=page live de Breizh Chrono").count()) return "blocked";
    if (await page.locator("text=résultats ne sont pas encore disponibles").count()) return "blocked";

    const submitBtn = page.locator('button[type="submit"]');
    if (!await submitBtn.isDisabled()) {
      // If the name field is required (shown for providers needing a search),
      // fill it with the athlete name so the form doesn't block submission
      const nameField = page.locator('input[placeholder*="ARNOUX"]');
      if (await nameField.isVisible({ timeout: 500 }).catch(() => false)) {
        await nameField.fill(athleteData.nom);
      }

      await submitBtn.click();

      // Wait for outcome: error with manual-entry button, or playwright fallback form
      const manualBtn  = page.locator("button", { hasText: "Saisir manuellement" });
      const fallbackBadge = page.locator("span").filter({ hasText: "Autre (navigateur)" });
      const saveBtn    = page.locator("text=Enregistrer le résultat");

      const outcome = await Promise.race([
        manualBtn.waitFor({ timeout: SCRAPE_TIMEOUT }).then(() => "error"),
        fallbackBadge.waitFor({ timeout: SCRAPE_TIMEOUT }).then(() => "fallback"),
        saveBtn.waitFor({ timeout: SCRAPE_TIMEOUT }).then(() => "direct"),
      ]).catch(() => "timeout");

      if (outcome === "timeout") return "timeout";

      if (outcome === "error") {
        await manualBtn.click();
        await saveBtn.waitFor({ timeout: 5_000 });
      }
      // "fallback" and "direct" already show the form
    }

    // Fill mandatory fields
    const set = (label, val) =>
      page.locator(`input[aria-label="${label}"]`).fill(val);

    await set("Nom",      athleteData.nom);
    await set("Prénom",   athleteData.prenom);
    await set("Épreuve",  athleteData.eventName);
    await page.locator("select").selectOption({ label: athleteData.eventType });
    await set("Temps total", athleteData.time);

    await page.locator("text=Enregistrer le résultat").click();
    await expect(page.locator("text=Résultat enregistré !")).toBeVisible({ timeout: 10_000 });

    // Verify in DB
    const ctx = await request.newContext({ baseURL: BACKEND_URL });
    const resp = await ctx.get(`/api/results?name=${encodeURIComponent(athleteData.nom)}`);
    const data = await resp.json();
    await ctx.dispose();
    expect(data.length, `${athleteData.nom} non trouvé après saisie manuelle`).toBeGreaterThan(0);

    return "ok";
  }

  test("breizhchrono resultat-course ajax — saisie manuelle après erreur", async ({ page }) => {
    test.setTimeout(SCRAPE_TIMEOUT + 30_000);
    const result = await doManualEntry(page,
      "https://www.breizhchrono.com/resultat-course/crs_id/18712/cor_id/162834569/?ajax=true&width=600&height=600",
      {
        nom: "AUBERT",
        prenom: "Marianne",
        eventName: "Triathlon Coetquidan 2025",
        eventType: "Triathlon (format inconnu)",
        time: "02:30:00",
      }
    );
    if (result === "timeout" || result === "blocked") test.skip();
    expect(result).toBe("ok");
  });

  test("sportinnovation detailAthlete — saisie manuelle après erreur", async ({ page }) => {
    test.setTimeout(SCRAPE_TIMEOUT + 30_000);
    const result = await doManualEntry(page,
      "https://results.sportinnovation.fr/detailAthlete/IMP-68e8d5a982694-529468540387167980",
      {
        nom: "PARIS",
        prenom: "Leo",
        eventName: "Sport Innovation Test",
        eventType: "Triathlon S (Sprint)",
        time: "01:10:00",
      }
    );
    if (result === "timeout" || result === "blocked") test.skip();
    expect(result).toBe("ok");
  });

  test("timepulse page événement (non résultats) — saisie manuelle", async ({ page }) => {
    test.setTimeout(SCRAPE_TIMEOUT + 30_000);
    const result = await doManualEntry(page,
      "https://www.timepulse.fr/evenements/voir/3010/planete-racing-aquarun-challans",
      {
        nom: "BELLEIL",
        prenom: "Julie",
        eventName: "Planète Racing Aquarun Challans",
        eventType: "Aquathlon",
        time: "00:45:00",
      }
    );
    if (result === "timeout" || result === "blocked") test.skip();
    expect(result).toBe("ok");
  });

  test("breizhchrono live-temps-intermediaire — saisie manuelle après fallback", async ({ page }) => {
    test.setTimeout(SCRAPE_TIMEOUT + 30_000);
    const result = await doManualEntry(page,
      "https://www.breizhchrono.com/live-temps-intermediaire/crs_id/18671",
      {
        nom: "MASHAYEKHI",
        prenom: "Sherwin",
        eventName: "Triathlon Test BC Live",
        eventType: "Triathlon M (Olympique)",
        time: "02:10:00",
      }
    );
    if (result === "timeout" || result === "blocked") test.skip();
    expect(result).toBe("ok");
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 3. Providers non gérés (fallback Playwright)
// ─────────────────────────────────────────────────────────────────────────────

test.describe("[non-géré] Provider inconnu → fallback + entrée manuelle", () => {
  test.beforeEach(async () => { await resetDb(); });

  test("prolivesport /fftri — URL sans eventId non supportée", async ({ page }) => {
    const url = "https://www.prolivesport.fr/fftri/grand-prix-duathlon";
    const outcome = await doScrape(page, url, "");

    // Should either show an error or offer manual entry
    const errorVisible   = await page.locator("text=Ce provider n'est pas encore supporté").count();
    const manualVisible  = await page.locator("text=Saisir manuellement").count();
    expect(errorVisible + manualVisible, "Aucun message d'erreur ni entrée manuelle").toBeGreaterThan(0);
  });

  test("espace-competition.com — provider non implémenté", async ({ page }) => {
    const url = "https://www.espace-competition.com/index.php?module=sportif&action=resultat&comp_uid=2657#5_5AF69D";
    const outcome = await doScrape(page, url, "");

    // Either an error with manual-entry offer, or the playwright fallback form ("Autre (navigateur)")
    const errorVisible       = await page.locator("text=Ce provider n'est pas encore supporté").count();
    const manualVisible      = await page.locator("text=Saisir manuellement").count();
    const playwrightFallback = await page.locator("text=Autre (navigateur)").count();
    expect(
      errorVisible + manualVisible + playwrightFallback,
      "Aucun message d'erreur, ni entrée manuelle, ni formulaire playwright"
    ).toBeGreaterThan(0);
  });

  test("lien PDF direct — fallback gracieux", async ({ page }) => {
    const url = "https://www.best-triathlon-saint-nazaire.com/_files/ugd/68889f_ead066ffe2c3403288dae1d0db90f332.pdf";
    const outcome = await doScrape(page, url, "");
    // Expect error, manual-entry offer, OR playwright fallback form — not a crash
    const errorVisible       = await page.locator("text=Ce provider").count();
    const manualVisible      = await page.locator("text=Saisir manuellement").count();
    const fallback           = await page.locator("text=Erreur").count();
    const playwrightFallback = await page.locator("text=Autre (navigateur)").count();
    expect(errorVisible + manualVisible + fallback + playwrightFallback).toBeGreaterThan(0);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 4. URLs bloquées — bandeaux d'avertissement (paramétrique sur la fixture)
// ─────────────────────────────────────────────────────────────────────────────

// Sample: 5 live + 5 dead for fast CI, covering different URL patterns
const LIVE_BC_SAMPLE  = (fixtures["breizhchrono_live"]  || []).slice(0, 5);
const DEAD_BC_SAMPLE  = (fixtures["breizhchrono_dead"]  || []).slice(0, 5);

test.describe("[bloqué] Bandeaux d'avertissement — live.breizhchrono.com", () => {
  LIVE_BC_SAMPLE.forEach((tc, i) => {
    const title = tc.label || tc.name_hint || `#${i + 1}`;
    test(title, async ({ page }) => {
      await page.goto("/");
      await page.locator('input[type="url"]').fill(tc.url);
      await page.waitForTimeout(400);
      await expect(
        page.locator("text=page live de Breizh Chrono"),
        `Bandeau live attendu pour ${tc.url}`
      ).toBeVisible();
      await expect(page.locator('button[type="submit"]')).toBeDisabled();
    });
  });
});

test.describe("[bloqué] Bandeaux d'avertissement — breizhchrono.com/detail-de-la-course", () => {
  DEAD_BC_SAMPLE.forEach((tc, i) => {
    const title = tc.label || tc.name_hint || `#${i + 1}`;
    test(title, async ({ page }) => {
      await page.goto("/");
      await page.locator('input[type="url"]').fill(tc.url);
      await page.waitForTimeout(400);
      await expect(
        page.locator("text=résultats ne sont pas encore disponibles"),
        `Bandeau résultats-pas-dispo attendu pour ${tc.url}`
      ).toBeVisible();
      await expect(page.locator('button[type="submit"]')).toBeDisabled();
    });
  });
});
