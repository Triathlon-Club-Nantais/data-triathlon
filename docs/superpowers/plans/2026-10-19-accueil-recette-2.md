# Accueil et Mon espace, deuxième recette : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (chosen by the user). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** retirer le type de rang de `/mon-espace` (#1656), déplacer « Dernières épreuves » sur l'accueil (#1661), rendre l'histogramme lisible et comparatif (#1658), faire traverser le reflet sur toute la carte orange (#1659).

**Architecture:** changements frontend seulement : `MaSaison`, pages `/` et `/mon-espace`, `BandeauDirect` + `lib/home.ts`, `app/globals.css`.

**Tech Stack:** Next.js 16 App Router, React, vitest + RTL, Tailwind, CSS.

**Spec:** corps des issues #1656, #1658, #1659, #1661 (`gh issue view <n>`) et décisions de l'utilisateur du 19/10/2026 : reflet derrière le texte (contenu au premier plan, contraste transitoire accepté) ; « Dernières épreuves » sous les tuiles ; plusieurs saisons = barres côte à côte, 3 saisons au plus.

## Global Constraints

- Copie visible en français, vouvoiement, « épreuve » jamais « course » dans un libellé. Identifiants, tests, commits en anglais. Jamais de tiret pour ponctuer une phrase.
- Écrans publics : `components/tcn/`, jetons `--tcn-*`, 44 px au doigt, focus opaque `--tcn-orange`. Texte 4,5:1, éléments graphiques 3:1.
- Animations : `transform`/`opacity`, coupées sous `prefers-reduced-motion`, invisibles au repos quand décoratives.
- Commits Conventional Commits, sans `Co-Authored-By`.

## Review Focus

- Sélection de 4 saisons ou plus : l'histogramme montre les 3 plus récentes et le dit. Test en Task 3.
- Mois sans résultat dans une saison et pas dans l'autre : barres vides distinguables, pas de décalage d'axe. Test en Task 3.
- `?rank=` resté dans une URL de `/mon-espace` : sans effet, aucun contrôle ni libellé. Test en Task 1.
- Accueil avec une saison sans épreuve : « Dernières épreuves » affiche son état vide existant. Test en Task 2.

## Livraison (une PR par issue, empilées)

`feat/1656-mon-espace-rank` (depuis `main`, Task 1) → `feat/1661-latest-races-home` (Task 2) → `feat/1658-histogram` (Task 3) → `feat/1659-shine` (Task 4).

---

### Task 1: no rank type on `/mon-espace` (#1656)

**Files:** Modify `frontend/components/dashboard/MaSaison.tsx` (~l.138 `mode`, ~l.196-197, ~l.335-355 `avecRang` + `RankTypeToggle`); Test `frontend/components/dashboard/MaSaison.test.tsx`, `frontend/app/(public_restricted)/mon-espace/page.test.tsx`.

**Interfaces:** `MaSaison` no longer reads `RANK_PARAM`; podiums counted with `compteMaSaison(participations, "all")`; the `avecRang` prop (or equivalent) and the `RankTypeToggle` import disappear.

- [ ] Step 1: failing tests: no « Type de rang » text and no rank toggle buttons (Général / Catégorie / Genre / Tous) in `MaSaison`; with `?rank=scratch` in the URL, the podium count equals the `all` count (fixture: one participation with `rank_category=1`, `rank_overall=40` → 1 podium); the band's podium label uses the `all` wording of `LIBELLE_RANG_BANDE` (read it; if it shows a mode name, replace it by « toutes catégories confondues »).
- [ ] Step 2: run `npx vitest run components/dashboard "app/(public_restricted)/mon-espace"`, expect FAIL.
- [ ] Step 3: implement; delete now-dead code (constant entries, imports) used only by the removed toggle; keep `RankTypeToggle` itself (still used by `/club`).
- [ ] Step 4: focused tests, full `npx vitest run`, `npm run lint`: PASS.
- [ ] Step 5: commit `feat(mon-espace): drop the rank type toggle and count podiums across all ranks (#1656)`.

### Task 2: « Dernières épreuves » on the home page (#1661)

**Files:** Modify `frontend/app/(public_restricted)/(accueil)/page.tsx`, `frontend/app/(public_restricted)/(accueil)/loading.tsx`, `frontend/app/(public_restricted)/mon-espace/page.tsx` (~l.43 `listEvents`, ~l.107 `RecentCourses`); Test the three matching test files.

**Interfaces:** home calls `listEvents({ scope: SCOPE_CLUB, federal_only, seasons, page_size: 6 })` once; `sortEventsByDateDesc(items)` feeds both `RecentCourses events={...}` (placed **after** `TuilesEspaces`) and the Résultats tile (`[0]`). `RecentCourses` component unchanged.

- [ ] Step 1: failing tests: home renders the « Dernières épreuves » heading after the space tiles (compare DOM order), `listEvents` called once with `page_size: 6` and the selected `seasons`; the Résultats tile still names the most recent event; `/mon-espace` no longer renders « Dernières épreuves » nor calls `listEvents` if nothing else uses it; home with an empty season shows `RecentCourses`' existing empty state; loading skeleton has one more block for the list.
- [ ] Step 2: run, expect FAIL.
- [ ] Step 3: implement; spacing between tiles and list consistent with the page (`mt-6`).
- [ ] Step 4: focused tests, full `npx vitest run`, `npm run lint`, `npx tsc --noEmit -p .`: PASS.
- [ ] Step 5: commit `feat(home): move the club's latest races from /mon-espace to the home page (#1661)`.

### Task 3: readable and comparative histogram (#1658)

**Files:** Modify `frontend/lib/home.ts`, `frontend/components/home/BandeauDirect.tsx` (`Histogramme`); Test `frontend/lib/home.test.ts`, `frontend/components/home/BandeauDirect.test.tsx`.

**Interfaces:**
- `moisComparesParSaison(byMonth: Record<string, number>, seasons: number[]): { saisons: number[]; tronque: boolean; mois: { index: number; libelle: string; valeurs: number[] }[] }` in `lib/home.ts`: `saisons` = the 3 most recent selected seasons, oldest first; `tronque` = more than 3 were selected; `mois` = 12 entries September → August, `valeurs[k]` = results of `saisons[k]` that month (0 when absent). Reuse `moisDeSaison` per season.
- Series colours, oldest → most recent: `var(--tcn-text-faint)`, `var(--tcn-ink)`, `var(--tcn-orange)` (all ≥ 3:1 on white; check and state the ratios). One season = orange only, as today.

- [ ] Step 1: failing tests:
  - `lib/home.test.ts`: `moisComparesParSaison({"2025-09": 3, "2026-09": 5, "2026-10": 2}, [2025, 2026])` → `saisons [2025, 2026]`, `mois[0].valeurs [3, 5]`, `mois[1].valeurs [0, 2]`, `tronque false`; with `[2022, 2023, 2024, 2025]` → `saisons [2023, 2024, 2025]`, `tronque true`.
  - BandeauDirect: one season → 12 month labels visible under the bars (« sept. » … « août », text, `aria-hidden` like the bars), each bar has a `title` with « sept. : 3 » style value; two seasons → 24 bars, a legend naming both seasons (`seasonLabel`), the `role="img"` label summarises each season; four seasons → a note « 3 saisons les plus récentes ».
- [ ] Step 2: run, expect FAIL.
- [ ] Step 3: implement. Month labels: abbreviations at 10-11 px under each group, `--tcn-text-muted`; under `sm` show only the first letter (S, O, N…) to fit 360 px. Groups: bars side by side inside each month slot, small gap between groups. Keep `tcn-barre` and `--i` (index by group) so the grow animation still runs.
- [ ] Step 4: focused tests, full `npx vitest run`, `npm run lint`: PASS.
- [ ] Step 5: commit `fix(home): label the monthly histogram and compare several selected seasons (#1658)`.

### Task 4: shine across the whole orange card (#1659)

**Files:** Modify `frontend/app/globals.css` (`.tcn-carte-sortie::after` ~l.955), `frontend/components/home/BandeauDirect.tsx` (orange card content); Test `frontend/app/globals.test.ts`, `frontend/components/home/BandeauDirect.test.tsx`.

- [ ] Step 1: failing tests: `globals.test.ts` asserts the `::after` covers the full height (`top: 0` or `inset: 0`, no `top: 40%`) and keeps base `opacity: 0`; BandeauDirect asserts the orange card's content sits in a wrapper with class `tcn-carte-sortie-contenu`.
- [ ] Step 2: run, expect FAIL.
- [ ] Step 3: implement: `::after` full height; content wrapper `position: relative; z-index: 1` (CSS class `tcn-carte-sortie-contenu`) so the text stays above the shine; reduced-motion and rest invisibility unchanged.
- [ ] Step 4: focused tests, full `npx vitest run`, `npm run lint`, `npm run build`: PASS.
- [ ] Step 5: commit `fix(home): let the shine cross the whole orange card behind its text (#1659)`.

## End

Final whole-branch review, then `ui-ux-review`, fixes, stacked PRs; merge by the user (squash of the top PR, as for the previous stack).
