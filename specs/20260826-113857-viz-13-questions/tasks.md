---
description: "Task list template for feature implementation"
---

# Tasks: Les 13 questions que l'app ne sait pas montrer

**Input**: Design documents from `specs/20260826-113857-viz-13-questions/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Principe III de la constitution v1.1.1 — TDD sans réseau, **non-négociable**. Chaque user story porte ses tâches de test, à écrire et faire échouer avant l'implémentation.

**Organization**: Une phase par user story (US1→US13, ordre de `spec.md`), livrées **séquentiellement dans une seule PR parapluie** (décision explicite de l'utilisateur, cf. `spec.md` §Assumptions — pas de découpage en issues séparées).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Peut s'exécuter en parallèle (fichiers différents, aucune dépendance non résolue)
- **[Story]**: User story à laquelle la tâche appartient (US1…US13)

## Path Conventions

Application web existante : `backend/app/`, `backend/tests/`, `frontend/app/`, `frontend/components/`, `frontend/lib/` — chemins réels du dépôt, pas de convention générique.

---

## Phase 1: Setup

- [ ] T001 [P] Vérifier que `d3-scale`/`d3-shape` sont présents dans `frontend/package.json` (aucune nouvelle dépendance de visualisation pour cette feature)
- [ ] T002 [P] Aligner l'environnement du worktree sur les lockfiles : `cd backend && uv sync`, `cd frontend && npm install`

---

## Phase 2: Foundational

**Aucune tâche bloquante commune.** Chaque user story touche des fichiers indépendants (cf. `plan.md` §Project Structure) ; la seule extension partagée (`participation_stats.py`, US4+US5) est additive et ne bloque ni US4 ni US5 l'une envers l'autre puisqu'elles ajoutent des champs distincts. La migration Alembic (US13) ne bloque qu'US13. Pas de phase fabriquée pour la forme (Principe VI, YAGNI).

**Checkpoint**: Aucune attente — les user stories peuvent démarrer dans l'ordre de priorité dès Setup terminé.

---

## Phase 3: User Story 1 - Est-ce que je progresse ? (Priority: P1) 🎯 MVP

**Goal**: Afficher, sur `/athletes/[id]`, l'évolution du ratio de performance de l'athlète à travers ses participations.

**Independent Test**: Un athlète ≥3 participations voit une série temporelle ; un athlète à 1 participation voit un état vide explicite.

### Tests for User Story 1

- [X] T003 [P] [US1] Test vitest pour `progressionSeries(participations)` (dérive `rankRatio` par participation, trié par `event_date`) dans `frontend/lib/utils/ranking.test.ts`
- [X] T004 [P] [US1] Test vitest pour `ProgressionChart` (rendu SSR, état vide <3 participations) dans `frontend/components/charts/ProgressionChart.test.tsx`

### Implementation for User Story 1

- [X] T005 [US1] Ajouter `progressionSeries(participations)` dans `frontend/lib/utils/ranking.ts`
- [X] T006 [US1] Créer `ProgressionChart` (d3-scale/d3-shape, SSR, état vide) dans `frontend/components/charts/ProgressionChart.tsx`
- [X] T007 [US1] Intégrer `ProgressionChart` dans `frontend/app/(public_restricted)/athletes/[id]/page.tsx`

**Checkpoint**: US1 fonctionnelle et testable indépendamment.

---

## Phase 4: User Story 2 - Mon temps, il vaut quoi ? (Priority: P2)

**Goal**: Sur le détail d'une participation, afficher l'histogramme des temps de l'épreuve avec un repère sur le temps de l'athlète.

**Independent Test**: Ouvrir le détail d'une participation validée et voir l'histogramme avec le repère.

### Tests for User Story 2

- [ ] T008 [P] [US2] Test vitest pour le calcul du bucket de l'athlète à partir de `summary.histogram` (`start_sec`/`bucket_sec`) dans `frontend/lib/utils/histogram-ticks.test.ts`
- [ ] T009 [P] [US2] Test vitest pour `Histogram` avec repère athlète dans `frontend/components/charts/Histogram.test.tsx`

### Implementation for User Story 2

- [ ] T010 [US2] Fetch `getCourseSummary` en parallèle sur `.../participations/[participationId]/page.tsx`, patron `courses/[id]/page.tsx:60-64`
- [ ] T011 [US2] Étendre `Histogram.tsx` pour accepter et afficher un repère de position
- [ ] T012 [US2] Intégrer l'histogramme avec repère sur l'écran détail participation

**Checkpoint**: US1+US2 fonctionnelles indépendamment.

---

## Phase 5: User Story 3 - Où je me situe dans ma catégorie ? (Priority: P3)

**Goal**: Sur le détail de participation, afficher le classement en catégorie avec son dénominateur.

**Independent Test**: Le détail affiche « Nᵉ / M » avec une représentation visuelle de la place dans l'effectif.

### Tests for User Story 3

- [ ] T013 [P] [US3] Test vitest pour `CategoryBars` avec marquage de la catégorie de l'athlète dans `frontend/components/charts/CategoryBars.test.tsx`

### Implementation for User Story 3

- [ ] T014 [US3] Étendre `CategoryBars.tsx` pour marquer la catégorie de l'athlète (depuis `summary.categories`/`categories_total`, déjà fetché en T010)
- [ ] T015 [US3] Afficher « Nᵉ / M » à côté de la représentation visuelle sur l'écran détail participation

**Checkpoint**: US1→US3 fonctionnelles indépendamment.

---

## Phase 6: User Story 4 - Où je perds du temps, et est-ce que ça change ? (Priority: P4)

**Goal**: Écarts de temps par segment en représentation visuelle (pas seulement en %), et récurrence d'un point faible sur la page profil.

**Independent Test**: Le détail de participation affiche les écarts en secondes ; la page profil signale un segment récurrent si applicable.

### Tests for User Story 4

- [ ] T016 [P] [US4] Test pytest rouge pour `mine_seconds`/`theirs_seconds` de `ComparisonRow` dans `backend/tests/test_services/test_participation_stats_service.py`
- [ ] T017 [P] [US4] Test contrat API pour la forme JSON étendue de `GET /api/v1/participations/{id}/stats` dans `backend/tests/test_api/test_participation_stats_api.py`
- [ ] T018 [P] [US4] Test vitest pour la représentation visuelle des écarts dans `frontend/components/charts/ComparisonTable.test.tsx`
- [ ] T019 [P] [US4] Test vitest pour l'agrégation de récurrence de segment dans `frontend/lib/utils/ranking.test.ts`

### Implementation for User Story 4

- [ ] T020 [US4] Ajouter `mine_seconds`/`theirs_seconds` à `ComparisonRow` dans `backend/app/schemas/participation_stats.py`
- [ ] T021 [US4] Exposer les valeurs déjà calculées par `_comparison` dans `backend/app/services/participation_stats_service.py`
- [ ] T022 [US4] Étendre `ComparisonTable.tsx` pour afficher les écarts en représentation visuelle
- [ ] T023 [US4] Ajouter l'agrégation de récurrence de segment dans `frontend/lib/utils/ranking.ts` (depuis `participation.splits`, déjà chargé)
- [ ] T024 [US4] Afficher le signal de récurrence sur `athletes/[id]/page.tsx`

**Checkpoint**: US1→US4 fonctionnelles indépendamment.

---

## Phase 7: User Story 5 - Ai-je accéléré, ou les autres ont-ils ralenti ? (Priority: P5)

**Goal**: Graphique de temps cumulés (allure) en complément du graphique de classement.

**Independent Test**: Le détail de participation affiche un graphique d'allure à côté du classement.

### Tests for User Story 5

- [ ] T025 [P] [US5] Test pytest rouge pour `cumulative_seconds` de `RankingEvolutionStep` dans `backend/tests/test_services/test_participation_stats_service.py`
- [ ] T026 [P] [US5] Test vitest pour le graphique d'allure dans `frontend/components/charts/RankingEvolutionChart.test.tsx`

### Implementation for User Story 5

- [ ] T027 [US5] Ajouter `cumulative_seconds` à `RankingEvolutionStep` dans `backend/app/schemas/participation_stats.py`
- [ ] T028 [US5] Exposer la valeur déjà calculée par `_cumulative_seconds` dans `backend/app/services/participation_stats_service.py`
- [ ] T029 [US5] Étendre `RankingEvolutionChart.tsx` avec le graphique de temps cumulés

**Checkpoint**: US1→US5 fonctionnelles indépendamment.

---

## Phase 8: User Story 6 - Comment je me compare à un coéquipier ? (Priority: P6)

**Goal**: Sélectionner un second athlète du club et afficher une comparaison sur une épreuve commune.

**Independent Test**: Comparaison affichée pour deux athlètes avec épreuve commune ; message explicite sans épreuve commune.

### Tests for User Story 6

- [ ] T030 [P] [US6] Test vitest pour le filtrage sur épreuve commune entre deux athlètes dans `frontend/lib/utils/athlete-comparison.test.ts`
- [ ] T031 [P] [US6] Test vitest pour `AthleteComparisonChart`, y compris le cas sans épreuve commune, dans `frontend/components/charts/AthleteComparisonChart.test.tsx`

### Implementation for User Story 6

- [ ] T032 [US6] Créer `frontend/lib/utils/athlete-comparison.ts` (filtre `listParticipations` sur épreuve commune)
- [ ] T033 [US6] Créer le sélecteur d'athlète + `AthleteComparisonChart.tsx`
- [ ] T034 [US6] Intégrer sur `athletes/[id]/page.tsx`

**Checkpoint**: US1→US6 fonctionnelles indépendamment.

---

## Phase 9: User Story 7 - Sur quoi je cours vraiment, et combien par saison ? (Priority: P7)

**Goal**: Répartition complète des disciplines/distances par saison, pas seulement le mode.

**Independent Test**: La page profil d'un athlète multi-discipline affiche la répartition complète.

### Tests for User Story 7

- [ ] T035 [P] [US7] Test vitest pour l'agrégation discipline × saison depuis `data.participations` dans `frontend/lib/utils/format.test.ts`

### Implementation for User Story 7

- [ ] T036 [US7] Ajouter l'agrégation complète (au-delà du mode) dans `frontend/lib/utils/format.ts`
- [ ] T037 [US7] Afficher la répartition sur `athletes/[id]/page.tsx`

**Checkpoint**: US1→US7 fonctionnelles indépendamment.

---

## Phase 10: User Story 8 - Le club progresse-t-il ? (Priority: P8)

**Goal**: Graphique de performance collective par saison, piloté par le `SeasonSelector` existant.

**Independent Test**: Changer de saison met à jour le graphique de performance (pas seulement de volume).

### Tests for User Story 8

- [ ] T038 [P] [US8] Test vitest pour `ClubPerformanceChart` piloté par `SeasonSelector` dans `frontend/components/charts/ClubPerformanceChart.test.tsx`

### Implementation for User Story 8

- [ ] T039 [US8] Créer `ClubPerformanceChart.tsx` consommant `rank_counters` (déjà servi par `GET /stats`)
- [ ] T040 [US8] Intégrer sur `dashboard/page.tsx`, piloté par `SeasonSelector`

**Checkpoint**: US1→US8 fonctionnelles indépendamment.

---

## Phase 11: User Story 9 - À quoi ressemble le club ? (Priority: P9)

**Goal**: Répartition du club par genre et catégorie d'âge sur `/club`.

**Independent Test**: `/club` affiche la répartition genre/catégorie.

### Tests for User Story 9

- [ ] T041 [P] [US9] Test vitest pour l'ajout de `category` à `RosterEntry`/`buildRoster` dans `frontend/lib/utils/club-aggregate.test.ts`

### Implementation for User Story 9

- [ ] T042 [US9] Ajouter `category` à `RosterEntry` et son agrégation dans `frontend/lib/utils/club-aggregate.ts`
- [ ] T043 [US9] Créer la vue de répartition genre/catégorie (pattern `GenderDonut`) sur `club/page.tsx`

**Checkpoint**: US1→US9 fonctionnelles indépendamment.

---

## Phase 12: User Story 10 - Où le club performe-t-il ? (Priority: P10)

**Goal**: Croiser `podiumsByScope` avec la discipline pour montrer la performance du club par discipline.

**Independent Test**: La vue club affiche la performance par discipline, distincte du volume d'épreuves.

### Tests for User Story 10

- [ ] T044 [P] [US10] Test vitest pour le croisement `podiumsByScope` × discipline dans `frontend/lib/utils/club-aggregate.test.ts`

### Implementation for User Story 10

- [ ] T045 [US10] Étendre `club-aggregate.ts` pour grouper `podiumsByScope` par discipline (`formatToken`)
- [ ] T046 [US10] Afficher la performance par discipline sur `club/page.tsx`

**Checkpoint**: US1→US10 fonctionnelles indépendamment.

---

## Phase 13: User Story 11 - Quelles saisons sont couvertes, où sont les trous ? (Priority: P11)

**Goal**: Vue de couverture temporelle des épreuves sur `/resultats`.

**Independent Test**: `/resultats` affiche la densité mensuelle/annuelle et les périodes vides.

### Tests for User Story 11

- [ ] T047 [P] [US11] Test vitest pour l'agrégation mois/année (`page_size=all`) dans `frontend/lib/utils/coverage.test.ts`

### Implementation for User Story 11

- [ ] T048 [US11] Créer `frontend/lib/utils/coverage.ts` (agrégation mois/année sur `course.event_date`)
- [ ] T049 [US11] Intégrer `MonthlyTrend` (réutilisé) sur `resultats/page.tsx`

**Checkpoint**: US1→US11 fonctionnelles indépendamment.

---

## Phase 14: User Story 12 - Quelles épreuves près de chez moi, et lesquelles à venir ? (Priority: P12)

**Goal**: Filtre "à venir" et tri/filtre par distance sur `/carte`.

**Independent Test**: Le filtre "à venir" ne montre que les épreuves futures ; le tri par distance fonctionne.

### Tests for User Story 12

- [ ] T050 [P] [US12] Test vitest pour le filtre "à venir" dans `frontend/lib/utils/map-filters.test.ts`
- [ ] T051 [P] [US12] Test vitest pour le calcul de distance haversine dans `frontend/lib/utils/map-filters.test.ts`

### Implementation for User Story 12

- [ ] T052 [US12] Créer `frontend/lib/utils/map-filters.ts` (filtre à venir + haversine depuis un point de référence statique)
- [ ] T053 [US12] Intégrer le filtre et le tri par distance sur `carte/page.tsx`/`MapView.tsx`

**Checkpoint**: US1→US12 fonctionnelles indépendamment.

---

## Phase 15: User Story 13 - La file de validation tient-elle le rythme ? (Priority: P13)

**Goal**: Arriéré de validation dans le temps et délai moyen de traitement sur `/benevoles`.

**Independent Test**: Après validations/rejets post-migration, le graphique d'arriéré et le délai moyen s'affichent ; état vide explicite avant toute résolution post-migration.

### Tests for User Story 13

- [ ] T054 [P] [US13] Test de migration (upgrade/downgrade) pour `validated_at`/`rejected_at` dans `backend/tests/test_migrations.py`
- [ ] T055 [P] [US13] Test pytest rouge pour l'écriture de `validated_at`/`rejected_at` dans `backend/tests/test_services/test_admin_actions.py`
- [ ] T056 [P] [US13] Test pytest pour la nouvelle fonction de repository d'historique dans `backend/tests/test_repositories/test_participation_repository.py`
- [ ] T057 [P] [US13] Test contrat API pour `GET /api/v1/benevoles/queue/history` dans `backend/tests/test_api/test_benevoles_api.py`
- [ ] T058 [P] [US13] Test vitest pour `ValidationBacklogChart` (état vide sans résolution post-migration) dans `frontend/components/charts/ValidationBacklogChart.test.tsx`

### Implementation for User Story 13

- [ ] T059 [US13] Migration Alembic : `validated_at`/`rejected_at` nullable sur `Participation` (`uv run alembic revision --autogenerate`, relecture manuelle)
- [ ] T060 [US13] Écrire `validated_at` dans `validate_participation`, `rejected_at` dans `reject_participation` (`backend/app/services/admin_actions.py`)
- [ ] T061 [US13] Ajouter la fonction de lecture d'historique dans `backend/app/repositories/participation_repository.py`
- [ ] T062 [US13] Créer le schéma `ValidationQueueHistory`/`ValidationQueueBacklogPoint` dans `backend/app/schemas/`
- [ ] T063 [US13] Créer le service d'agrégation (arriéré par jour, délai moyen) dans `backend/app/services/`
- [ ] T064 [US13] Ajouter la route `GET /benevoles/queue/history` dans `backend/app/api/v1/benevoles.py`, gardée par `require_benevole_access`
- [ ] T065 [US13] Ajouter `getValidationQueueHistory` dans `frontend/lib/api/client.ts`
- [ ] T066 [US13] Créer `ValidationBacklogChart.tsx` et l'intégrer sur `benevoles/page.tsx`

**Checkpoint**: US1→US13 toutes fonctionnelles indépendamment — périmètre de l'issue #466 couvert.

---

## Phase 16: Polish & Cross-Cutting Concerns

- [ ] T067 [P] Vérifier le responsive à 375 px sur les 6 écrans touchés (standard #480)
- [ ] T068 [P] Vérifier le rendu SSR sans JavaScript sur un écran par famille de graphique nouveau
- [ ] T069 Dérouler les 13 scénarios manuels de `quickstart.md`
- [ ] T070 [P] `uv run ruff check backend` et `npm run lint` (frontend)
- [ ] T071 Suite complète verte : `uv run pytest -m "not integration"`, `npm run build`, `npm test`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** : aucune dépendance.
- **Foundational (Phase 2)** : aucune tâche — rien ne bloque les user stories.
- **User Stories (Phase 3-15)** : chacune indépendante de Setup terminé ; **livrées séquentiellement dans l'ordre P1→P13** par décision de l'utilisateur (pas de parallélisation d'équipe pour cette feature), mais chaque story reste indépendamment testable si l'ordre devait changer.
- **Polish (Phase 16)** : après les 13 user stories.

### User Story Dependencies

Aucune dépendance croisée entre user stories — chacune touche des écrans/fichiers distincts, à l'exception de deux paires qui partagent un écran ou un fichier **sans se bloquer** :

- US2 et US3 partagent l'écran détail de participation et le fetch `getCourseSummary` (T010) — US3 réutilise le fetch posé par US2, mais pourrait fetcher indépendamment si l'ordre était inversé.
- US9 et US10 partagent `frontend/lib/utils/club-aggregate.ts` — livrées séquentiellement dans cet ordre pour éviter un conflit de merge sur le même fichier, pas par dépendance fonctionnelle.

### Within Each User Story

- Tests écrits et rouges avant l'implémentation (Principe III).
- Backend (schéma → service → repository → route) avant frontend quand la story touche les deux couches (US4, US5, US13).
- Story complète et vérifiée (checkpoint) avant de passer à la priorité suivante.

### Parallel Opportunities

- T001-T002 (Setup) en parallèle.
- Toutes les tâches de test `[P]` d'une même story en parallèle entre elles.
- Au sein d'US13, T054-T058 (tests) en parallèle ; T059 (migration) précède T060-T064, qui peuvent ensuite s'enchaîner par couche.

---

## Parallel Example: User Story 4

```bash
# Tests d'US4 en parallèle :
Task: "Test pytest rouge pour mine_seconds/theirs_seconds dans backend/tests/test_services/test_participation_stats_service.py"
Task: "Test contrat API dans backend/tests/test_api/test_participation_stats_api.py"
Task: "Test vitest ComparisonTable dans frontend/components/charts/ComparisonTable.test.tsx"
Task: "Test vitest récurrence de segment dans frontend/lib/utils/ranking.test.ts"
```

---

## Implementation Strategy

### MVP first (User Story 1 seule)

1. Setup (Phase 1) — pas de Foundational à part.
2. Phase 3 (US1) : progression individuelle.
3. **Valider indépendamment** avant de poursuivre.

### Livraison séquentielle (choix retenu pour cette PR)

US1 → US2 → US3 → US4 → US5 → US6 → US7 → US8 → US9 → US10 → US11 → US12 →
US13 → Polish. Chaque checkpoint est un point d'arrêt possible sans casser ce
qui précède — la PR parapluie reste mergeable à tout checkpoint si le
périmètre devait se réduire en cours de route.
