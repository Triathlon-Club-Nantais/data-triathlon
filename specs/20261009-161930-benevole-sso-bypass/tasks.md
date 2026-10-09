# Tasks: Accès bénévoles sans mot de passe pour l'administrateur qui le gère

**Input**: Design documents from `specs/20261009-161930-benevole-sso-bypass/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: obligatoires (Principe III, TDD non négociable) : chaque tâche de test est écrite et vue **rouge** avant la tâche d'implémentation qui la suit.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

Aucune : pas de dépendance, de migration ni de configuration nouvelle.

## Phase 2: Foundational

- [X] T001 Créer le module de test `backend/tests/test_auth/test_benevole_access_sso.py` avec ses fixtures locales (`mot_de_passe_configure`, `compte_systeme`, `resultat_pendant`, `cookie_benevole`), sur le modèle de `backend/tests/test_api/test_benevoles_api.py`, la fixture `ouvrir_session` venant de `backend/tests/test_auth/conftest.py`

**Checkpoint**: le module de test se collecte.

---

## Phase 3: User Story 1 - L'administrateur qui gère le mot de passe entre sans le saisir (P1) 🎯 MVP

**Goal**: un connecté qui détient `benevole_access:manage` atteint toutes les ressources gardées sans cookie.

**Independent Test**: `ouvrir_session(P.BENEVOLE_ACCESS_MANAGE)` puis `GET /api/v1/benevoles/queue` rend 200 sans cookie bénévoles.

### Tests for User Story 1 (écrits d'abord, rouges)

- [X] T002 [US1] Tests rouges dans `backend/tests/test_auth/test_benevole_access_sso.py` : un connecté avec le pouvoir et sans cookie obtient 200 sur chacune des cinq lectures (`queue`, `queue/count`, `queue/history`, `rejected`, `athletes?name=..`) et 200 sur `POST .../validate` (fixture `compte_systeme` posée, statut seul : l'attribution relève de T009) ; un superutilisateur (`ouvrir_session(superutilisateur=True)`) obtient 200 sur `queue`
- [X] T003 [P] [US1] Test rouge dans `frontend/app/benevoles/page.test.tsx` : avec `tcn_logged_in` posé et `getSession` rendant un utilisateur dont `permissions` contient `benevole_access:manage`, la file s'affiche et aucun bouton « Se déconnecter » n'est rendu ; sans ce pouvoir, le bouton reste

### Implementation for User Story 1

- [X] T004 [US1] Dans `backend/app/api/deps.py`, `require_benevole_access` compose `optional_user` et rend l'utilisateur quand `authorization.has_permission(db, user, P.BENEVOLE_ACCESS_MANAGE)` ; sinon garde actuelle inchangée, rend `None` (T002 vert)
- [X] T005 [US1] Dans `frontend/app/benevoles/page.tsx`, lire `useSession()` et masquer « Se déconnecter » quand `permissions` contient `benevole_access:manage` (T003 vert)

**Checkpoint**: US1 livrable seule.

---

## Phase 4: User Story 2 - Sans le pouvoir, rien ne change (P1)

**Goal**: anonyme, session invalide et connecté sans pouvoir gardent exactement la garde actuelle.

**Independent Test**: connecté sans pouvoir et sans cookie, `GET /api/v1/benevoles/queue` rend le même 401 qu'un anonyme.

### Tests for User Story 2

- [X] T006 [US2] Tests dans `backend/tests/test_auth/test_benevole_access_sso.py` : connecté sans le pouvoir et sans cookie → 401 au corps identique à celui d'un anonyme (jamais 403) ; connecté sans le pouvoir avec cookie valide → 200 ; jeton SSO invalide sans cookie → 401 ; configuration absente et connecté sans pouvoir muni d'un ancien cookie → 401 ; administrateur dont le rôle perd le pouvoir entre deux appels → 401 au second. Vérifier en plus que `backend/tests/test_api/test_benevoles_api.py` reste vert sans modification

### Implementation for User Story 2

- [X] T007 [US2] Tâche conditionnelle, aucun code propre attendu (couvert par T004) ; si un test de T006 échoue, corriger `require_benevole_access` dans `backend/app/api/deps.py`

**Checkpoint**: US1 et US2 vertes ensemble.

---

## Phase 5: User Story 3 - Les gestes de l'administrateur sont tracés à son nom (P2)

**Goal**: les six écritures journalisent l'administrateur admis par pouvoir ; le cookie seul journalise le compte système.

**Independent Test**: valider en tant qu'administrateur admis, lire `admin_action_log_repository.list_for_entity` : `user_id` est le sien.

### Tests for User Story 3 (écrits d'abord, rouges)

- [X] T008 [P] [US3] Test rouge dans `backend/tests/test_services/test_benevole_access.py` : `benevole_access.actor_user_id(db, admin)` rend `admin.id` ; avec `None`, rend l'id du compte système
- [X] T009 [US3] Tests rouges dans `backend/tests/test_auth/test_benevole_access_sso.py` : pour `validate`, `reject`, `unreject`, `update_fields`, `rename_course` et `reassign` faits par un connecté avec le pouvoir, l'entrée du journal porte son `user_id` ; avec pouvoir **et** cookie, l'identité SSO prime ; un connecté sans pouvoir muni du cookie est journalisé au compte système

### Implementation for User Story 3

- [X] T010 [US3] Ajouter `actor_user_id(db, admin: User | None) -> int` dans `backend/app/services/benevole_access.py` (T008 vert)
- [X] T011 [US3] Dans `backend/app/api/v1/benevoles.py`, les six routes d'écriture reçoivent `admin: User | None = Depends(require_benevole_access)` et passent `user_id=benevole_access.actor_user_id(db, admin)` aux services `admin_actions` (T009 vert)

**Checkpoint**: toutes les stories vertes.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T012 [P] Mettre à jour la section « Page bénévoles » de `backend/app/api/AGENTS.md` et les docstrings de `backend/app/api/v1/benevoles.py` et de `require_benevole_access` (admission par pouvoir, acteur du journal)
- [X] T013 Vérification complète : depuis `backend/`, `uv run pytest -m "not integration"` et `uv run ruff check .` ; depuis `frontend/`, `npm test`, `npm run lint`, `npm run build`

---

## Dependencies & Execution Order

- T001 → T002 → T004 ; T003 → T005 (indépendant du backend)
- T006 après T004
- T008 → T010 ; T009 → T011 ; T011 après T004 (signature de la garde)
- T012, T013 en dernier

### Parallel Opportunities

- T003 (front) en parallèle de T002 (back) ; T008 en parallèle de T009.

## Implementation Strategy

MVP = US1 (T001 à T005). US2 n'ajoute que des tests de non-régression. US3 ajoute la traçabilité. Chaque test est vu échouer avant son implémentation.
