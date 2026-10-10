# Tasks: Groupes d'entraînement, inscription d'office et séances récurrentes

**Input**: `specs/20261010-122023-groupes-seances-recurrentes/` (plan.md, spec.md, research.md, data-model.md, contracts/api.md)

**Tests**: obligatoires (Principe III, TDD sans réseau). Dans chaque phase, la tâche de test précède la tâche d'implémentation qu'elle couvre et doit échouer avant elle.

**Préalable**: #1290 fusionnée, branche rebasée sur `main` (research R7).

## Phase 1: Setup

- [ ] T001 Rebaser `feat/1291-training-groups` sur `origin/main` après fusion de #1290 et vérifier que `cd backend && uv run pytest -m "not integration"` et `cd frontend && npm test` passent avant toute modification

## Phase 2: Foundational (bloquant pour toutes les stories)

- [ ] T002 Écrire les tests de modèle (contraintes d'unicité groupe/nom par organisation, membre unique par groupe, colonnes `recurrence_id`, `detached`, `added_manually` avec leurs défauts) dans backend/tests/test_repositories/test_training_group_repository.py
- [ ] T003 Créer `TrainingGroup` et `TrainingGroupMember` dans backend/app/models/training_group.py, `TrainingRecurrence` et les tables d'association `training_recurrence_groups` et `training_session_groups` dans backend/app/models/training_recurrence.py, ajouter `recurrence_id`, `detached`, relation `groups` dans backend/app/models/training_session.py et `added_manually` (défaut vrai) dans backend/app/models/training_participant.py, enregistrer les modèles dans backend/app/models/__init__.py
- [ ] T004 Générer et relire la migration Alembic `training_groups_and_recurrences` dans backend/alembic/versions/ (`server_default` vrai pour `added_manually`, faux pour `detached`), vérifier `uv run alembic upgrade head` puis `downgrade -1` sur SQLite
- [ ] T005 [P] Écrire les tests de la catégorie FFTri (oracle research R1 : saison 2026 = Mini-poussins 2018-2019 … Juniors 2006-2007, bascule au 1er novembre, `None` sans date de naissance, « Moins de 6 ans », « Senior ») dans backend/tests/test_services/test_fftri_category.py
- [ ] T006 [P] Implémenter `fftri_category(birth_date, on)` avec la constante de mois de bascule marquée `ponytail:` dans backend/app/services/fftri_category.py
- [ ] T007 Écrire les tests de la purge de rétention qui retire aussi les appartenances de groupe du profil purgé dans backend/tests/test_services/test_retention_service.py
- [ ] T008 Ajouter `delete_memberships_of_profile` dans backend/app/repositories/training_group_repository.py et l'appeler dans la purge dans backend/app/services/retention_service.py, à côté de `delete_participations_of_profile`

**Checkpoint**: schéma migré, catégorie calculable, purge propre.

## Phase 3: User Story 1, constituer des groupes (P1) 🎯 MVP

**Goal**: créer, renommer, supprimer un groupe ; ajouter et retirer des membres ; voir les groupes d'un profil.

**Independent Test**: créer un groupe, y ajouter trois profils, en retirer un ; la fiche de chaque profil liste ses groupes.

- [ ] T009 [P] [US1] Écrire les tests du dépôt (liste triée par nom avec nombre de membres, ajout idempotent, retrait, groupes d'un profil) dans backend/tests/test_repositories/test_training_group_repository.py
- [ ] T010 [US1] Implémenter backend/app/repositories/training_group_repository.py
- [ ] T011 [P] [US1] Écrire les tests du service (nom vide ou déjà pris refusé en `DomainError` français, profil absent en 404, suppression qui laisse en place les inscriptions déjà produites) dans backend/tests/test_services/test_training_group_service.py
- [ ] T012 [US1] Implémenter backend/app/services/training_group_service.py (sans la resynchronisation, ajoutée en US2)
- [ ] T013 [P] [US1] Écrire les tests d'API (gardes 401/403 lecture et écriture, contrat de contracts/api.md section Groupes) dans backend/tests/test_api/test_admin_training_groups.py
- [ ] T014 [US1] Implémenter backend/app/api/v1/admin_training_groups.py et l'enregistrer dans backend/app/api/v1/router.py
- [ ] T015 [P] [US1] Écrire les tests des vues profil (`category` dans `ProfileRead`, `groups` dans `ProfileDetailRead`) dans backend/tests/test_auth/test_admin_profiles_api.py
- [ ] T016 [US1] Étendre `profile_view` et `profile_detail_view` dans backend/app/services/profile_service.py et les schémas de réponse de backend/app/api/v1/admin_profiles.py
- [ ] T017 [P] [US1] Ajouter types et appels API (groupes, `category`, `groups`) dans frontend/lib/types.ts et frontend/lib/api/client.ts
- [ ] T018 [P] [US1] Écrire les tests de l'écran groupes (liste, création, renommage refusé, suppression confirmée par `useDangerConfirm`, lecture seule sans `jeunes:write`, état d'erreur distinct de l'état vide) dans frontend/components/admin/jeunes/GroupesList.test.tsx
- [ ] T019 [US1] Implémenter frontend/components/admin/jeunes/GroupesList.tsx, frontend/components/admin/jeunes/GroupeDetail.tsx et la page frontend/app/admin/jeunes/groupes/page.tsx (mobile-first, 375 px sans défilement horizontal)
- [ ] T020 [US1] Ajouter l'entrée « Groupes » à la section « Jeunes » (permission `jeunes:read`, `helpAnchor: "jeunes"`) dans frontend/components/layout/nav.config.ts et faire passer frontend/components/layout/nav.config.test.ts
- [ ] T021 [P] [US1] Écrire les tests de la fiche profil (section « Groupes », ajout et retrait depuis la fiche) dans frontend/components/admin/ProfileDetail.test.tsx
- [ ] T022 [US1] Ajouter la section « Groupes » dans frontend/components/admin/ProfileDetail.tsx

**Checkpoint**: US1 utilisable seule.

## Phase 4: User Story 2, inscription d'office (P1)

**Goal**: une séance vise des groupes, leurs membres actifs y sont inscrits, et les séances à venir non pointées suivent la composition des groupes.

**Independent Test**: créer une séance visant un groupe de trois membres ; l'appel liste les trois sans ajout manuel.

- [ ] T023 [P] [US2] Écrire les tests de `sync_group_enrolment` (US2.1 à US2.5, FR-005, FR-006, FR-017 : membre partagé inscrit une fois, ajout manuel conservé, séance passée ou pointée intacte, adhésion terminée non inscrite) dans backend/tests/test_services/test_training_session_service.py
- [ ] T024 [US2] Ajouter les requêtes nécessaires (séances à venir visant un groupe, présence saisie sur une séance) dans backend/app/repositories/training_session_repository.py et implémenter `sync_group_enrolment` dans backend/app/services/training_session_service.py ; l'ajout manuel pose `added_manually=True`
- [ ] T025 [US2] Appeler la resynchronisation des séances concernées après ajout et retrait de membre dans backend/app/services/training_group_service.py, test dans backend/tests/test_services/test_training_group_service.py
- [ ] T026 [P] [US2] Écrire les tests d'API séances (`group_ids` à la création et au PATCH, `added_manually` et `category` sur les participants, `group_ids` absent au PATCH = inchangé) dans backend/tests/test_api/test_admin_training_sessions.py
- [ ] T027 [US2] Étendre les schémas et routes de backend/app/api/v1/admin_training_sessions.py et les vues de backend/app/services/training_session_service.py
- [ ] T028 [P] [US2] Écrire les tests du sélecteur de groupes et de la fenêtre de séance (choix multiple, inscrits mis à jour après enregistrement) dans frontend/components/admin/jeunes/EntrainementDetailDialog.test.tsx
- [ ] T029 [US2] Implémenter frontend/components/admin/jeunes/GroupesPicker.tsx et l'utiliser dans frontend/components/admin/jeunes/EntrainementForm.tsx et frontend/components/admin/jeunes/EntrainementDetailDialog.tsx (utilisable à 375 px)
- [ ] T030 [P] [US2] Écrire les tests de la création rapide de la séance du jour avec choix des groupes (FR-019) dans frontend/app/admin/jeunes/appel/page.test.tsx
- [ ] T031 [US2] Proposer les groupes dans la création de la séance du jour sur frontend/app/admin/jeunes/appel/page.tsx

**Checkpoint**: US1 et US2 utilisables ; SC-001 vérifiable.

## Phase 5: User Story 3, séances récurrentes (P2)

**Goal**: générer les séances hebdomadaires d'une période, modifier et supprimer la récurrence sans toucher aux séances passées, pointées ou modifiées seules.

**Independent Test**: récurrence mercredi 14 h du 1er octobre au 30 novembre ; une séance par mercredi, inscrits des groupes visés.

- [ ] T032 [P] [US3] Écrire les tests de génération de dates (jour de semaine, bornes incluses, 0 et 54 occurrences refusées) dans backend/tests/test_services/test_training_recurrence_service.py
- [ ] T033 [US3] Implémenter backend/app/repositories/training_recurrence_repository.py et la génération, l'aperçu et la création dans backend/app/services/training_recurrence_service.py (séances créées puis `sync_group_enrolment`)
- [ ] T034 [P] [US3] Écrire les tests de modification et suppression (R4 : séances synchronisables non détachées mises à jour, dates retirées supprimées, dates nouvelles créées ; suppression avec `deleted_session_count` et `kept_session_count` ; séance PATCHée seule passée `detached`) dans backend/tests/test_services/test_training_recurrence_service.py
- [ ] T035 [US3] Implémenter modification et suppression dans backend/app/services/training_recurrence_service.py, et le passage `detached=True` au PATCH d'une séance générée dans backend/app/services/training_session_service.py
- [ ] T036 [P] [US3] Écrire les tests d'API récurrences (gardes, aperçu, création, modification, suppression, contrat de contracts/api.md) dans backend/tests/test_api/test_admin_training_recurrences.py
- [ ] T037 [US3] Implémenter backend/app/api/v1/admin_training_recurrences.py et l'enregistrer dans backend/app/api/v1/router.py
- [ ] T038 [P] [US3] Ajouter types et appels API des récurrences dans frontend/lib/types.ts et frontend/lib/api/client.ts
- [ ] T039 [P] [US3] Écrire les tests du formulaire de récurrence (nombre de séances annoncé avant validation via l'aperçu, refus lisible, suppression confirmée avec le nombre de séances à venir) dans frontend/components/admin/jeunes/RecurrenceForm.test.tsx
- [ ] T040 [US3] Implémenter frontend/components/admin/jeunes/RecurrenceForm.tsx et la liste des récurrences dans frontend/components/admin/jeunes/CalendrierEntrainements.tsx (utilisables à 375 px)

**Checkpoint**: SC-002 vérifiable.

## Phase 6: User Story 4, catégorie FFTri (P3)

**Goal**: catégorie affichée dans la liste, la fiche et l'appel ; filtre par catégorie.

**Independent Test**: un profil né en 2013 affiche « Benjamin » en saison 2026 ; filtre « Pupille ».

- [ ] T041 [P] [US4] Écrire les tests de la liste (catégorie affichée, « Catégorie inconnue », filtre) dans frontend/components/admin/ProfilesList.test.tsx
- [ ] T042 [US4] Afficher la catégorie et le filtre dans frontend/components/admin/ProfilesList.tsx, et la catégorie dans frontend/components/admin/ProfileDetail.tsx et frontend/components/admin/jeunes/AppelPresence.tsx

## Phase 7: Polish

- [ ] T043 [P] Documenter groupes, inscription d'office et récurrences dans la section « jeunes » du guide admin frontend/components/guide/guide-content.admin.ts
- [ ] T044 [P] Ajouter une ligne sur les groupes et la synchronisation R3 dans backend/AGENTS.md (inventaire des modules)
- [ ] T045 Lancer `uv run pytest -m "not integration"`, `uv run ruff check .`, `npm test`, `npm run lint`, `npx tsc --noEmit`, puis dérouler quickstart.md

## Dependencies & Execution Order

- Setup → Foundational → US1 → US2 → US3 ; US4 ne dépend que de la Foundational (T006) et peut se faire en parallèle de US2 ou US3.
- US2 dépend de US1 (groupes). US3 dépend de US2 (`sync_group_enrolment`).
- Dans chaque story : tests, dépôt, service, API, client front, écran.

## Parallel Example: User Story 1

```text
T009, T011, T013, T015 (tests backend, fichiers distincts) en parallèle ;
T017 et T018 (client et tests front) en parallèle des tâches backend.
```

## Implementation Strategy

MVP = Phases 1 à 4 (groupes et inscription d'office : le gain principal de SC-001). US3 puis US4 en incréments, une PR unique pour la feature, un commit par tâche ou groupe de tâches cohérent.
