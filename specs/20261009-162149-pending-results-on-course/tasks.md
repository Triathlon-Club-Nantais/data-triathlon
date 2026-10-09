# Tasks: Résultats en attente de validation visibles sur la page de l'épreuve

**Input**: Design documents from `specs/20261009-162149-pending-results-on-course/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: obligatoires (Principe III). Chaque tâche de test précède son
implémentation et **doit échouer** avant elle (import manquant ou assertion rouge :
c'est attendu).

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

Aucune : pas de dépendance, pas de migration, pas de nouveau module.

## Phase 2: Foundational

- [ ] T001 Écrire le test de `awaiting_validation_clause` (en attente et non refusé ; une validée et une refusée sont écartées) dans backend/tests/test_core/test_validation.py (le symbole n'existe pas encore : le test doit échouer)
- [ ] T002 Ajouter `awaiting_validation_clause(pending_column, rejected_column)` dans backend/app/core/validation.py, docstring de module mise à jour (affichage seulement, jamais un compte)

**Checkpoint**: T001 vert.

---

## Phase 3: User Story 1 + User Story 3, page de l'épreuve sans aucun compte (Priority: P1) 🎯 MVP

**Goal**: la page d'une épreuve rend ses résultats en attente non refusés, à la fin du classement, sans rang ni écart, et aucun compte de FR-006 ne bouge.

**Independent Test**: épreuve à 1 validé + 1 en attente + 1 refusé ; `GET /courses/{id}` rend `total = 1` et une seule ligne dans `pending_participations` ; tous les comptes de FR-006 valent 1 résultat.

### Tests (écrits d'abord, rouges)

- [ ] T003 [P] [US1] Tests repository de `list_pending_for_course` dans backend/tests/test_repositories/test_pending_on_course.py : ne rend que les en attente non refusés de l'épreuve, triés par nom ; applique `q`, `club_only`, `club`, `category` ; `list_page_for_course` garde `total` et lignes inchangés en présence d'une ligne en attente ; une fois validée, la ligne quitte `list_pending_for_course` et entre dans `list_page_for_course` (US1 scénario 5)
- [ ] T004 [P] [US1] [US3] Test API dans backend/tests/test_api/test_course_pending_rows.py, fixture « 1 validé + 1 en attente + 1 refusé » (+ une épreuve qui n'a qu'un résultat en attente) : `GET /courses/{id}` rend `pending_participations` (la seule en attente, avec `is_pending_validation=true`, page 1 et page 2 identiques, filtrée par `q`) et `total = 1`, `participations` sans ligne en attente ; puis **un test par compte de FR-006**, chacun égal à la valeur sans la ligne en attente : `participation_count` et `tcn_count` de l'épreuve, `GET /courses/{id}/summary` (`total`, `finishers`, `tcn_count`, catégories), rangs et écarts (`GET /participations/{validée}` → `stats`), `GET /stats` (totaux), `GET /stats/seasons`, `GET /club/summary` (roster, podiums), `GET /courses/events` (`total`, `tcn_count`, `total_participations`), et la file qualité (`GET /courses/count?unreliable=true` et `?awaiting_review=true` inchangés, routes publiques que lit aussi `/admin/quality`)

### Implementation

- [ ] T005 [US1] Extraire de `list_page_for_course` une requête de lignes filtrées (`q`, `club_only`, `club`, `category`) sans clause de validation, et ajouter `list_pending_for_course` (clause `awaiting_validation_clause`, tri nom/prénom/id, non paginée) dans backend/app/repositories/participation_repository.py
- [ ] T006 [US1] Ajouter `pending_participations: list[ParticipationOut] = []` à `CourseParticipationPage` dans backend/app/schemas/participation.py
- [ ] T007 [US1] Renvoyer `pending_participations` depuis `get_course` dans backend/app/api/v1/courses.py (mêmes filtres que le classement)
- [ ] T008 [P] [US1] Tests Vitest dans frontend/components/results/RaceFinishers.test.tsx (rouges d'abord) : avec `pending` sur la dernière page, la ligne suit les lignes classées, porte « En attente de validation », aucun rang ni marqueur d'écart ni rang de catégorie, lien vers son détail ; absente sur une page qui n'est pas la dernière ; épreuve sans ligne validée : pas d'état vide, la ligne en attente s'affiche ; le tri client ne la déplace pas ; présente aussi dans l'arbre cartes ; sans aucune ligne (ni validée ni en attente) l'état vide existant reste
- [ ] T009 [US1] Ajouter `pending_participations` à `CourseParticipationPage` dans frontend/lib/types.ts
- [ ] T010 [US1] Rendre les lignes en attente en fin de dernière page (grille et cartes, `PendingBadge`, tiret de rang, ni `MarqueurEcart` ni rang de catégorie, hors du tri, annonce de statut qui les compte à part) dans frontend/components/results/RaceFinishers.tsx
- [ ] T011 [US1] Passer `data.pending_participations` à `RaceFinishers` dans frontend/app/(public_restricted)/courses/[id]/page.tsx (et mettre à jour son test page.test.tsx si le mock d'API l'exige)

**Checkpoint**: T003, T004 (page épreuve et comptes), T008 verts.

---

## Phase 4: User Story 2, listes d'épreuves (Priority: P2)

**Goal**: une épreuve qui n'a que des résultats en attente figure dans `/courses/events` avec `pending_count`, et les listes disent « N résultat(s) en attente ».

**Independent Test**: épreuve dont l'unique résultat est en attente : listée avec `total = 0`, `pending_count = 1` ; `total_participations` inchangé ; une épreuve dont l'unique résultat est refusé n'est pas listée.

### Tests (écrits d'abord, rouges)

- [ ] T012 [P] [US2] Tests repository de `events_page` dans backend/tests/test_repositories/test_pending_on_course.py, sur les **deux chemins** (rapide : sans filtre ; groupé : `name=…` et `club_only=True`) : l'épreuve en attente seule est listée avec `total = 0`, `tcn_count = 0`, `pending_count = 1` ; l'épreuve refusée seule ne l'est pas ; l'épreuve mixte garde `total`/`tcn_count` validés et `pending_count = 1` ; `total_participations` ne compte que des validées ; `total_events` compte l'épreuve en attente seule ; `events_with_counts` ne liste toujours pas l'épreuve en attente seule
- [ ] T013 [P] [US2] Étendre backend/tests/test_api/test_course_pending_rows.py : `GET /courses/events` rend `pending_count` et l'épreuve en attente seule
- [ ] T014 [P] [US2] Tests Vitest (rouges d'abord) : `pendingResultsLabel` dans frontend/lib/utils/event.test.ts (« 1 résultat en attente », « 2 résultats en attente ») ; `pendingCount` par groupe dans frontend/lib/utils/eventGroups.test.ts ; libellé affiché à la place du compte quand `total = 0` dans frontend/components/results/EventList.test.tsx, frontend/components/dashboard/RecentCourses.test.tsx et frontend/app/(public_restricted)/ajouter/page.test.tsx ; compte inchangé quand `total > 0`

### Implementation

- [ ] T015 [US2] `events_page` inclut les épreuves en attente seule : chemin rapide (`participation_count > 0 OR EXISTS awaiting`, `pending_count` en sous-requête corrélée) et chemin groupé (jointure validées + en attente non refusées, `total`/`tcn_count`/`total_participations` en `SUM(CASE validated)`, `pending_count` en `SUM(CASE awaiting)`) ; `events_with_counts` inchangé, dans backend/app/repositories/participation_repository.py
- [ ] T016 [US2] `pending_count: int = 0` sur `EventOut` dans backend/app/schemas/course.py et dans `_event_row` de backend/app/services/stats_service.py
- [ ] T017 [US2] `pending_count` dans `EventOut` de frontend/lib/types.ts, `pendingResultsLabel` dans frontend/lib/utils/event.ts, `pendingCount` dans frontend/lib/utils/eventGroups.ts
- [ ] T018 [US2] Afficher le libellé dans frontend/components/results/EventList.tsx (ligne, groupe, carte), frontend/components/dashboard/RecentCourses.tsx et frontend/app/(public_restricted)/ajouter/page.tsx

**Checkpoint**: T012, T013, T014 verts.

---

## Phase 5: Polish & Cross-Cutting

- [ ] T019 Mettre à jour la section « Résultats en attente de validation » de backend/app/api/AGENTS.md (l'exclusion vaut pour les comptes ; la page épreuve et `events_page` listent les en attente via `awaiting_validation_clause`) et la docstring de tête de backend/tests/test_repositories/test_pending_exclusion.py si elle se contredit
- [ ] T020 Vérification complète : `uv run pytest -m "not integration"` et `uv run ruff check .` (backend/), `npm test`, `npm run lint`, `npm run build` (frontend/)

## Dependencies & Execution Order

- T001 → T002 → toute la suite.
- US1 : T003, T004 → T005 → T006 → T007 ; T008 → T009 → T010 → T011.
- US2 dépend de T002 seulement : T012, T013, T014 → T015 → T016 → T017 → T018.
- Polish après les deux stories.

## Parallel Opportunities

- T003, T004, T008 (fichiers distincts) ; T012, T013, T014.
- Backend et frontend d'une même story en parallèle une fois le contrat figé (contracts/api.md).

## Implementation Strategy

MVP : Phase 2 + Phase 3 (la page épreuve montre ses lignes, aucun compte ne bouge).
Puis Phase 4 (listes), puis Polish. US3 n'a pas de code propre : c'est l'invariant,
prouvé par T004 et T012.
