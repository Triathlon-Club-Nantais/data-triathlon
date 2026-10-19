# Accueil et club, suites de recette : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (chosen by the user). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** sélecteur de saison sur `/` et `/club` (#1639), bandeau de l'accueil en deux cartes (#1641), flèches des tuiles visibles (#1640), quatre animations CSS légères (#1642).

**Architecture:** les endpoints club gagnent un paramètre `seasons` optionnel (ajout seul) ; les pages `/` et `/club` lisent `?seasons=` comme `/mon-espace` et le passent à chaque appel. Le bandeau devient deux cartes ; tuiles et animations restent du CSS (`app/globals.css`) et des composants `components/home/`.

**Tech Stack:** FastAPI, SQLAlchemy 2, pytest ; Next.js 16 App Router, React Query, vitest + RTL, Tailwind, lucide-react.

**Spec:** les corps des issues #1639, #1641, #1640, #1642 (`gh issue view <n>`), plus les décisions de l'utilisateur du 19/10/2026 : sélecteur multi-saisons identique à `/mon-espace` sans option « toutes saisons » ; carte orange = dernière sortie, carte blanche = club, saison, chiffres et histogramme ; animations retenues : tuiles en cascade, barres qui poussent, reflet unique sur l'orange, pouls « Ce week-end ».

## Global Constraints

- Copie visible en français, vouvoiement, « épreuve » jamais « course » dans un libellé, « athlète ». Identifiants, tests, commits en anglais.
- Jamais de tiret pour ponctuer une phrase (copie et commentaires). Commentaires seulement pour une contrainte non évidente.
- Backend : `api → services → repositories`, seuls les repositories construisent des requêtes. `/api/v1` : ajouts seulement, défauts inchangés.
- Écrans publics : `components/tcn/`, jetons `--tcn-*`, 44 px au doigt, anneau de focus opaque `--tcn-orange`. Contraste texte 4,5:1, éléments d'interface 3:1.
- Animations : `transform` et `opacity` seulement, aucune en boucle continue, toutes coupées sous `prefers-reduced-motion: reduce`, contenu final présent dans le HTML serveur.
- Commits Conventional Commits, sans `Co-Authored-By`.

## Review Focus

- Plusieurs saisons cochées sur `/club` : tous les chiffres, podiums, effectif et répartition portent sur la même sélection (plus de rangée mi-saison mi-cumul). Test en Task 2.
- Saison passée sélectionnée sur `/` : la dernière sortie est la dernière de cette saison, jamais « Ce week-end » si elle date de plus de 7 jours. Test en Task 3.
- Saison sans aucune épreuve : `/` et `/club` affichent leur état vide sans erreur. Tests en Task 2 et 3.
- Dépliage « Voir les N podiums » de `/club` : la liste complète suit la même sélection que l'aperçu. Test en Task 2.
- Animations sous `prefers-reduced-motion` : rien ne bouge, rien n'est caché. Test en Task 6.

## Livraison (une PR par issue, empilées)

- `feat/1639-season-selector` (depuis `main`) : Tasks 1 à 3, PR vers `main`, `Closes #1639`.
- `feat/1641-banner-cards` (sur 1639) : Task 4, `Closes #1641`.
- `feat/1640-tile-arrows` (sur 1641) : Task 5, `Closes #1640`.
- `feat/1642-home-animations` (sur 1640) : Task 6, `Closes #1642`.

---

### Task 1: `seasons` on the club endpoints (#1639)

**Files:**
- Modify: `backend/app/repositories/athlete_repository.py` (`_club_roster_query` ~l.902, `club_roster` ~l.938, `club_composition` ~l.970), `backend/app/repositories/participation_repository.py` (`club_podiums` ~l.1258, `latest_club_event_date`), `backend/app/services/club_service.py` (`get_club_podiums`, `get_club_summary`), `backend/app/services/stats_service.py` (`get_last_outing`), `backend/app/api/v1/club.py`
- Test: `backend/tests/test_services/test_club_service.py`, `backend/tests/test_services/test_last_outing.py`, `backend/tests/test_api/test_club_api.py`

**Interfaces:**
- Produces: query param `seasons` (CSV of season start years, parsed with `app.core.season.parse_seasons`, same as `/stats`) on `GET /club/summary`, `GET /club/podiums`, `GET /club/last-outing`; absent = current behaviour (all seasons for summary/podiums, current season for last-outing).
- Produces: `get_club_summary(db, *, federal_only=False, podiums_preview=False, seasons: list[int] | None = None)`, `get_club_podiums(db, *, federal_only=False, seasons=None)`, `get_last_outing(db, *, federal_only=False, seasons: list[int] | None = None)`; repository functions take the same `seasons` keyword and filter with `participation_repository.season_clause(seasons)` on `Course.event_date`.
- `licensees` in the summary: computed for `max(seasons)` when given, else current season.
- `latest_club_event_date(db, *, seasons: list[int], federal_only=False)` (replaces the single `season`); `get_last_outing` uses `seasons or [current_season()]`.

- [ ] **Step 1: Write the failing tests**
  - `test_club_summary_restricts_roster_podiums_and_composition_to_seasons`: two TCN results, one in season 2025 (2026-05-10) with `rank_overall=1`, one in 2026 (2026-10-11) with `rank_overall=2`, different athletes ; `get_club_summary(db, seasons=[2026])` has roster of 1 (the 2026 athlete), `podiums_totals.scratch == 1`, composition counts 1 athlete ; without `seasons`, 2 of each.
  - `test_club_summary_licensees_follow_the_latest_selected_season`: with `seasons=[2025]`, `licensees.season == 2025` when a 2025 licensee exists.
  - `test_club_podiums_restricted_to_seasons`: same fixture, `get_club_podiums(db, seasons=[2025]).scratch` has 1 entry.
  - In `test_last_outing.py`: `test_last_outing_in_a_past_season` (clock frozen 2026-10-15, races 2026-05-10 and 2026-10-11 ; `seasons=[2025]` gives `end_date == date(2026, 5, 10)`), `test_last_outing_across_several_seasons_takes_the_latest` (`seasons=[2025, 2026]` gives 2026-10-11).
  - API: `test_club_summary_accepts_seasons` and `test_last_outing_accepts_seasons` (`?seasons=2025` changes the JSON as above).
- [ ] **Step 2: Run them, expect FAIL** (`uv run pytest tests/test_services/test_club_service.py tests/test_services/test_last_outing.py tests/test_api/test_club_api.py -n 0 -q`, unexpected keyword `seasons`).
- [ ] **Step 3: Implement** the signatures above; routers parse `seasons: str | None = Query(None, description=...)` with `parse_seasons` exactly like `api/v1/stats.py` does (read it and copy its validation, including bounds).
- [ ] **Step 4: Run** the three files, then `uv run pytest -m "not integration" -q` and `uv run ruff check .`: PASS, no existing test changed.
- [ ] **Step 5: Commit** `feat(club): accept a season selection on the club summary, podiums and last outing (#1639)`.

### Task 2: season selector on `/club` (#1639)

**Files:**
- Modify: `frontend/lib/api/server.ts` (`getClubSummary`, `getClubLastOuting`), `frontend/lib/api/client.ts:292` (`getClubPodiums`), `frontend/app/(public_restricted)/club/page.tsx`, `frontend/components/club/ClubDashboard.tsx`, `frontend/components/club/PodiumsList.tsx:62`
- Test: `frontend/app/(public_restricted)/club/page.test.tsx`, `frontend/components/club/ClubDashboard.test.tsx`, `frontend/components/club/PodiumsList.test.tsx`

**Interfaces:**
- Consumes: Task 1 query params.
- Produces: `getClubSummary(opts: { federal_only?: boolean; podiums?: "preview"; seasons?: number[] })`, `getClubLastOuting(opts: { federal_only?: boolean; seasons?: number[] })` (server), `getClubPodiums(opts: { federal_only?: boolean; seasons?: number[] })` (client). `toQuery` already serialises arrays the way `getStats` does: check and reuse.
- `ClubDashboard` loses `resultsTotal`; it receives a single `stats` scoped to the selection and a `seasons: number[]` prop for the KPI hint (`seasonSelectionLabel(seasons)`).

- [ ] **Step 1: Failing tests**
  - page: `?seasons=2025` calls `getStats`, `getClubSummary` and the season best times with `seasons: [2025]` (best times: `season: 2025`, the max of the selection) ; no `?seasons` → `[currentSeason()]` ; renders `SeasonSelector` (assert the « Saisons » control is present, mocking `listSeasons` like `mon-espace/page.test.tsx` does).
  - page: only **one** `getStats` call (the all-time call is gone).
  - ClubDashboard: the four KPI read the same `stats`, « Résultats » hint is `seasonSelectionLabel(seasons)`.
  - PodiumsList: expanding calls `getClubPodiums` with the `seasons` from `?seasons=` (default current season).
  - page: a season with `stats.total === 0` renders the existing empty state.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** Page reads `parseSeasonsParam(sp.seasons)` with fallback `[currentSeason()]` (pattern of `mon-espace/page.tsx`), fetches `listSeasons({ scope: SCOPE_CLUB, federal_only })` and renders `SeasonSelector` + `SeasonTags` in the `PageHeader` actions next to `RankTypeToggle` and `DisciplineToggle`. Best times: the « saison » tab uses `Math.max(...selected)`.
- [ ] **Step 4: Run** `npx vitest run app/(public_restricted)/club components/club`, then full `npx vitest run`, `npm run lint`: PASS.
- [ ] **Step 5: Commit** `feat(club): select the seasons shown on the club page (#1639)`.

### Task 3: season selector on `/` (#1639)

**Files:**
- Modify: `frontend/app/(public_restricted)/(accueil)/page.tsx`, `frontend/components/home/BandeauDirect.tsx`, `frontend/components/home/TuilesEspaces.tsx`
- Test: `frontend/app/(public_restricted)/(accueil)/page.test.tsx`, `frontend/components/home/BandeauDirect.test.tsx`, `frontend/components/home/TuilesEspaces.test.tsx`

**Interfaces:**
- Consumes: `getClubLastOuting({ federal_only, seasons })` (Task 2).
- Produces: `BandeauDirect` props become `{ sortie, stats, seasons: number[], today }` (`season` removed): the h1 reads `${CLUB_NAME} · ${seasonSelectionLabel(seasons)}`, the histogram plots `moisDeSaison(stats.by_month, Math.max(...seasons))` with caption « Résultats par mois · Saison X — Y » when several seasons are selected.
- `TuilesEspaces` gains `query: string` (the current `?seasons=&sports=` query, possibly empty) appended to the Résultats, Club and Mon espace hrefs.

- [ ] **Step 1: Failing tests**
  - page: `?seasons=2025` passes `seasons: [2025]` to `getStats` and `getClubLastOuting`; renders the « Saisons » control.
  - BandeauDirect: several seasons → h1 contains « 2 saisons sélectionnées » and the histogram caption names the latest season; with a 2025 outing dated 2026-05-10 and today 2026-10-15, the title is « Dernière sortie · 10 mai ».
  - TuilesEspaces: with `query="?seasons=2025"`, the Club link href is `/club?seasons=2025`, Mon espace `/mon-espace?seasons=2025`.
  - page: a season with no result renders the banner fallback « Pas encore d'épreuve cette saison » without error.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** Selector placement: a toolbar row above the banner, right-aligned on `lg`, wrapping on mobile (reuse the `FieldLabel` + `SeasonSelector` + `SeasonTags` block of `mon-espace/page.tsx`).
- [ ] **Step 4: Run** focused then full `npx vitest run`, `npm run lint`, `npx tsc --noEmit -p .`: PASS.
- [ ] **Step 5: Commit** `feat(home): select the seasons shown on the home page (#1639)`.

### Task 4: banner in two cards (#1641)

**Files:**
- Modify: `frontend/components/home/BandeauDirect.tsx`
- Test: `frontend/components/home/BandeauDirect.test.tsx`

**Interfaces:**
- Consumes: Task 3 props (unchanged signature).
- Produces: two regions inside the component: `<section aria-label="Dernière sortie">` (orange card) and `<section aria-labelledby="bandeau-saison-titre">` (white card holding the `h1`). Class hooks for Task 6: `tcn-carte-sortie` on the orange card, `tcn-barre` on each histogram bar, `tcn-pouls` on the « Ce week-end » dot.

- [ ] **Step 1: Failing tests:** two regions exist; the outing region contains « Ce week-end » and « 48 TCN »; the season region contains the h1, the three figures and the histogram (`role="img"`); fallback « Pas encore d'épreuve cette saison » sits in the orange card; histogram bars in the white card use `var(--tcn-orange)`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** Grid `md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]`, stacked below `md`, `minWidth: 0` on both cards. Orange card: `--tcn-orange-grad`, white text, the outing block as today. White card: `tcn/Card`, ink text, h1 as an eyebrow in `--tcn-text-muted` (check 4.5:1), the three figures in `--tcn-ink` (Anton), bars `var(--tcn-orange)` with empty months `var(--tcn-grey-300)`.
- [ ] **Step 4: Run** `npx vitest run components/home "app/(public_restricted)/(accueil)"`, `npm run lint`: PASS.
- [ ] **Step 5: Commit** `feat(home): split the live banner into an outing card and a season card (#1641)`.

### Task 5: visible tile arrows (#1640)

**Files:**
- Modify: `frontend/components/home/TuilesEspaces.tsx`, `frontend/app/globals.css` (`.tcn-tuile-espace` block ~l.640)
- Test: `frontend/components/home/TuilesEspaces.test.tsx`

**Interfaces:**
- Produces: in each tile, `<span aria-hidden="true" className="tcn-tuile-fleche">` wrapping lucide `ArrowRight` (`size={18}`); class hook `tcn-tuile-fleche` for Task 6.

- [ ] **Step 1: Failing tests:** every tile link contains an `aria-hidden` `.tcn-tuile-fleche` with an `svg`; accessible names of the five links unchanged (assert the existing names).
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** Pastille 32 px ronde, fond `--tcn-orange-12`, icône `--tcn-orange-deeper`; on `.tcn-tuile-espace:hover` and `:focus-visible`: fond `--tcn-orange`, icône blanche, `transform: translateX(3px)` (transition `var(--tcn-dur-fast)`), no transform under reduced motion. Remove the old `→` text arrow.
- [ ] **Step 4: Run** focused + `npm run lint`: PASS.
- [ ] **Step 5: Commit** `fix(home): make the space tile arrows clearly visible (#1640)`.

### Task 6: home animations (#1642)

**Files:**
- Modify: `frontend/app/globals.css`, `frontend/components/home/BandeauDirect.tsx`, `frontend/components/home/TuilesEspaces.tsx`, `frontend/lib/home.ts`
- Test: `frontend/components/home/BandeauDirect.test.tsx`, `frontend/components/home/TuilesEspaces.test.tsx`, `frontend/lib/home.test.ts`, `frontend/app/globals.test.ts`

**Interfaces:**
- Consumes: class hooks from Tasks 4 and 5.
- Produces: `estToutRecent(endDate: string, today: Date): boolean` in `lib/home.ts` (true when the outing ended 0 to 2 days ago); the pulse dot renders only when it is true.

- [ ] **Step 1: Failing tests**
  - `lib/home.test.ts`: `estToutRecent("2026-10-11", new Date("2026-10-13T12:00:00"))` true, with 2026-10-14 false.
  - BandeauDirect: `.tcn-pouls` present for an outing 1 day old, absent for 5 days old; each bar has `tcn-barre` and an inline `--i` index (`style` contains `--i:`).
  - TuilesEspaces: each tile has `tcn-tuile-entree` and an inline `--i` index in order.
  - `globals.test.ts` (read how it parses `globals.css`): every new `@keyframes` (`tcn-entree`, `tcn-pousse`, `tcn-reflet`, `tcn-pouls`) is neutralised inside a `@media (prefers-reduced-motion: reduce)` block (`animation: none`).
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** in `globals.css`:
  - `tcn-entree`: tiles fade in from `opacity: 0; transform: translateY(8px)`, 360 ms ease-out, `animation-delay: calc(var(--i) * 50ms)`, `animation-fill-mode: both`.
  - `tcn-pousse`: bars from `transform: scaleY(0)` (`transform-origin: bottom`), 500 ms, delay `calc(var(--i) * 30ms)`.
  - `tcn-reflet`: a `::after` diagonal white gradient (`opacity` ≤ 0.25) crossing `.tcn-carte-sortie` once, 1.2 s, 300 ms delay, `pointer-events: none`, card `overflow: hidden; position: relative`.
  - `tcn-pouls`: an 8 px white dot whose ring scales 1 → 2.2 and fades, 1.6 s, **3 iterations** then stops.
  - One `@media (prefers-reduced-motion: reduce)` block setting `animation: none` on the four selectors.
- [ ] **Step 4: Run** `npx vitest run components/home lib app/globals.test.ts`, full `npx vitest run`, `npm run lint`, `npm run build`: PASS.
- [ ] **Step 5: Commit** `feat(home): add light entrance, bar, shine and pulse animations to the home page (#1642)`.

## End

- Code review per task (subagent-driven), final whole-branch review across the four branches, then `ui-ux-review` on the top branch, fixes, PRs ready, review requested. Merge stays with the user.
