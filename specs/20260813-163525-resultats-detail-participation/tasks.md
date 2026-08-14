---
description: "Task list for feature implementation"
---

# Tasks: Page de résultats détaillée d'une participation

**Input**: Design documents from `/specs/20260813-163525-resultats-detail-participation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/get-participation-stats.md, quickstart.md

**Tests**: Le Principe III de la constitution est **non-négociable** — TDD sans
réseau. Chaque user story ouvre par ses tâches de test, qui doivent échouer
avant l'implémentation. Backend : `uv run pytest -m "not integration"`.
Frontend : `npm test` (vitest + RTL, tests colocalisés `*.test.tsx`).

**Organization**: Tâches groupées par user story pour permettre une
implémentation et une validation indépendantes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallélisable (fichiers distincts, pas de dépendance ouverte)
- **[Story]**: user story de rattachement (US1, US2, US3)
- Chemins de fichiers exacts dans chaque description

## Path Conventions

Monorepo web existant : `backend/app/`, `backend/tests/`, `frontend/`.
Aucune migration Alembic, aucune nouvelle dépendance (cf. plan.md).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: partir d'une base verte — la feature n'ajoute ni dépendance ni
migration, le setup se réduit à la vérification de départ.

- [X] T001 Vérifier la base verte avant tout code : `cd backend && uv run pytest -m "not integration"` puis `cd frontend && npm test`, et consigner le nombre de tests au vert comme référence

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: règle d'éligibilité, enveloppe de contrat, coquille de page et
état « statistiques indisponibles » — tout ce dont les trois stories dépendent.

**⚠️ CRITICAL**: aucune user story ne peut démarrer avant la fin de cette phase.

### Tests (écrire en premier, doivent échouer)

- [X] T002 [P] Écrire les tests de la règle d'éligibilité dans `backend/tests/test_core/test_splits_reliability.py` : `has_reliable_splits` faux pour `None`, `"manuel"`, `"t2area"`, `"breizhchrono"` ; vrai pour `"raceresult"`, `"klikego"`, `"oktime"` ; `is_stats_eligible(course)` délègue au provider de la course
- [X] T003 [P] Écrire les tests d'enveloppe du service dans `backend/tests/test_services/test_participation_stats_service.py` : `build(...)` retourne `None` si la course n'est pas éligible, `None` si `participation.is_relay` est vrai, et un objet non nul (blocs vides admis à ce stade) sur une course éligible — fakes `types.SimpleNamespace`, sans session DB (research.md §6)
- [X] T004 [P] Étendre `backend/tests/test_api/test_participations_api.py` : `GET /api/v1/participations/{id}` expose `stats` à `null` pour une course non éligible et pour un relais ; expose un `stats` **peuplé** (trois blocs présents, forme conforme à `contracts/get-participation-stats.md`) sur une course éligible, **y compris pour une participation non-TCN** (FR-004) ; les champs existants de `ParticipationOut` restent inchangés, et le champ apparaît à `null` sur `GET /courses/{id}` sans déclencher de calcul (Principe IV)
- [X] T005 [P] Écrire le test de la coquille de page dans `frontend/app/courses/[id]/participations/[participationId]/page.test.tsx` : rendu de l'état « statistiques indisponibles » quand `stats` vaut `null` (message explicatif + lien de retour, aucun tableau ni graphique), et `notFound()` quand `participation.course.id` diffère du `courseId` de l'URL

### Implémentation

- [X] T006 Créer `backend/app/core/splits_reliability.py` : `UNRELIABLE_SPLIT_PROVIDERS: frozenset[str] = {"t2area", "breizhchrono"}`, `has_reliable_splits(provider: str | None) -> bool`, `is_stats_eligible(course) -> bool` — module miroir de `backend/app/core/club.py`, point d'entrée unique du prédicat (data-model.md §Règle métier)
- [X] T007 [P] Créer `backend/app/schemas/participation_stats.py` : `RankingEvolutionStep`, `ComparisonRow`, `ImprovementRow`, `ParticipationStatsOut` conformes à data-model.md §Value objects
- [X] T008 Ajouter `stats: ParticipationStatsOut | None = None` à `ParticipationOut` dans `backend/app/schemas/participation.py` (champ additif, aucun champ existant touché)
- [X] T009 Créer `backend/app/services/participation_stats_service.py` avec `build(db, participation)` : sort `None` si `not is_stats_eligible(participation.course)` ou `participation.is_relay`, sinon charge le classement via `participation_repository.list_for_course(db, course_id)` et retourne une enveloppe aux trois blocs vides ; y placer le helper de segments publiés (FR-013 — dérivé des clés réellement présentes dans les `splits` du classement, pas d'une liste figée) et réutiliser `to_seconds` / `fmt_seconds` de `backend/app/scrapers/utils.py`
- [X] T010 Câbler `stats` dans le handler `get_participation` de `backend/app/api/v1/participations.py` en déléguant au service (le router reste fin, aucune requête SQL ajoutée — Principe II) ; `GET /courses/{id}` reste inchangé
- [X] T011 [P] Déclarer les types `ParticipationStats`, `RankingEvolutionStep`, `ComparisonRow`, `ImprovementRow` et le champ `stats` sur `Participation` dans `frontend/lib/types.ts`
- [X] T012 [P] Ajouter `getParticipation(id)` à `apiServer` dans `frontend/lib/api/server.ts` (méthode absente à ce jour)
- [X] T013 Créer `frontend/components/tcn/participation-detail/UnavailableState.tsx` : message générique expliquant que les statistiques détaillées ne s'affichent que si l'intégralité des résultats du chronométreur a pu être récupérée, avec lien de retour vers la page de l'athlète (FR-005 — aucun nom de fournisseur affiché)
- [X] T014 Créer la route `frontend/app/courses/[id]/participations/[participationId]/page.tsx` : appel `getParticipation`, `notFound()` si l'ID de course de l'URL ne correspond pas à `participation.course.id` (contracts §404), rendu de `UnavailableState` si `stats` est `null`, et emplacements vides pour les blocs des stories suivantes

**Checkpoint**: la page existe, répond en 404 cohérent, et rend l'état
indisponible ; le contrat API porte `stats` — les trois stories peuvent démarrer.

---

## Phase 3: User Story 1 - Se comparer aux autres coureurs sur sa performance (Priority: P1) 🎯 MVP

**Goal**: depuis une ligne de résultat cliquable, afficher la ligne de
résultat de l'athlète et le tableau de comparaison aux positions de référence
(1er, 10e, 25e, 50e, 100e), segment par segment et sur le total.

**Independent Test**: sur une participation d'une course éligible, la page
affiche le bloc ligne de résultat et le tableau de comparaison, sans graphique
ni simulation — la valeur « comment je me situe » est déjà rendue.

### Tests for User Story 1

> Écrire ces tests d'abord, vérifier qu'ils échouent (Principe III).

- [X] T015 [P] [US1] Tester le calcul de comparaison dans `backend/tests/test_services/test_participation_stats_service.py` : pourcentages par segment et sur `total` face aux rangs 1/10/25/50/100 sur un classement fabriqué ; ligne omise quand le rang de référence dépasse l'effectif (FR-014) ; segment absent chez l'athlète ou chez la référence → pas de pourcentage inventé (FR-007)
- [X] T016 [P] [US1] Tester `frontend/components/tcn/participation-detail/ResultRow.test.tsx` : rang scratch, nom, catégorie, sexe, temps total et splits publiés affichés ; un split absent rend un tiret et jamais `0:00:00` (FR-007) ; disciplines chronométrées visuellement distinctes des transitions (FR-006)
- [X] T017 [P] [US1] Tester `frontend/components/tcn/participation-detail/ComparisonTable.test.tsx` : une ligne par position de référence présente, pourcentages par segment et total, ligne absente quand la position n'existe pas dans le classement (FR-014), colonnes limitées aux segments publiés (FR-013)
- [X] T018 [P] [US1] Étendre `frontend/components/results/RaceFinishers.test.tsx` : le clic sur une ligne de finisher navigue vers `/courses/{courseId}/participations/{participationId}` et non plus vers `/athletes/{athleteId}` (FR-001, research.md §7)
- [X] T019 [P] [US1] Étendre `frontend/app/athletes/[id]/page.test.tsx` : le clic sur une ligne d'épreuve pointe vers `/courses/{courseId}/participations/{participationId}` et non plus vers `/courses/{courseId}` (FR-002)

### Implementation for User Story 1

- [X] T020 [US1] Implémenter le bloc `comparison` dans `backend/app/services/participation_stats_service.py` : pour chaque rang de référence existant dans le classement, temps de l'athlète en pourcentage du temps de la référence par segment publié et sur le total (FR-008, FR-014)
- [X] T021 [P] [US1] Créer `frontend/components/tcn/participation-detail/ResultRow.tsx` (FR-006, FR-007) — jetons de design existants uniquement, transitions en gris atténué (research.md §5), exporté via `frontend/components/tcn/index.ts`
- [X] T022 [P] [US1] Créer `frontend/components/tcn/participation-detail/ComparisonTable.tsx` (FR-008, FR-013, FR-014), exporté via `frontend/components/tcn/index.ts`
- [X] T023 [US1] Monter `ResultRow` et `ComparisonTable` dans `frontend/app/courses/[id]/participations/[participationId]/page.tsx`, avec le retour vers les résultats de l'athlète et l'accès au bouton d'ajout d'un triathlon (FR-015)
- [X] T024 [P] [US1] Rediriger le clic de ligne vers la nouvelle route dans `frontend/components/results/RaceFinishers.tsx` (FR-001 — remplace la navigation vers la fiche athlète, elle n'est pas conservée en parallèle)
- [X] T025 [P] [US1] Rediriger le lien de ligne d'épreuve vers la nouvelle route dans `frontend/app/athletes/[id]/page.tsx` (FR-002 — remplace la navigation vers la page course)

**Checkpoint**: US1 livrable seule — page atteignable en un clic depuis les
deux entrées, ligne de résultat et comparaison rendues (SC-001, SC-002).

---

## Phase 4: User Story 2 - Comprendre l'évolution de son classement au fil de la course (Priority: P2)

**Goal**: graphique d'évolution du classement par étape — position scratch
cumulée (ligne) et position sur le segment isolé (barre), avec infobulle au
survol.

**Independent Test**: sur une participation déjà dotée du bloc US1, le
graphique affiche cinq étapes, meilleure position en haut, et les infobulles
répondent au survol, une seule à la fois.

### Tests for User Story 2

- [X] T026 [P] [US2] Tester le calcul d'évolution dans `backend/tests/test_services/test_participation_stats_service.py` : `scratch_position` cumulée à la sortie de chaque étape et `segment_position` sur l'étape isolée, sur un classement fabriqué ; une entrée par segment publié uniquement (FR-013) ; cohérence avec le classement de l'app — `ranking_evolution[-1].scratch_position == participation.rank_overall` (SC-005)
- [X] T027 [P] [US2] Tester `frontend/components/tcn/participation-detail/RankingEvolutionChart.test.tsx` : cinq étapes rendues avec ligne scratch et barres de segment, axe des ordonnées inversé (meilleure position en haut, FR-009), bornes calculées depuis min/max des positions avec marge (spec.md §Assumptions), et infobulle au survol affichant nom d'étape + position, une seule visible à la fois (FR-010)

### Implementation for User Story 2

- [X] T028 [US2] Implémenter le bloc `ranking_evolution` dans `backend/app/services/participation_stats_service.py` (FR-009)
- [X] T029 [US2] Créer `frontend/components/tcn/participation-detail/RankingEvolutionChart.tsx` : SVG à la main sur le patron du `Histogram` de `frontend/app/courses/[id]/page.tsx`, `viewBox` fixe et `width: 100%`, infobulle positionnée adaptativement gauche/droite (research.md §4) — aucune librairie de charting ajoutée
- [X] T030 [US2] Monter `RankingEvolutionChart` dans `frontend/app/courses/[id]/participations/[participationId]/page.tsx`

**Checkpoint**: US1 et US2 fonctionnent indépendamment sur la même page.

---

## Phase 5: User Story 3 - Estimer le gain de classement d'une amélioration ciblée (Priority: P3)

**Goal**: tableau croisant les cinq segments et six pourcentages
d'amélioration, donnant le nombre de places scratch gagnées.

**Independent Test**: sur une participation déjà dotée des blocs US1 et US2, le
tableau 5 segments × 6 pourcentages s'affiche et chaque cellule se recoupe avec
un recalcul manuel depuis le classement complet.

### Tests for User Story 3

- [X] T031 [P] [US3] Tester le calcul de simulation dans `backend/tests/test_services/test_participation_stats_service.py` : pour chaque segment publié et chacun des pourcentages `0.5`, `1`, `2`, `5`, `10`, `25`, nombre de places scratch gagnées avec le temps total recalculé, toutes choses égales par ailleurs (FR-011) ; gain nul admis, jamais négatif
- [X] T032 [P] [US3] Tester `frontend/components/tcn/participation-detail/ImprovementMatrix.test.tsx` : une ligne par segment publié, six colonnes de pourcentage, valeurs rendues telles que fournies par l'API

### Implementation for User Story 3

- [X] T033 [US3] Implémenter le bloc `improvement` dans `backend/app/services/participation_stats_service.py` (FR-011)
- [X] T034 [US3] Créer `frontend/components/tcn/participation-detail/ImprovementMatrix.tsx` (FR-011, FR-013), exporté via `frontend/components/tcn/index.ts`
- [X] T035 [US3] Monter `ImprovementMatrix` dans `frontend/app/courses/[id]/participations/[participationId]/page.tsx`

**Checkpoint**: les trois user stories sont fonctionnelles indépendamment.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T036 Ajouter un test d'assemblage bout en bout avec `db_session` dans `backend/tests/test_services/test_participation_stats_service.py`, sur les helpers `_seed`/`_epreuve` de `backend/tests/test_services/test_stats_service.py` : repository → service → forme de sortie complète (research.md §6)
- [X] T037 [P] Documenter le champ `stats` de `GET /participations/{id}` et la règle d'éligibilité dans `backend/app/api/AGENTS.md`
- [X] T038 Vérifier SC-003 sur une course de 300+ finishers : mesurer `GET /api/v1/participations/{id}` côté serveur (< 500 ms) et le rendu complet de la page (< 2 s), et confirmer un seul `SELECT` de classement par requête via l'observabilité SQL (`backend/app/core/`, cf. `backend/app/core/AGENTS.md`) — aucun N+1 introduit
- [X] T039 Dérouler `specs/20260813-163525-resultats-detail-participation/quickstart.md` (scénarios 1, 2 et 3) sur les serveurs de dev
- [X] T040 Suite complète au vert : `cd backend && uv run pytest -m "not integration"` et `uv run ruff check .`, puis `cd frontend && npm test`, `npm run lint`, `npm run build`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** : aucune dépendance
- **Foundational (Phase 2)** : dépend du Setup — **bloque** toutes les stories
- **US1 (Phase 3)**, **US2 (Phase 4)**, **US3 (Phase 5)** : dépendent de la Phase 2, indépendantes entre elles
- **Polish (Phase 6)** : dépend des stories livrées

### User Story Dependencies

- **US1 (P1)** : démarre après la Phase 2, aucune dépendance sur US2/US3
- **US2 (P2)** : démarre après la Phase 2 ; s'insère dans la même page que US1 mais se teste seule
- **US3 (P3)** : démarre après la Phase 2 ; même remarque

### Within Each User Story

- Tests écrits et en échec avant implémentation (Principe III)
- Calcul backend avant composant frontend qui le consomme
- Composants avant leur montage dans `page.tsx`
- T023, T030 et T035 touchent le **même fichier** `page.tsx` — à sérialiser si les stories sont menées en parallèle

### Parallel Opportunities

- T002, T003, T004, T005 en parallèle (quatre fichiers de test distincts)
- T007, T011, T012 en parallèle après T006
- Tous les tests d'une même story marqués [P] en parallèle
- T021, T022 en parallèle ; T024, T025 en parallèle
- Les trois stories peuvent être menées par trois personnes, sous réserve de la sérialisation de `page.tsx` ci-dessus et du fichier de service partagé (T020, T028, T033)

---

## Parallel Example: User Story 1

```bash
# Tests d'abord, en parallèle :
Task: "Test du calcul de comparaison dans backend/tests/test_services/test_participation_stats_service.py"
Task: "Test de ResultRow dans frontend/components/tcn/participation-detail/ResultRow.test.tsx"
Task: "Test de ComparisonTable dans frontend/components/tcn/participation-detail/ComparisonTable.test.tsx"
Task: "Test de navigation dans frontend/components/results/RaceFinishers.test.tsx"
Task: "Test de navigation dans frontend/app/athletes/[id]/page.test.tsx"

# Puis composants en parallèle :
Task: "Créer frontend/components/tcn/participation-detail/ResultRow.tsx"
Task: "Créer frontend/components/tcn/participation-detail/ComparisonTable.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 seule)

1. Phase 1 : Setup
2. Phase 2 : Foundational (bloquante)
3. Phase 3 : US1
4. **STOP et VALIDER** : scénario 1 du quickstart limité aux blocs ligne de résultat et comparaison, plus scénarios 2 et 3 (états indisponibles)
5. Déployer / démontrer

### Incremental Delivery

1. Setup + Foundational → page atteignable, contrat étendu, état indisponible rendu
2. + US1 → valeur centrale de l'issue #272 livrée (MVP)
3. + US2 → lecture temporelle du classement
4. + US3 → simulation prospective
5. Polish → doc, perf, suite complète

---

## Phase 7 : Retours de revue (PR #326)

Remarques d'usage relevées en rendu réel après livraison. Chacune amende la
spec au FR indiqué — les tâches ci-dessus restent le journal de la livraison
initiale, elles ne sont pas réécrites.

- [X] T034 Deux retours dans la page (`page.tsx`) — course **et** athlète, rendus dans les deux états ; le lien de retour interne à `UnavailableState` disparaît, il faisait doublon (FR-005, FR-015)
- [X] T035 Suppression de l'action « Ajouter un triathlon » de l'en-tête (FR-015)
- [X] T036 Nom de la course et nom de l'athlète cliquables vers leurs pages (`page.tsx`, `ResultRow.tsx`) (FR-015)
- [X] T037 Position sur chaque segment isolé dans la ligne de résultat (`ResultRow.tsx`), alimentée par `ranking_evolution` (FR-006)
- [X] T038 Graphique ramené à un bandeau, axe des positions gradué, légende des deux séries (`RankingEvolutionChart.tsx`) (FR-009)
- [X] T039 Tableau de simulation : phrase d'intro, gains signés, segments stériles sortis du tableau et nommés en une phrase (`ImprovementMatrix.tsx`) (FR-011)
- [X] T040 Colonne « Position » du tableau de comparaison ramenée à sa largeur utile (`ComparisonTable.tsx`) (FR-008)

---

## Notes

- Aucune migration Alembic, aucune nouvelle dépendance backend ou frontend
- `GET /courses/{id}` n'est jamais modifié : `stats` ne se calcule que pour la lecture d'**une** participation (contracts §Rétrocompatibilité)
- La liste `UNRELIABLE_SPLIT_PROVIDERS` est une liste d'**exclusion** : un nouveau fournisseur est éligible par défaut (research.md §1)
- Le trou de doc `breizhchrono` (splits fins réservés aux membres TCN, non documenté dans `docs/scrapers/`) est signalé par research.md §1 mais **hors périmètre** de cette branche
- Commit après chaque tâche ou groupe logique
