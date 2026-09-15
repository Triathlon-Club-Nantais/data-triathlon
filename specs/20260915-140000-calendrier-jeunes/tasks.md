# Tasks: Calendrier des entraînements jeunes

**Input**: Design documents from `/specs/20260915-140000-calendrier-jeunes/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Principe III (TDD sans réseau, non-négociable) — chaque capacité
backend et frontend est précédée d'un test qui échoue avant l'implémentation.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

Aucune tâche : le projet, ses dépendances et son outillage existent déjà
(`backend/`, `frontend/`).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose** : le modèle de données et le socle de garde, dont dépendent les
trois user stories.

**⚠️ CRITICAL**: aucune user story ne démarre avant la fin de cette phase.

- [X] T001 [P] Modèle `Entrainement` dans `backend/app/models/entrainement.py`
      (`date`, `heure_debut`, `lieu`, `type_seance`, `created_at`, relation
      `participants` en cascade `delete-orphan` — cf. `data-model.md`)
- [X] T002 [P] Modèle `EntrainementParticipant` dans
      `backend/app/models/entrainement_participant.py` (`entrainement_id` FK,
      `jeune_id` `Integer` **sans FK** pour ce lot — cf. `research.md`
      §Dépendance, `UNIQUE(entrainement_id, jeune_id)`)
- [X] T003 Migration Alembic (`uv run alembic revision --autogenerate -m
      "add entrainements_jeunes"` puis relecture manuelle de la révision
      générée, `backend/alembic/versions/`) (dépend de T001, T002)
- [X] T004 [P] Schémas Pydantic dans `backend/app/schemas/entrainement.py` :
      `EntrainementRead`, `EntrainementDetailRead`, `EntrainementCreate`,
      `EntrainementUpdate`, `ParticipantRead`, `ParticipantAdd`
- [X] T005 Router vide `backend/app/api/v1/admin_jeunes_entrainements.py`
      (`APIRouter(tags=["admin"])`) et son enregistrement dans
      `backend/app/api/v1/router.py` (groupe gardé par `require_site_access`,
      aux côtés d'`admin_groups`)
- [X] T006 Retirer l'entrée `"jeunes:read"` de `GARDE_A_VENIR` dans
      `backend/tests/test_permissions_catalogue.py` — **vérifier d'abord
      l'état courant du fichier** : si la sous-issue parallèle #867 l'a déjà
      retirée, ne rien faire ici (pas de conflit à créer). Sera de toute façon
      vérifié à l'ouverture de la PR (cf. instructions de la tâche).

**Checkpoint**: modèle et migration en place, `uv run alembic upgrade head`
réussit, `uv run pytest -m "not integration"` toujours vert avant toute user
story.

---

## Phase 3: User Story 1 - Consulter le calendrier des entraînements (Priority: P1) 🎯 MVP

**Goal**: un porteur de `jeunes:read` voit la liste des entraînements, triée
par date, avec leur nombre d'inscrits, et le détail d'un entraînement avec sa
liste de participants.

**Independent Test**: créer trois entraînements en base (via une fixture de
test ou l'API), vérifier qu'ils s'affichent triés par date sur l'écran
calendrier, avec les champs optionnels absents rendus proprement.

### Tests for User Story 1

- [X] T007 [P] [US1] Test repository `list_all`/`get`/`participant_count`/
      `list_participants` (tri par date puis heure, entraînement sans heure en
      fin de liste, compteur exact, liste de participants vide par défaut)
      dans `backend/tests/test_repositories/test_entrainement_repository.py`
- [X] T008 [P] [US1] Test service `list_view`/`detail_view` (formatage,
      `participant_count`, 404 sur un id inconnu) dans
      `backend/tests/test_services/test_entrainements_jeunes.py`
- [X] T009 [P] [US1] Test API `GET /admin/jeunes/entrainements` et
      `GET /admin/jeunes/entrainements/{id}` — 401 sans session, 403 sans
      `jeunes:read`, 200 avec, 404 sur id inconnu — dans
      `backend/tests/test_api/test_admin_jeunes_entrainements.py`
- [X] T010 [P] [US1] Test composant `CalendrierEntrainements` (liste triée,
      champs optionnels absents sans texte vide, aucune commande d'écriture
      sans `jeunes:write`) dans
      `frontend/components/admin/jeunes/CalendrierEntrainements.test.tsx`

### Implementation for User Story 1

- [X] T011 [US1] Implémenter `list_all`/`get`/`participant_count`/
      `list_participants` dans
      `backend/app/repositories/entrainement_repository.py` (fait passer T007)
- [X] T012 [US1] Implémenter `list_view`/`detail_view`/`get_entrainement_or_404`
      dans `backend/app/services/jeunes/entrainements.py` (fait passer T008 ;
      dépend de T011)
- [X] T013 [US1] Implémenter les deux routes `GET` dans
      `backend/app/api/v1/admin_jeunes_entrainements.py`, gardées par
      `require_permission(P.JEUNES_READ)` (fait passer T009 ; dépend de T012)
- [X] T014 [P] [US1] Types `Entrainement`/`EntrainementDetail` dans
      `frontend/lib/types.ts` et appels `listEntrainements`/`getEntrainement`
      dans `frontend/lib/api/client.ts`
- [X] T015 [US1] Hooks `useEntrainements`/`useEntrainement` (React Query) dans
      `frontend/lib/queries/admin.ts` (dépend de T014)
- [X] T016 [US1] Composant `CalendrierEntrainements.tsx` (liste, états
      chargement/erreur/vide sur le patron de `GroupsTable`) dans
      `frontend/components/admin/jeunes/CalendrierEntrainements.tsx` (fait
      passer T010 ; dépend de T015)
- [X] T017 [US1] Page `frontend/app/admin/jeunes/calendrier/page.tsx` et
      entrée de navigation « Jeunes » gardée par `jeunes:read` dans
      `frontend/components/layout/nav.config.ts` (dépend de T016)

**Checkpoint**: US1 fonctionnelle et testable seule — le calendrier consulte
des entraînements créés directement en base ou par un script, sans écran de
création.

---

## Phase 4: User Story 2 - Créer et modifier une séance d'entraînement (Priority: P2)

**Goal**: un porteur de `jeunes:write` crée une séance depuis l'écran, et
corrige une séance existante.

**Independent Test**: créer une séance par le formulaire, vérifier qu'elle
apparaît dans la liste (US1) avec zéro participant, la modifier, vérifier que
la correction s'affiche sans doublon.

### Tests for User Story 2

- [X] T018 [P] [US2] Test repository `create`/`update` (champs partiels sur
      `update`, champs absents non écrasés) dans
      `backend/tests/test_repositories/test_entrainement_repository.py`
- [X] T019 [P] [US2] Test service `create_entrainement`/`update_entrainement`
      dans `backend/tests/test_services/test_entrainements_jeunes.py`
- [X] T020 [P] [US2] Test API `POST`/`PATCH /admin/jeunes/entrainements` — 403
      pour un porteur du seul `jeunes:read`, 201/200 pour `jeunes:write`, 422
      sans `date` à la création, 404 sur `PATCH` d'un id inconnu — dans
      `backend/tests/test_api/test_admin_jeunes_entrainements.py`
- [X] T021 [P] [US2] Test composant `EntrainementForm` (soumission, champs
      optionnels, désactivé/masqué pendant l'envoi) dans
      `frontend/components/admin/jeunes/EntrainementForm.test.tsx`

### Implementation for User Story 2

- [X] T022 [US2] Implémenter `create`/`update` dans
      `backend/app/repositories/entrainement_repository.py` (fait passer T018)
- [X] T023 [US2] Implémenter `create_entrainement`/`update_entrainement` dans
      `backend/app/services/jeunes/entrainements.py` (fait passer T019 ;
      dépend de T022)
- [X] T024 [US2] Implémenter `POST`/`PATCH` dans
      `backend/app/api/v1/admin_jeunes_entrainements.py`, gardées par
      `require_permission(P.JEUNES_WRITE)` (fait passer T020 ; dépend de T023)
- [X] T025 [US2] Retirer l'entrée `"jeunes:write"` de `GARDE_A_VENIR` dans
      `backend/tests/test_permissions_catalogue.py` **si elle porte encore
      la seule mention #869** au moment de l'implémentation — coordination
      documentée dans les instructions de la tâche, à revérifier à l'ouverture
      de la PR (dépend de T024)
- [X] T026 [P] [US2] Appels `createEntrainement`/`updateEntrainement` dans
      `frontend/lib/api/client.ts`
- [X] T027 [US2] Hooks `useCreateEntrainement`/`useUpdateEntrainement`
      (invalidation de `queryKeys.entrainements()`) dans
      `frontend/lib/queries/admin.ts` (dépend de T026)
- [X] T028 [US2] Composant `EntrainementForm.tsx` (date obligatoire,
      heure/lieu/type optionnels) dans
      `frontend/components/admin/jeunes/EntrainementForm.tsx` (fait passer
      T021 ; dépend de T027)
- [X] T029 [US2] Brancher `EntrainementForm` dans `CalendrierEntrainements`
      derrière la garde d'apparence `jeunes:write` (patron `peutEcrire` de
      `GroupsTable`) dans
      `frontend/components/admin/jeunes/CalendrierEntrainements.tsx` (dépend
      de T028 et de T016)

**Checkpoint**: US1 + US2 fonctionnelles ensemble — création et modification
depuis l'écran, toujours sans gestion des participants.

---

## Phase 5: User Story 3 - Gérer la liste des participants inscrits (Priority: P2)

**Goal**: un porteur de `jeunes:write` inscrit/désinscrit un jeune à une
séance ; tout porteur de `jeunes:read` consulte la liste des inscrits.

**Independent Test**: inscrire un jeune (identifiant entier) à une séance,
vérifier qu'il apparaît dans la liste de cette séance et dans aucune autre,
réinscrire le même jeune (aucun doublon), puis le désinscrire.

### Tests for User Story 3

- [X] T030 [P] [US3] Test repository `add_participant` (idempotent),
      `remove_participant` (sans effet si absent) dans
      `backend/tests/test_repositories/test_entrainement_repository.py`
      (`list_participants` déjà posée et testée en US1, T007/T011)
- [X] T031 [P] [US3] Test service `add_participant`/`remove_participant` — 404
      sur entraînement inconnu — dans
      `backend/tests/test_services/test_entrainements_jeunes.py`
- [X] T032 [P] [US3] Test API `POST`/`DELETE
      /admin/jeunes/entrainements/{id}/participants[/{jeune_id}]` — 403 pour
      `jeunes:read` seul, 201/204 pour `jeunes:write`, idempotence des deux
      gestes, 404 sur entraînement inconnu — dans
      `backend/tests/test_api/test_admin_jeunes_entrainements.py`
- [X] T033 [P] [US3] Test composant `ParticipantsList` (liste, inscription,
      désinscription, garde d'écriture) dans
      `frontend/components/admin/jeunes/ParticipantsList.test.tsx`

### Implementation for User Story 3

- [X] T034 [US3] Implémenter `add_participant`/`remove_participant` dans
      `backend/app/repositories/entrainement_repository.py` (fait passer T030)
- [X] T035 [US3] Implémenter `add_participant`/`remove_participant` dans
      `backend/app/services/jeunes/entrainements.py` (fait passer T031 ;
      dépend de T034)
- [X] T036 [US3] Implémenter `POST`/`DELETE .../participants` dans
      `backend/app/api/v1/admin_jeunes_entrainements.py`, gardées par
      `require_permission(P.JEUNES_WRITE)` (fait passer T032 ; dépend de T035)
- [X] T037 [P] [US3] Appels `addParticipant`/`removeParticipant` dans
      `frontend/lib/api/client.ts`
- [X] T038 [US3] Hooks `useAddParticipant`/`useRemoveParticipant` dans
      `frontend/lib/queries/admin.ts` (dépend de T037)
- [X] T039 [US3] Composant `ParticipantsList.tsx` dans
      `frontend/components/admin/jeunes/ParticipantsList.tsx` (fait passer
      T033 ; dépend de T038)
- [X] T040 [US3] Brancher `ParticipantsList` dans le détail d'un entraînement
      (modale ou panneau, patron `GroupDetailDialog`) de
      `CalendrierEntrainements.tsx` (dépend de T039 et de T029)

**Checkpoint**: les trois user stories fonctionnelles ensemble — c'est le
périmètre complet de #868.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T041 [P] `uv run ruff check .` et `uv run pytest -m "not integration"`
      verts (`backend/`)
- [X] T042 [P] `npm run lint`, `npm test` et `npm run build` verts (`frontend/`)
- [X] T043 Valider `quickstart.md` de bout en bout, largeur 375 px sans
      défilement horizontal (SC-003)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)** bloque toutes les user stories.
- **US1 (Phase 3)** peut démarrer dès la Phase 2 terminée.
- **US2 (Phase 4)** dépend de la Phase 2 ; réutilise les composants
  frontend d'US1 (T029 dépend de T016) mais ses tests backend sont
  indépendants d'US1.
- **US3 (Phase 5)** dépend de la Phase 2 ; réutilise le composant frontend
  d'US2 pour le branchement final (T040 dépend de T029) mais ses tests
  backend et repository sont indépendants d'US1/US2.
- **Polish (Phase 6)** après les user stories retenues.

### Parallel Opportunities

- T001/T002 en parallèle (fichiers distincts).
- Les tests marqués `[P]` d'une même phase (T007-T010, T018-T021, T030-T033)
  s'écrivent en parallèle — fichiers distincts, aucune dépendance entre eux.
- US2 et US3 peuvent être implémentées par deux personnes en parallèle après
  US1, leurs backends ne se recoupant pas (repository/service/route touchent
  la même paire de fichiers mais des fonctions disjointes — sérialiser les
  commits sur `entrainement_repository.py`/`entrainements.py`/
  `admin_jeunes_entrainements.py` reste nécessaire si menées en parallèle).

---

## Implementation Strategy

### MVP First

1. Phase 2 (Foundational)
2. Phase 3 (US1) — **STOP and VALIDATE** : calendrier consultable seul
3. Déployer/démontrer si suffisant

### Incremental Delivery

Phase 2 → US1 (MVP) → US2 → US3 → Polish, chaque phase testée et validée
avant la suivante.
