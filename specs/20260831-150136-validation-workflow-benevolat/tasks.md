---

description: "Task list for #779 — workflow de validation admin des actions de bénévolat"

---

# Tasks: Workflow de validation admin des actions de bénévolat

**Input**: Design documents from `specs/20260831-150136-validation-workflow-benevolat/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/admin-volunteer-actions-api.md, quickstart.md

**Tests**: Principe III de la constitution v1.2.0 — TDD sans réseau, non-négociable.

**Organization**: Tasks are grouped by user story (spec.md).

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

Aucune tâche : projet existant.

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: permission, schéma et fonctions repository partagés par les
trois user stories — aucune ne peut être testée sans eux.

### Tests

> **Écrire ces tests d'abord, vérifier qu'ils échouent avant implémentation.**

- [ ] T001 [P] Test repository : `list_pending()` rend uniquement les lignes `status="en_attente"` ; `get()` rend `None` sur id inconnu ; `set_status()` change le statut et le relit dans `backend/tests/test_repositories/test_volunteer_action_repository.py`
- [ ] T002 [P] Test repository : `exists_for_athlete_season` ignore désormais les lignes `"en_attente"`/`"refusee"`, ne compte que `"validee"` dans `backend/tests/test_repositories/test_volunteer_action_repository.py`

### Implementation

- [ ] T003 [P] Ajouter `ATHLETES_VOLUNTEER_VALIDATE` (`"athletes:volunteer_validate"`) dans `backend/app/core/permissions.py` — `FEATURE_ATHLETES`, ajouté à `ALL`
- [ ] T004 [P] Ajouter `AdminVolunteerActionOut` (title/description optionnels) dans `backend/app/schemas/volunteer_action.py`
- [ ] T005 Implémenter `list_pending()`, `get()`, `set_status()` dans `backend/app/repositories/volunteer_action_repository.py` — fait passer T001
- [ ] T006 Modifier `exists_for_athlete_season()` pour filtrer `status == "validee"` dans `backend/app/repositories/volunteer_action_repository.py` — fait passer T002 (depends on T005, même fichier)

**Checkpoint**: fondations posées, les trois user stories peuvent démarrer.

---

## Phase 3: User Story 1 - Un admin consulte les déclarations en attente (Priority: P1)

**Goal**: lister les déclarations `VolunteerAction` en attente.

**Independent Test**: cf. spec.md US1 Acceptance Scenarios 1-2 / quickstart.md Scénarios 1, 4.

### Tests for User Story 1

- [ ] T007 [P] [US1] Test service : `list_pending()` ne rend que les lignes en attente dans `backend/tests/test_services/test_volunteer_action_service.py`
- [ ] T008 [P] [US1] Test API : `GET /admin/volunteer-actions/pending` — `200` liste filtrée (title/description `null` pour une ligne créée par le chemin admin), `403` sans le pouvoir dédié dans `backend/tests/test_api/test_admin_volunteer_actions_api.py` (NEW)

### Implementation for User Story 1

- [ ] T009 [US1] Implémenter `volunteer_action_service.list_pending()` dans `backend/app/services/volunteer_action_service.py` — fait passer T007 (depends on T005)
- [ ] T010 [US1] Créer le router `backend/app/api/v1/admin_volunteer_actions.py` (NEW) avec `GET /admin/volunteer-actions/pending`, gardé par `require_permission(P.ATHLETES_VOLUNTEER_VALIDATE)` — fait passer T008 (depends on T009, T004, T003)
- [ ] T011 [US1] Enregistrer le nouveau router dans `backend/app/api/v1/router.py` (depends on T010)

**Checkpoint**: US1 fonctionnelle et testable.

---

## Phase 4: User Story 2 - Un admin accepte une déclaration en attente (Priority: P1)

**Goal**: accepter une déclaration, idempotent, effet visible sur le quota.

**Independent Test**: cf. spec.md US2 Acceptance Scenarios 1-3 / quickstart.md Scénario 2.

### Tests for User Story 2

- [ ] T012 [P] [US2] Test service : `accept()` fait passer `"en_attente"` → `"validee"` ; no-op (pas d'erreur, pas de transition) si déjà `"validee"` **ou** si `"refusee"` (`/speckit-analyze` finding U1) ; `NotFoundError` si id inconnu dans `backend/tests/test_services/test_volunteer_action_service.py`
- [ ] T013 [P] [US2] Test API : `POST /admin/volunteer-actions/{id}/accept` — `200` statut `"validee"`, `404` id inconnu, `403` sans pouvoir, et `GET .../season-quota` reflète `has_volunteer_action: true` après acceptation dans `backend/tests/test_api/test_admin_volunteer_actions_api.py`

### Implementation for User Story 2

- [ ] T014 [US2] Implémenter `volunteer_action_service.accept()` (transition uniquement depuis `"en_attente"` ; no-op pour tout autre statut de départ, journalise seulement la vraie transition) dans `backend/app/services/volunteer_action_service.py` — fait passer T012 (depends on T005, T006)
- [ ] T015 [US2] Ajouter `POST /admin/volunteer-actions/{action_id}/accept` au router `admin_volunteer_actions.py` — fait passer T013 (depends on T014, T010)

**Checkpoint**: US1 et US2 fonctionnelles.

---

## Phase 5: User Story 3 - Un admin refuse une déclaration en attente (Priority: P2)

**Goal**: refuser une déclaration (y compris déjà validée), idempotent.

**Independent Test**: cf. spec.md US3 Acceptance Scenarios 1-3 / quickstart.md Scénario 3.

### Tests for User Story 3

- [ ] T016 [P] [US3] Test service : `reject()` fait passer `"en_attente"` **ou** `"validee"` → `"refusee"`, idempotent si déjà `"refusee"` dans `backend/tests/test_services/test_volunteer_action_service.py`
- [ ] T017 [P] [US3] Test API : `POST /admin/volunteer-actions/{id}/reject` — `200` statut `"refusee"` depuis `"en_attente"` et depuis `"validee"`, `403` sans pouvoir dédié (`/speckit-analyze` finding E1 — FR-007 non testé sur ce endpoint), `has_volunteer_action` redevient `false` si c'était la seule ligne validée dans `backend/tests/test_api/test_admin_volunteer_actions_api.py`

### Implementation for User Story 3

- [ ] T018 [US3] Implémenter `volunteer_action_service.reject()` dans `backend/app/services/volunteer_action_service.py` — fait passer T016 (depends on T005, T006)
- [ ] T019 [US3] Ajouter `POST /admin/volunteer-actions/{action_id}/reject` au router `admin_volunteer_actions.py` — fait passer T017 (depends on T018, T010)

**Checkpoint**: les trois user stories fonctionnelles indépendamment.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T020 [P] Rejouer les 4 scénarios de `quickstart.md` contre le serveur de dev réel
- [ ] T021 [P] `cd backend && uv run pytest -m "not integration"` — suite complète verte
- [ ] T022 [P] `cd backend && uv run ruff check .`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)** : bloque les trois user stories.
- **US1, US2, US3** : toutes dépendent de Foundational ; US2/US3 partagent le fichier `admin_volunteer_actions.py` créé par US1 (T010) — séquentielles sur ce fichier, pas parallèles entre elles.
- **Polish** : dépend des trois user stories.

### Parallel Opportunities

- T001, T002 (tests foundational) en parallèle.
- T003, T004 (permission, schéma — fichiers distincts) en parallèle.
- T007/T008 (US1), T012/T013 (US2), T016/T017 (US3) : tests en parallèle au sein de chaque story.

---

## Implementation Strategy

### MVP First

1. Foundational, puis US1+US2 (P1) livrent déjà la valeur complète de
   l'issue #779 côté « faire compter une déclaration ».
2. US3 (P2) complète le workflow (refus).
3. Polish avant PR.

### Hors périmètre (rappel)

Aucune tâche ne touche le formulaire de saisie (#778, déjà livré) ni
l'affichage de la fiche athlète (#781) — cette sous-issue est backend
uniquement, conforme au titre de l'issue #779.
