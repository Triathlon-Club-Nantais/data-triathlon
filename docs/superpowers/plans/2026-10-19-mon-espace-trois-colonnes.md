# Carte orange et Mon espace en trois colonnes : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (chosen by the user). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** remplir la carte orange de l'accueil avec les épreuves de la sortie (#1660), puis refondre `/mon-espace` en version personnelle et plus riche de la fiche athlète, en trois colonnes (#1695 à #1701).

**Architecture:** l'accueil réutilise `/club/last-outing` enrichi d'un champ `courses`. Mon espace lit l'athlète **rattaché au compte** (`useHydratedSession().data.athlete`), réutilise les données publiques de `GET /athletes/{id}` (participations, challenges) et les composants de la fiche athlète, et n'ajoute des endpoints que pour ce qui n'existe pas (mes actions de bénévolat, médiane des splits du club, coéquipiers de course).

**Tech Stack:** FastAPI, SQLAlchemy 2, pytest ; Next.js 16 App Router, React Query, vitest + RTL, Tailwind, SVG maison (`components/charts/`).

**Spec:** issue #1660 (corps réécrit le 19/10/2026) et `docs/superpowers/specs/2026-10-19-mon-espace-trois-colonnes-design.md` (sections et « Arbitrages après relecture »). Les corps des issues #1695 à #1701 renvoient aux sections du design.

## Global Constraints

- Copie visible en français, vouvoiement, « épreuve » jamais « course » dans un libellé, « athlète ». Identifiants, tests, commits en anglais. Jamais de tiret pour ponctuer une phrase.
- Backend : `api → services → repositories`, seuls les repositories construisent des requêtes ; `/api/v1` : ajouts seulement, défauts inchangés ; un service n'importe pas de symbole `_privé` d'un autre service.
- Écrans publics : `components/tcn/`, jetons `--tcn-*`, 44 px, focus opaque `--tcn-orange` (anneau clair opaque sur fond orange), texte 4,5:1, graphiques 3:1 avec résumé accessible, animations coupées sous `prefers-reduced-motion`.
- Session lue côté client par `useHydratedSession` (règle #1090) ; Mon espace ne lit plus `useSelectedAthlete`.
- Données privées (objectifs, demandes, déclarations, actions de bénévolat) servies seulement au compte rattaché, par des routes `/auth/me/*` authentifiées.
- Appartenance au club par les critères existants (`counts_for_tcn`, `tcn_clause`), jamais une constante nouvelle (#1686).
- Commits Conventional Commits, sans `Co-Authored-By`.

## Review Focus

- Compte connecté **non** rattaché, ou visiteur anonyme, sur `/mon-espace` : invitation, aucune donnée d'un autre athlète, aucun appel `/auth/me/*` en échec visible. Test en Task 2.
- Membre rattaché sans aucune épreuve dans la sélection : chaque onglet et encart a un état vide explicite, pas de graphique vide muet. Tests dans chaque task.
- Plusieurs saisons sélectionnées : pas d'écarts « vs saison précédente », graphiques cohérents avec la sélection. Tests en Tasks 2 et 5.
- Coéquipier ayant fait opposition : jamais listé. Test en Task 8.
- Épreuve non fiable (`is_reliable === false`) : exclue des ratios et des records, signalée dans le résumé accessible. Tests en Tasks 4 et 5.

## Livraison (une branche par issue, empilées depuis `docs/mon-espace-trois-colonnes`)

`feat/1660-outing-races` (T1) → `feat/1695-mon-espace-layout` (T2) → `feat/1696-mon-espace-tabs` (T3) → `feat/1697-records-tab` (T4) → `feat/1698-progression-tab` (T5) → `feat/1699-disciplines-tab` (T6) → `feat/1700-right-column` (T7) → `feat/1701-teammates-map` (T8). Fusion finale par la PR du haut vers `main` (squash), qui ferme toutes les issues.

---

### Task 1: races of the last outing in the orange card (#1660)

**Files:** `backend/app/repositories/participation_repository.py`, `backend/app/services/stats_service.py` (`get_last_outing`), `backend/app/schemas/club.py` (`ClubLastOuting`), `frontend/lib/types.ts`, `frontend/components/home/BandeauDirect.tsx`, `frontend/app/(public_restricted)/(accueil)/page.tsx` (query for the « et N autres » link); tests `backend/tests/test_services/test_last_outing.py`, `backend/tests/test_api/test_club_api.py`, `frontend/components/home/BandeauDirect.test.tsx`.

**Interfaces:**
- Repository: `club_outing_courses(db, *, seasons, federal_only, dates) -> list[tuple[int, str, str, int, list[tuple]]]` or equivalent returning per course `(id, name, event_type, tcn, rank rows)`; the service computes `podiums` per course with `_rank_counters(rows)["all"]["podiums"]`.
- `ClubLastOuting.courses: list[ClubOutingCourse]` with `ClubOutingCourse{id: int, name: str, event_type: str, tcn: int, podiums: int}`, sorted by `tcn` desc then name; TS mirror `courses: { id; name; event_type; tcn; podiums }[]`.
- `BandeauDirect` gains `resultatsHref: string` (built by the page from `?seasons=` / `?sports=`).

- [ ] Step 1: failing tests: backend: outing of 3 courses (36/7/5 TCN, podiums 5/2/1) gives `courses` in that order with those counts; a course outside the window or without TCN absent; `federal_only` and `seasons` respected; API JSON shape. Front: desktop shows 3 rows (format pill text, name, « 36 », podium icon with accessible name « 5 podiums »), each row a link to `/courses/{id}`; with 5 courses « et 2 autres épreuves → » links to `resultatsHref`; mobile hides the podium count (class `hidden md:inline` or equivalent, assert the class) and shows 2 rows (assert `md:hidden`/`hidden md:flex` on the 3rd row); fallback without outing unchanged.
- [ ] Step 2: run, expect FAIL.
- [ ] Step 3: implement (rows inside `tcn-carte-sortie-contenu`; row min-height 44 px; focus ring opaque light on orange; format pill white with `--tcn-orange-deeper` text; `lucide-react` `Medal` icon).
- [ ] Step 4: backend focused + full unit suite + ruff; frontend focused + full vitest + lint.
- [ ] Step 5: commit `feat(home): list the last outing's races in the orange card (#1660)`.

### Task 2: three-column layout, linked-account access and « Mes chiffres » (#1695)

**Files:** `frontend/app/(public_restricted)/mon-espace/page.tsx` + `loading.tsx`, new `frontend/components/mon-espace/` (`MonEspace.tsx` client shell, `MesChiffres.tsx`, `InvitationMonEspace.tsx`), `frontend/lib/mon-espace.ts` (pure helpers); tests alongside.

**Interfaces:**
- Page (server) keeps header (title « Mon espace », `SeasonSelector`, `SeasonTags`, `DisciplineToggle`) and renders `<MonEspace seasons={number[]} federalOnly={boolean} />` (client).
- `MonEspace`: reads `useHydratedSession()`; pending → skeleton; no `data.athlete` → `InvitationMonEspace` (anonymous: « Se connecter » ; logged-in not linked: link to the claim flow used by `InvitationAthlete`/athlete page); linked → loads `apiClient.getAthlete(athlete.id, { seasons, federal_only })` and the same for the previous-season-to-date window, renders the 3-column grid `lg:grid-cols-[minmax(0,1fr)_320px]` (navigation is the app rail, already left) with slots `centre` and `droite` (exported layout so later tasks add tabs and cards).
- `lib/mon-espace.ts`: `chiffresSaison(participations: Participation[]): { epreuves: number; podiums: number; km: number; tempsSecondes: number; meilleurRatio: number | null }` (podiums via `compteMaSaison(..., "all")`, km from `course.distance_km`, time from `total_time` via existing duration parser, ratio via `rankRatio`, best = smallest ratio), `fenetreSaisonPrecedente(season: number, today: Date): { start: string; end: string }` (same date one year earlier, bounded to that season), `ecart(a: number, b: number): number`.
- `MesChiffres({ courant, precedent | null, seasons })`: five figures, deltas only when `precedent` given; link « Récap de la saison passée » (`/mon-espace/recap`).
- `MaSaison` and `InvitationAthlete` are removed from `/mon-espace` (delete the components if no other user remains; grep first). `SeasonGoals` stays rendered in the centre column until Task 3 moves it into a tab.

- [ ] Step 1: failing tests: `lib/mon-espace.test.ts` (chiffres on a fixture of 3 participations incl. one unreliable course and one relay; window for season 2026 and today 2026-10-15 → 2025-09-01..2025-10-15); `MonEspace` three access cases (anonymous, logged-in not linked, linked) with mocked session and API; `MesChiffres` with and without deltas; page renders header and shell; loading skeleton matches (header + figures row + two columns).
- [ ] Step 2: run, expect FAIL.
- [ ] Step 3: implement. The previous-season call uses the participation endpoint filter that exists (`seasons` = previous season) and filters client-side to the window (`event_date <= window.end`); if `getAthlete` has no date filter, filtering client-side is the rule.
- [ ] Step 4: full vitest, lint, tsc.
- [ ] Step 5: commit `feat(mon-espace): three-column layout, linked-account access and my figures (#1695)`.

### Task 3: tabs with my races, challenges, CSV, volunteering and goals (#1696)

**Files:** `frontend/components/mon-espace/OngletsMonEspace.tsx`, reuse `athletes/[id]/EventsTable.tsx` (move to `components/athletes/` if it must be shared, update imports), `components/challenges/AthleteChallenges.tsx`, `components/dashboard/SeasonGoals.tsx`; backend new self route for validated volunteer actions: `GET /auth/me/volunteer-actions` in `backend/app/api/v1/auth.py` (service/repository reuse of the admin validated list, scoped to the linked athlete, 401/404 like the other `/auth/me` routes); `frontend/lib/api/client.ts`, `frontend/lib/queries/auth.ts` (`useMyVolunteerActions(enabled)`); tests.

**Interfaces:**
- `OngletsMonEspace({ athleteId, participations, challenges, seasons, federalOnly })` using `components/ui/tabs`; tab value in `?onglet=` (`epreuves`, `benevolat`, `objectifs`; later tasks add `progression`, `records`, `disciplines` before them). Default tab: the first available.
- Épreuves tab: `EventsTable` + CSV link (already inside) + `AthleteChallenges` below.
- Bénévolat tab: list of my validated actions (date, label, credits) from `useMyVolunteerActions`; empty state; link to `/benevolat` to declare.
- Objectifs tab: `SeasonGoals` moved here (removed from the centre column).

- [ ] Step 1: failing tests: backend: `/auth/me/volunteer-actions` returns only the linked athlete's validated actions, 401 anonymous, empty list for unlinked or none; frontend: tabs present in order, `?onglet=benevolat` selects it, arrow-key navigation (ui/tabs already supports it: assert `aria-selected` after ArrowRight), each tab content and empty state.
- [ ] Step 2: run, expect FAIL.
- [ ] Step 3: implement.
- [ ] Step 4: backend focused + full + ruff; frontend full + lint + tsc.
- [ ] Step 5: commit `feat(mon-espace): tabs with my races, challenges, export, volunteering and goals (#1696)`.

### Task 4: records tab (#1697)

**Files:** `frontend/lib/utils/best-times.ts` (reuse; add a pure helper if needed), `frontend/components/mon-espace/OngletRecords.tsx`; tests.

**Interfaces:**
- `recordsPersonnels(selection: Participation[], carriere: Participation[]): { format: string; discipline: string; meilleur: { temps: string; participation: Participation }; record: { temps: string; participation: Participation }; badge: "record" | "premiere" | null }[]` in `lib/mon-espace.ts`, built on `bestTimes()`; `carriere` = all seasons (one more `getAthlete(id, { federal_only })` call without `seasons`, cached).
- Tab inserted before Épreuves.

- [ ] Step 1: failing tests: helper (record beaten in selection → `record`; first ever result on a format → `premiere`; relay and unreliable excluded); component rows, badges with text (not colour only), link to the course, empty state.
- [ ] Step 2: run, expect FAIL. Step 3: implement. Step 4: full vitest, lint. Step 5: commit `feat(mon-espace): records tab with personal bests and badges (#1697)`.

### Task 5: progression tab (#1698)

**Files:** `frontend/components/mon-espace/OngletProgression.tsx`, reuse `components/charts/ProgressionChart.tsx` (add an optional `comparaison?: ProgressionPoint[]` drawn dashed, if absent), `lib/utils/ranking.ts` (`progressionSeries`), histogram: extract the home histogram rendering (`BandeauDirect` `Histogramme`) into `components/charts/HistogrammeMois.tsx` reused by both; tests.

**Interfaces:**
- `OngletProgression({ courant: Participation[], precedent: Participation[] | null, seasons })`: curve of `progressionSeries(courant)` with the previous season dashed; « Mes épreuves par mois » via `HistogrammeMois` fed by a `byMonth` computed from my participations.
- `HistogrammeMois({ byMonth, seasons })` keeps the exact behaviour, tests and classes of the home histogram (home test must still pass unchanged).

- [ ] Step 1: failing tests: two series (solid and dashed) with accessible summary naming both; unreliable courses absent and mentioned in the summary; histogram from my participations; home BandeauDirect tests unchanged and green.
- [ ] Step 2: run, expect FAIL. Step 3: implement. Step 4: full vitest, lint. Step 5: commit `feat(mon-espace): progression tab with the ranking curve and races per month (#1698)`.

### Task 6: disciplines tab and splits against the club median (#1699)

**Files:** backend: `GET /club/split-medians?event_type=&seasons=&federal_only=` in `backend/app/api/v1/club.py`, service in `club_service` (or a new `split_stats_service`), repository query over club participations with reliable splits (reuse `split_gap.gap`/`is_outlier` and `split_gap.median`); schema `ClubSplitMedians{event_type: str, sample: int, swim: str | None, bike: str | None, run: str | None}`; frontend `components/mon-espace/OngletDisciplines.tsx`, client method + hook; tests.

**Interfaces:**
- Repartition: count of my participations by discipline (`disciplineOf`) and format (`formatToken`), bars with labels and accessible summary.
- Splits: for each format I raced with reliable splits, my median split per discipline vs the club median from `/club/split-medians` for that `event_type`; show only when both sides exist and `sample >= 5`.

- [ ] Step 1: failing tests: backend (median over reliable splits only, outliers excluded, `sample` count, club-only, seasons filter, empty → nulls); frontend (repartition bars; comparison rows; hidden without reliable splits; summary).
- [ ] Step 2: run, expect FAIL. Step 3: implement. Step 4: backend full + ruff, frontend full + lint. Step 5: commit `feat(mon-espace): disciplines tab with splits against the club median (#1699)`.

### Task 7: right column: last result, place in club, next milestone (#1700)

**Files:** `frontend/components/mon-espace/` (`DernierResultat.tsx`, `MaPlaceAuClub.tsx`, `ProchainPalier.tsx`), `lib/mon-espace.ts` (`prochainPalier`); reuse result card download (#1371: find its component/route), `useClubRosterRank`; tests.

**Interfaces:**
- `DernierResultat({ participation, record: boolean })`: course, date, time, place, « record perso » badge, link, « Ma carte résultat » (existing #1371 action).
- `MaPlaceAuClub({ athleteId, seasons, federalOnly, rangPrecedent?: number | null })`: rank/total from `useClubRosterRank`, evolution vs previous season (second call with previous season), hidden when 404/null.
- `prochainPalier(courant: { epreuves; podiums }, saisons: { epreuves; podiums }[]): { type: "epreuves" | "podiums"; reste: number; cible: number } | null` (nearest of the two « match your best season » milestones, null when both already reached).
- Placeholders for #1671 / #1670: none rendered (they plug in later); leave a comment-free slot order in `MonEspace`.

- [ ] Step 1: failing tests: helper cases (nearest, ties, none); each card states incl. empty; rank evolution; result card button present only for own result.
- [ ] Step 2: run, expect FAIL. Step 3: implement. Step 4: full vitest, lint. Step 5: commit `feat(mon-espace): right column with my last result, my place in the club and the next milestone (#1700)`.

### Task 8: race teammates and a map of my races (#1701)

**Files:** backend `GET /auth/me/teammates?seasons=&federal_only=` (authenticated, linked athlete) in `auth.py` + service + repository (club members on the same courses, excluding athletes with an opposition: reuse the opposition filter used by public listings); schema `Teammate{athlete_id, prenom, nom, courses_communes}`; frontend `MesCoequipiers.tsx` (link « Me comparer » to `/athletes/{me}?comparer={teammateId}`: add that URL param support to `AthleteComparisonChart` so the teammate is preselected), `MiniCarte.tsx` (new compact map component reusing `getEventsGeo` data filtered on my course ids; if the map library makes a mini map heavy, a static SVG of points on a France outline is acceptable: decide and justify); tests.

- [ ] Step 1: failing tests: backend (sorted by common courses, limit 3, club only, opposition excluded, 401 anonymous); frontend (list, empty state, compare link; `AthleteComparisonChart` preselects from `?comparer=`; mini map renders my points with a text alternative listing the places).
- [ ] Step 2: run, expect FAIL. Step 3: implement. Step 4: backend full + ruff; frontend full + lint + tsc + build. Step 5: commit `feat(mon-espace): race teammates and a map of my races (#1701)`.

## End

Final whole-branch review (most capable model), one fix wave, `ui-ux-review`, PR from the top branch to `main` closing #1660 and #1695 to #1701; merge by the user.
