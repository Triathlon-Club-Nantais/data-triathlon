# Résultats par sexe : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** un filtre Tous / Hommes / Femmes (`?sexe=H|F`) sur la fiche épreuve, `/club`, la fiche challenge et `/club/athletes`, avec une place par sexe sur les classements.

**Architecture:** côté API, un paramètre optionnel `gender: Literal["M","F"] | None` sur les endpoints de lecture concernés, filtrant sur `Athlete.gender`. La place par sexe se calcule dans le repository (épreuve) ou le service (challenge), sur toute l'épreuve, avant les autres filtres. Côté front, un composant `SexeToggle` partagé pilote `?sexe=` et chaque page passe `gender` à l'API.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 sync, Pydantic v2, pytest ; Next.js 16 App Router, TypeScript, vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-10-19-results-by-sex-design.md` (sondage de référence : `docs/superpowers/specs/2026-10-19-rank-gender-coverage-sondage.md`).

## Global Constraints

- Sans `gender`, chaque réponse d'endpoint reste identique (Principe IV) ; les nouveaux champs sont additifs, `null` par défaut.
- `gender` hors de `M`/`F` → 422 (FastAPI `Literal`).
- URL : `?sexe=H|F` ; absent ou autre valeur = Tous. Mapper `H→M`, `F→F`.
- Libellés : « Tous », « Hommes », « Femmes » ; groupe `role="group"` `aria-label="Sexe"` ; cibles 44 px (classe `tcn-cible-tactile`).
- Mention : « N résultats sans sexe connu non comptés » (singulier : « 1 résultat sans sexe connu non compté »), affichée seulement si N > 0, seulement sur les vues de classement (épreuve, challenge).
- Population classée d'une épreuve : finishers (`_DISPLAY_GROUP == 0`) validés, non relais, `rank_overall` non nul, du sexe demandé. Place officielle (`rank_gender`) si **toutes** ces lignes en ont un, sinon position recalculée dans `_display_order` sur cette population. Autres lignes du sexe : après, ordre actuel, `gender_place = null`.
- Couches : `api → services → repositories`, seules les repositories requêtent. `validated_clause` reste dans tous les agrégats.
- Langue : UI et docs en français, identifiants et tests en anglais. Aucun tiret de ponctuation dans les textes produits.
- TDD : test rouge d'abord, à chaque tâche.
- Commandes : backend depuis `backend/` (`uv run pytest <fichier> -n 0 -q`), front depuis `frontend/` (`npx vitest run <fichier>`).
- **Git** : `git` nu est bloqué par le hook du worktree ; utiliser `/usr/bin/git -C /home/mherrmann/Documents/work/tcn/data-triathlon/.claude/worktrees/epic-1643-results-by-sex …`. Commits directs sur `epic/1643-results-by-sex`, Conventional Commits, message terminé par `Refs #<sous-issue>`, **sans** trailer `Co-Authored-By`.

## Review Focus

- **Pagination sous filtre** : page 2 d'un classement féminin doit continuer les places (3e femme officielle de rang 4 affiche 4, pas 1). Test en tâche 2.
- **Filtres cumulés** : sous `scope=club` ou `q`, la place reste celle de toute l'épreuve. Test en tâche 2.
- **Épreuve sans finisher du sexe** : liste vide, aucune erreur, pas de mention « place recalculée ». Test en tâche 2.
- **Relais du sexe sans `rank_gender`** : ne fait pas basculer l'épreuve en recalculé. Test en tâche 2.
- **Valeur d'URL invalide** (`?sexe=x`) : se comporte comme Tous, aucun appel API avec `gender`. Test en tâche 1.

---

### Task 1: URL `?sexe=` et composant `SexeToggle` (front, socle)

**Files:**
- Modify: `frontend/lib/scope.ts`
- Test: `frontend/lib/scope.test.ts`
- Create: `frontend/components/layout/SexeToggle.tsx`
- Test: `frontend/components/layout/SexeToggle.test.tsx`
- Modify: `frontend/AGENTS.md` (une ligne à côté des paramètres d'URL déjà décrits, s'il y en a)

**Interfaces:**
- Produces: `export const SEXE_PARAM = "sexe"` ; `export type Gender = "M" | "F"` ; `export function genderFromSexeParam(sexe?: string | null): Gender | undefined` ; `export function SexeToggle(): JSX.Element` (client, lit et écrit `?sexe=` sur le chemin courant).

- [ ] **Step 1: Tests rouges du mapper** dans `scope.test.ts` :

```ts
it("maps sexe URL values to API gender", () => {
  expect(genderFromSexeParam("H")).toBe("M");
  expect(genderFromSexeParam("F")).toBe("F");
  expect(genderFromSexeParam("x")).toBeUndefined();
  expect(genderFromSexeParam(undefined)).toBeUndefined();
});
```

- [ ] **Step 2: Tests rouges de `SexeToggle`** (mock `next/navigation` comme `ScopeToggle.test.tsx`) :
  - `renders Tous, Hommes, Femmes inside a group labelled Sexe` : `getByRole("group", { name: "Sexe" })` contient trois boutons.
  - `marks Femmes as selected when sexe=F` : état sélectionné sur « Femmes » (attribut exposé par `SegmentedControl`).
  - `treats an invalid sexe value as Tous` : `?sexe=x` → « Tous » sélectionné.
  - `pushes sexe=F and drops page when Femmes is clicked` : depuis `?page=3&scope=club`, `router.push` reçoit `/chemin?scope=club&sexe=F`.
  - `removes sexe when Tous is clicked` : depuis `?sexe=H`, `router.push` reçoit le chemin sans `sexe`.
- [ ] **Step 3: Run** `npx vitest run lib/scope.test.ts components/layout/SexeToggle.test.tsx`, attendu FAIL.
- [ ] **Step 4: Implémenter** `SEXE_PARAM`, `Gender`, `genderFromSexeParam` dans `scope.ts` (patron de `federalOnlyFromParam`) et `SexeToggle` : `SegmentedControl` du kit `components/tcn/` (options `{value:"", label:"Tous"}`, `{value:"H", label:"Hommes"}`, `{value:"F", label:"Femmes"}`), enveloppé dans `role="group" aria-label="Sexe"`, navigation par `router.push` dans `useTransition` comme `ScopeToggle`, en supprimant `page`. Cibles 44 px.
- [ ] **Step 5: Run** la même commande, attendu PASS ; puis `npm run lint`.
- [ ] **Step 6: Commit** `feat(results): sexe URL param and shared toggle` + `Refs #1645`.

### Task 2: Place par sexe sur `GET /courses/{id}` (backend)

**Files:**
- Modify: `backend/app/repositories/participation_repository.py` (`_course_rows`, `list_page_for_course`, `list_pending_for_course`, nouvelle `gender_places`)
- Modify: `backend/app/schemas/participation.py` (`ParticipationOut`)
- Modify: `backend/app/api/v1/courses.py` (`get_course`)
- Modify: `backend/app/api/AGENTS.md` (paramètre `gender` : optionnel, filtre sur `Athlete.gender`, 422 hors M/F, place par sexe)
- Test: `backend/tests/test_api/test_courses_api.py`

**Interfaces:**
- Produces:
  - `gender_places(db: Session, course_id: int, gender: Literal["M","F"]) -> tuple[dict[int, int], bool]` : `{participation_id: place}` sur la population classée, et `official` (vrai si elle est non vide et que toutes ses lignes ont un `rank_gender`).
  - `list_page_for_course(..., gender: Literal["M","F"] | None = None, official_gender_order: bool = False)` et `list_pending_for_course(..., gender=None)` ; `_course_rows(..., gender=None)` ajoute `Athlete.gender == gender`.
  - `ParticipationOut.gender_place: int | None = None`, `ParticipationOut.gender_place_official: bool | None = None`.
  - Paramètre `gender` sur `GET /api/v1/courses/{id}`.

- [ ] **Step 1: Tests rouges** dans `test_courses_api.py` (fixtures existantes du fichier). Jeu commun : une épreuve avec femmes finishers `rank_overall` 10, 11, 15, 19 et `rank_gender` 1, 2, 4, 5 ; un homme finisher ; un athlète `gender=""` ; une femme DNF ; un relais de femme sans `rank_gender`.
  - `test_get_course_without_gender_is_unchanged` : toutes les lignes, `gender_place` et `gender_place_official` à `None`, ordre inchangé.
  - `test_get_course_gender_uses_official_rank_gender` : `gender=F` → finishers classés en tête, places `[1, 2, 4, 5]`, `gender_place_official is True` ; ni l'homme ni la ligne sans sexe ; le relais et la DNF après, `gender_place is None`.
  - `test_get_course_gender_recalculates_when_one_rank_gender_missing` : `rank_gender` de la 3e femme à `None` → places `[1, 2, 3, 4]`, `gender_place_official is False`.
  - `test_get_course_gender_relay_does_not_switch_to_recalculated` : le relais sans `rank_gender` laisse `official` vrai (déjà couvert par le jeu commun, assert explicite).
  - `test_get_course_gender_place_survives_query_filter` : `gender=F&q=<nom de la 3e femme>` → une ligne, `gender_place == 4`.
  - `test_get_course_gender_place_continues_across_pages` : `gender=F&page_size=2&page=2` → places `[4, 5]`.
  - `test_get_course_gender_without_matching_finisher_is_empty` : épreuve sans femme → `participations == []`, `total == 0`.
  - `test_get_course_gender_filters_pending_rows` : une ligne en attente d'un homme et d'une femme, appel bénévole → `pending_participations` ne contient que la femme, `gender_place is None`.
  - `test_get_course_rejects_unknown_gender` : `gender=X` → 422.
- [ ] **Step 2: Run** `uv run pytest tests/test_api/test_courses_api.py -n 0 -q -k gender`, attendu FAIL.
- [ ] **Step 3: Implémenter.** Clause de population : `_GENDER_RANKED = and_(_DISPLAY_GROUP == 0, Participation.rank_overall.is_not(None), Participation.is_relay.is_(False))`. `gender_places` lit `(id, rank_gender)` des lignes validées du sexe sur cette clause, triées par `_display_order()`, puis rend `{id: rank_gender}` si officiel, sinon `{id: position}` (1-based). Sous `gender`, `list_page_for_course` trie par `case((_GENDER_RANKED, 0), else_=1)`, puis `Participation.rank_gender` si `official_gender_order`, puis `_display_order()`. La route appelle `gender_places` avant `list_page_for_course`, lui passe `official`, et pose `gender_place`/`gender_place_official` par `model_copy(update=…)` sur les lignes présentes dans le dict.
- [ ] **Step 4: Run** le fichier entier puis `uv run pytest -m "not integration" -q` et `uv run ruff check .`, attendu PASS.
- [ ] **Step 5: Commit** `feat(courses): filter a race by sex and rank by gender place` + `Refs #1645`.

### Task 3: Fiche épreuve par sexe (front)

**Files:**
- Modify: `frontend/lib/types.ts` (`CourseQuery.gender?: Gender`, `Participation.gender_place?: number | null`, `gender_place_official?: boolean | null`)
- Modify: `frontend/app/(public_restricted)/courses/[id]/page.tsx`
- Modify: `frontend/components/results/RaceFinishers.tsx`
- Test: `frontend/components/results/RaceFinishers.test.tsx`, test de page existant s'il y en a un

**Interfaces:**
- Consumes: `SEXE_PARAM`, `genderFromSexeParam`, `Gender`, `SexeToggle` (tâche 1) ; `gender_place`, `gender_place_official` (tâche 2).
- Produces: props `gender?: Gender` et `unknownGenderCount?: number` sur `RaceFinishers`.

- [ ] **Step 1: Tests rouges** dans `RaceFinishers.test.tsx` :
  - `renders the sexe toggle` : groupe « Sexe » présent.
  - `shows gender_place in the place column under a gender filter` : lignes avec `rank_overall` 10/11 et `gender_place` 1/2, `gender="F"` → la colonne de place affiche 1 et 2.
  - `flags recalculated places` : une ligne `gender_place_official: false` → texte contenant « place recalculée » (ou « places recalculées »).
  - `announces unknown-sex rows` : `unknownGenderCount={3}` → « 3 résultats sans sexe connu non comptés » ; `1` → singulier ; `0` → rien.
  - `keeps the current place column without gender` : sans `gender`, rien ne change (assertion sur l'affichage actuel).
- [ ] **Step 2: Run** `npx vitest run components/results/RaceFinishers.test.tsx`, attendu FAIL.
- [ ] **Step 3: Implémenter.** `page.tsx` lit `sp[SEXE_PARAM]`, passe `gender` à `getCourse` et à `RaceFinishers`, et calcule `unknownGenderCount` depuis `CourseSummary` (`total - male - female` ; vérifier dans le service de résumé que `male`/`female` comptent la même population que `total`, sinon prendre la population qui correspond aux lignes listées). `lienFiltre()` conserve `sexe`. `RaceFinishers` place `SexeToggle` à côté du contrôle « Tous / TCN » ; sous `gender`, la place affichée est `gender_place` ; une ligne de note discrète au-dessus du tableau pour « place recalculée » et pour la mention des lignes sans sexe.
- [ ] **Step 4: Run** le test, puis `npm test`, `npm run lint`, `npm run build`, attendu PASS.
- [ ] **Step 5: Commit** `feat(courses): sex toggle and gender place on the race page` + `Refs #1645`.

### Task 4: Filtre `gender` sur `/stats`, `/club/summary`, `/club/podiums`, `/participations` (backend)

**Files:**
- Modify: `backend/app/repositories/participation_repository.py` (`_stats_filters` et ses appelants `stats_totals`, `stats_by_type`, `stats_by_month_rows`, `stats_recent_rows`, `stats_rank_rows` ; `club_podiums` ; `_apply_filters`/`list_participations`)
- Modify: `backend/app/repositories/athlete_repository.py` (`_club_roster_query`, `club_roster`, `club_composition`)
- Modify: `backend/app/services/stats_service.py` (`get_stats`), `backend/app/services/club_service.py` (`get_club_summary`, `get_club_podiums`)
- Modify: `backend/app/api/v1/stats.py`, `backend/app/api/v1/club.py`, `backend/app/api/v1/participations.py`
- Test: `backend/tests/test_api/test_club_api.py`, `backend/tests/test_api/test_participations_api.py`, et le fichier qui teste `GET /api/v1/stats` (`grep -rln '/api/v1/stats"' tests`)

**Interfaces:**
- Produces: kwarg `gender: Literal["M","F"] | None = None` sur chacune des fonctions listées, et paramètre `gender` sur `GET /stats`, `GET /club/summary`, `GET /club/podiums`, `GET /participations`. Filtre côté participations : `Participation.athlete_id.in_(select(Athlete.id).where(Athlete.gender == gender))`, qui ne dépend d'aucune jointure.
- `/club/best-times` : **inchangé**, il rend déjà une ligne par genre ; le front filtre (tâche 5).

- [ ] **Step 1: Tests rouges.** Jeu : participations TCN validées de 2 femmes, 1 homme, 1 athlète `gender=""`, dont un podium féminin et un podium masculin.
  - `test_stats_gender_filter_counts_only_that_sex` : sans `gender`, le total de résultats vaut 4 ; `gender=F` → 2 ; `gender=M` → 1.
  - `test_club_podiums_gender_filter` : `gender=F` → seuls des podiums d'athlètes F dans chaque mode.
  - `test_club_summary_gender_filter` : `gender=F` → roster et podiums sans l'homme ; sans `gender`, réponse inchangée.
  - `test_club_summary_gender_keeps_unlinked_members_by_licence_gender` : seulement si la section roster lit des membres sans athlète lié (`ClubMember`) ; alors un membre F non lié reste sous `gender=F`. Sinon, ne pas écrire ce test et le noter dans le rapport de tâche.
  - `test_participations_gender_filter` : `GET /participations?scope=club&gender=F` → deux lignes.
  - `test_gender_param_rejects_unknown_value` paramétré sur les quatre endpoints : `gender=X` → 422.
- [ ] **Step 2: Run** les fichiers concernés avec `-k gender`, attendu FAIL.
- [ ] **Step 3: Implémenter** en propageant `gender` de la route au service puis au repository ; `_stats_filters` porte la clause une seule fois pour toutes les requêtes de stats. Roster et composition : filtrer sur la source de sexe que la requête utilise déjà.
- [ ] **Step 4: Run** `uv run pytest -m "not integration" -q`, `uv run ruff check .`, attendu PASS.
- [ ] **Step 5: Commit** `feat(club): gender filter on stats, club summary, podiums and participations` + `Refs #1646`.

### Task 5: `/club` par sexe (front)

**Files:**
- Modify: `frontend/lib/api/server.ts`, `frontend/lib/api/client.ts`, `frontend/lib/types.ts` (option `gender?: Gender` sur `getStats`, `getClubSummary`, `getClubPodiums`, `ParticipationFilters`)
- Modify: `frontend/app/(public_restricted)/club/page.tsx`
- Modify: `frontend/components/club/ClubDashboard.tsx`, `PodiumsList.tsx` (là où `getClubPodiums` est appelé), `ClubBestTimesCard.tsx`
- Test: `frontend/app/(public_restricted)/club/page.test.tsx`, `frontend/components/club/ClubDashboard.test.tsx`, `ClubBestTimesCard.test.tsx`, `PodiumsList.test.tsx`

**Interfaces:**
- Consumes: tâche 1 (`SexeToggle`, `genderFromSexeParam`), tâche 4 (paramètres API).
- Produces: prop `gender?: Gender` sur `ClubDashboard`, `PodiumsList` et `ClubBestTimesCard`.

- [ ] **Step 1: Tests rouges.**
  - `page.test.tsx` : `passes gender to stats, summary and recent results when sexe=F` (les mocks `getStats`, `getClubSummary`, `listParticipations` reçoivent `gender: "F"`) ; `sends no gender for an invalid sexe value`.
  - `ClubDashboard.test.tsx` : `renders the sexe toggle` ; `hides the composition card under a gender filter`.
  - `PodiumsList.test.tsx` : `requests full podiums with the gender filter`.
  - `ClubBestTimesCard.test.tsx` : `shows only the selected sex best times` (entrées M et F, `gender="F"` → seules les F).
- [ ] **Step 2: Run** ces fichiers, attendu FAIL.
- [ ] **Step 3: Implémenter** : la page lit `SEXE_PARAM` et propage ; `SexeToggle` dans les contrôles du tableau de bord, à côté de `RankTypeToggle` ; `ClubComposition` non rendue sous `gender`.
- [ ] **Step 4: Run** `npm test`, `npm run lint`, `npm run build`, attendu PASS.
- [ ] **Step 5: Commit** `feat(club): sex toggle on the club page` + `Refs #1646`.

### Task 6: Challenges par sexe (backend et front)

**Files:**
- Modify: `backend/app/schemas/challenge.py` (`ChallengeResultOut`, schéma de détail)
- Modify: `backend/app/services/challenge_service.py` (`detail`)
- Modify: `backend/app/api/v1/challenges.py`
- Test: `backend/tests/test_api/test_challenges_api.py`
- Modify: `frontend/lib/types.ts`, `frontend/lib/api/server.ts` (`getChallenge(id, { gender })`)
- Modify: `frontend/app/(public_restricted)/challenges/[id]/page.tsx`
- Test: `frontend/app/(public_restricted)/challenges/[id]/page.test.tsx`

**Interfaces:**
- Produces: `ChallengeResultOut.gender: str`, `.rank_gender: int | None`, `.gender_place: int | None = None`, `.gender_place_official: bool | None = None` ; détail `.unknown_gender_count: int | None = None` ; `challenge_service.detail(db, challenge_id, gender: Literal["M","F"] | None = None)`.

- [ ] **Step 1: Tests rouges backend.**
  - `test_challenge_detail_exposes_gender_and_rank_gender` : sans filtre, chaque résultat porte `gender` et `rank_gender`, `gender_place is None`, `unknown_gender_count is None`.
  - `test_challenge_detail_gender_official_places` : femmes finishers `rank_overall` 3, 5, 8, `rank_gender` 1, 2, 4 ; `gender=F` → places `[1, 2, 4]`, officielles, homme absent.
  - `test_challenge_detail_gender_recalculated_places` : un `rank_gender` manquant → `[1, 2, 3]`, `gender_place_official is False`.
  - `test_challenge_detail_gender_counts_unknown` : un résultat `gender=""` → `unknown_gender_count == 1` sous `gender=F`.
  - `test_challenge_detail_rejects_unknown_gender` : 422.
- [ ] **Step 2: Tests rouges front** (`page.test.tsx`) : `passes gender to getChallenge when sexe=F` ; `shows gender_place under the filter` ; `announces unknown-sex results` ; `renders the sexe toggle`.
- [ ] **Step 3: Run** les deux suites, attendu FAIL.
- [ ] **Step 4: Implémenter.** Population classée : `status == "finisher"` et `rank_overall` non nul ; officiel si toutes ont un `rank_gender` ; tri des classées par `rank_gender` (officiel) ou par l'ordre actuel, le reste après. Front : même présentation que la fiche épreuve (tâche 3).
- [ ] **Step 5: Run** `uv run pytest -m "not integration" -q`, `uv run ruff check .`, `npm test`, `npm run lint`, `npm run build`, attendu PASS.
- [ ] **Step 6: Commit** `feat(challenges): expose sex and gender rank and filter results by sex` + `Refs #1647`.

### Task 7: `/club/athletes` par sexe

**Files:**
- Modify: `backend/app/schemas/athlete.py` (`AthleteSeasonActivity.gender: str`), `backend/app/repositories/athlete_repository.py` (`list_with_season_participation_count` sélectionne `Athlete.gender` si nécessaire)
- Test: `backend/tests/test_api/test_athletes_api.py`
- Modify: `frontend/lib/types.ts`, `frontend/components/club/AthleteSeasonList.tsx`
- Test: `frontend/components/club/AthleteSeasonList.test.tsx`

**Interfaces:**
- Consumes: `SEXE_PARAM`, `genderFromSexeParam`, `SexeToggle` (tâche 1).
- Produces: `AthleteSeasonActivity.gender`.

- [ ] **Step 1: Test rouge backend** `test_season_activity_exposes_gender` : chaque ligne de `GET /athletes/season-activity` porte `gender` (`"M"`, `"F"` ou `""`).
- [ ] **Step 2: Tests rouges front** : `filters the list by sexe=F` (athlètes M et F, URL `?sexe=F` → seuls les F) ; `renders the sexe toggle` ; `shows everyone without sexe`.
- [ ] **Step 3: Run**, attendu FAIL.
- [ ] **Step 4: Implémenter** : filtre client dans `AthleteSeasonList`, combiné à la recherche et au filtre de validation existants ; `SexeToggle` dans la barre d'outils de la liste. Pas de paramètre API.
- [ ] **Step 5: Run** `uv run pytest -m "not integration" -q`, `npm test`, `npm run lint`, `npm run build`, attendu PASS.
- [ ] **Step 6: Commit** `feat(club): filter the club athletes list by sex` + `Refs #1648`.
