# Tasks: Page de vérification des résultats par les bénévoles

**Input**: Design documents from `specs/20260815-114258-page-validation-benevoles/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md — tous présents.

**Tests**: TDD non-négociable (Principe III) — chaque tâche de logique métier ou d'endpoint est précédée d'une tâche de test qui échoue puis passe au vert.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Chemins de fichiers exacts dans chaque description.

---

## Phase 0: Blocage externe — NE PAS DÉMARRER l'implémentation

- [ ] T001 **BLOQUÉ** — Vérifier que la branche `20260814-130052-saisie-manuelle-resultats`
  (#270) est fusionnée dans `main` et que `backend/app/models/participation.py`
  porte bien `is_pending_validation`, `evidence_url`, `team_name` sur `main`
  avant de commencer **toute** tâche ci-dessous (T002 et suivantes). Sans
  cette fusion, `Participation.is_pending_validation` n'existe pas et aucune
  tâche de ce fichier ne peut s'exécuter. (#330 — reprise des résultats
  manuels antérieurs — est fermée `not_planned` : aucun stock existant, ce
  second blocage est levé.)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffolding partagé, avant toute logique métier.

- [ ] T002 [P] Ajouter `benevole_shared_password: str = ""` à
  `backend/app/core/config.py` (défaut vide = accès non configuré, fail-closed
  — patron d'`auth_session_secret_key`, cf. `research.md` §D1).
- [ ] T003 [P] Ajouter `BENEVOLE_SHARED_PASSWORD=` à `backend/.env.example`
  avec un commentaire renvoyant à `research.md` §D1.
- [ ] T004 [P] Créer `backend/app/services/benevole_access.py` (fichier vide
  avec docstring de module, renvoyant à `research.md` §D1) et
  `backend/app/api/v1/benevoles.py` (routeur vide, `APIRouter(tags=["benevoles"])`).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Le mécanisme d'accès, la lecture de la file et le compte système
— aucune user story ne peut être implémentée avant que cette phase soit complète.

**⚠️ CRITICAL**: Aucune tâche de story ne démarre avant la fin de cette phase.

### Tests foundational

> Écrire ces tests d'abord, les voir échouer, puis les faire passer (Principe III).

- [ ] T005 [P] Test `sign_session`/`verify_session` (round-trip valide, échec
  si mot de passe changé entre-temps, échec si horodatage corrompu) dans
  `backend/tests/test_services/test_benevole_access.py`.
- [ ] T006 [P] Test de la dépendance `require_benevole_access` (401 sans
  cookie, 401 avec cookie invalide, passe avec cookie valide) dans
  `backend/tests/test_api/test_benevoles_api.py`.
- [ ] T007 [P] Test `participation_repository.list_pending` : ne renvoie que
  les participations `is_pending_validation=True`, tous clubs confondus (pas
  de filtre `tcn_clause`) dans
  `backend/tests/test_repositories/test_participation_repository.py`.

### Implémentation foundational

- [ ] T008 Implémenter `sign_session`/`verify_session` dans
  `backend/app/services/benevole_access.py` (HMAC-SHA256, clé = mot de passe
  courant, message = horodatage — cf. `research.md` §D1). Dépend de T005.
- [ ] T009 Implémenter `require_benevole_access` (dépendance FastAPI) dans
  `backend/app/api/deps.py`, distincte de `require_permission` — vérifie le
  cookie via `benevole_access.verify_session`, lève 401 sinon. Dépend de T006, T008.
- [ ] T010 [P] Implémenter `participation_repository.list_pending(db)` dans
  `backend/app/repositories/participation_repository.py`, filtre
  `Participation.is_pending_validation.is_(True)` (complément de
  `validated_clause`, cf. `research.md` §D4). Dépend de T007.
- [ ] T011 Créer la migration Alembic de données (pas de schéma) insérant le
  compte système « Bénévoles (accès partagé) » dans `users` (aucune ligne
  `identities` associée) — `backend/alembic/versions/<rev>_seed_benevole_system_user.py`.
  Consigner l'`id` généré dans une constante lisible (ex.
  `backend/app/core/config.py` ou un module dédié) pour que les services de
  la Phase 3+ le référencent sans requête ad hoc. Cf. `data-model.md`.
- [ ] T012 Monter `benevoles.py` dans `backend/app/api/v1/router.py` (routeur
  vide à ce stade, les routes arrivent story par story).

**Checkpoint**: Le mécanisme d'accès, la lecture de la file et le compte
système existent — les user stories peuvent démarrer.

---

## Phase 3: User Story 4 - Accès protégé par mot de passe partagé (Priority: P1)

**Goal**: Un bénévole s'authentifie par le mot de passe partagé et obtient un
cookie de session ; un visiteur sans mot de passe n'obtient rien.

**Independent Test**: `POST /api/v1/benevoles/session` avec mot de passe
erroné → 401 ; avec le bon mot de passe → 204 + cookie ; toute route gardée
sans ce cookie → 401.

### Tests for User Story 4

- [ ] T013 [P] [US4] Test `POST /api/v1/benevoles/session` : 401 mot de passe
  erroné, 401 si `benevole_shared_password` non configuré, 204 + cookie posé
  si correct, dans `backend/tests/test_api/test_benevoles_api.py`.
- [ ] T014 [P] [US4] Test `DELETE /api/v1/benevoles/session` : efface le
  cookie, 204, dans `backend/tests/test_api/test_benevoles_api.py`.

### Implementation for User Story 4

- [ ] T015 [US4] Implémenter `POST /api/v1/benevoles/session` dans
  `backend/app/api/v1/benevoles.py` (`hmac.compare_digest`, pose le cookie via
  `benevole_access.sign_session`). Dépend de T008, T013.
- [ ] T016 [US4] Implémenter `DELETE /api/v1/benevoles/session` (efface le
  cookie) dans `backend/app/api/v1/benevoles.py`. Dépend de T014.
- [ ] T017 [P] [US4] Test composant : formulaire de mot de passe affiché sur
  401, soumission, redirection vers la file sur succès, message d'erreur
  français sur échec, dans
  `frontend/components/benevoles/__tests__/AccessGate.test.tsx`.
- [ ] T018 [US4] Implémenter `app/benevoles/page.tsx` (garde d'accès : tente
  `GET /api/v1/benevoles/queue`, affiche `AccessGate` sur 401) et
  `components/benevoles/AccessGate.tsx` (formulaire de mot de passe,
  `components/ui/` pour l'input + `components/tcn/Card` pour le cadre — cf.
  `research.md` §D3). Dépend de T015, T017.
- [ ] T019 [US4] Ajouter les appels `POST`/`DELETE /benevoles/session` dans
  `frontend/lib/api/client.ts`.

**Checkpoint**: L'accès par mot de passe fonctionne de bout en bout,
indépendamment des autres stories.

---

## Phase 4: User Story 1 - File d'attente et validation d'un résultat légitime (Priority: P1) 🎯 MVP

**Goal**: Un bénévole authentifié voit la file des résultats en attente et
valide un résultat, qui devient visible sur la fiche de l'athlète et dans les
agrégats publics.

**Independent Test**: Créer une participation `is_pending_validation=true`,
la voir dans `GET /api/v1/benevoles/queue`, la valider, vérifier qu'elle
apparaît sur `GET /api/v1/athletes/{id}` et dans un agrégat public qui
l'excluait.

### Tests for User Story 1

- [ ] T020 [P] [US1] Test `GET /api/v1/benevoles/queue` : renvoie les
  participations en attente avec épreuve, athlète, temps, splits,
  `evidence_url`, `team_name` ; liste vide sans erreur si aucune en attente ;
  401 sans cookie, dans `backend/tests/test_api/test_benevoles_api.py`.
- [ ] T021 [P] [US1] Test `admin_actions.validate_participation` : passe
  `is_pending_validation` à `false`, journalise `participation.validate` sous
  le `user_id` du compte système, idempotent si déjà validée (pas de second
  écrit au journal, cf. `contracts/api.md`), dans
  `backend/tests/test_services/test_admin_actions.py`.
- [ ] T022 [P] [US1] Test `POST /api/v1/benevoles/participations/{id}/validate` :
  200 et disparition de la file, 404 si la participation n'existe pas, dans
  `backend/tests/test_api/test_benevoles_api.py`.

### Implementation for User Story 1

- [ ] T023 [US1] Implémenter `GET /api/v1/benevoles/queue` dans
  `backend/app/api/v1/benevoles.py`, délègue à
  `participation_repository.list_pending`. Dépend de T009, T010, T020.
- [ ] T024 [US1] Implémenter `validate_participation(db, *, participation_id,
  user_id)` dans `backend/app/services/admin_actions.py`, sur le patron de
  `update_course`/`reassign_participation` (instantané avant/après,
  `admin_action_log_repository.create` action `participation.validate`).
  Dépend de T021.
- [ ] T025 [US1] Implémenter
  `POST /api/v1/benevoles/participations/{participation_id}/validate` dans
  `backend/app/api/v1/benevoles.py`, appelle `validate_participation` avec le
  `user_id` du compte système (T011). Dépend de T024, T022.
- [ ] T026 [P] [US1] Test composant `ValidationQueue` (liste, sélection d'un
  résultat, affichage du panneau de détail avec `evidence_url`/`team_name`) et
  `ParticipationPanel` (bouton de validation) dans
  `frontend/components/benevoles/__tests__/ValidationQueue.test.tsx`.
- [ ] T027 [US1] Implémenter `components/benevoles/ValidationQueue.tsx` et
  `components/benevoles/ParticipationPanel.tsx` (`components/ui/table` +
  `components/ui/dialog`, `components/tcn/Card` pour les blocs d'information —
  cf. `research.md` §D3) et les brancher sur `app/benevoles/page.tsx`. Dépend
  de T018, T026.
- [ ] T028 [US1] Ajouter les appels `GET /benevoles/queue` et
  `POST /benevoles/participations/{id}/validate` dans
  `frontend/lib/api/client.ts`.

**Checkpoint**: MVP complet — un bénévole peut valider un résultat de bout en
bout.

---

## Phase 5: User Story 2 - Uniformisation du nom de l'épreuve (Priority: P2)

**Goal**: Un bénévole renomme l'épreuve associée à un résultat en attente pour
l'aligner sur une épreuve déjà connue.

**Independent Test**: `PATCH /api/v1/benevoles/courses/{course_id}` avec un
nom qui coïncide avec une épreuve existante → 409 ; avec un nom qui ne
collisionne pas → 200.

**Note** : la logique de renommage et de détection de collision
(`admin_actions.update_course`, `course_repository.get_by_identity`) est déjà
livrée et déjà testée pour le back-office (#117) — ces tests-là ne sont **pas**
repris ici. Les tests de cette story portent uniquement sur le nouveau chemin
d'exposition (garde bénévole, délégation avec le bon `user_id`).

### Tests for User Story 2

- [ ] T029 [P] [US2] Test `PATCH /api/v1/benevoles/courses/{course_id}` : 200
  si renommage sans collision (délègue bien à `admin_actions.update_course`
  avec le `user_id` du compte système, vérifié sur l'entrée du journal), 409
  si collision, 401 sans cookie, dans `backend/tests/test_api/test_benevoles_api.py`.

### Implementation for User Story 2

- [ ] T030 [US2] Implémenter `PATCH /api/v1/benevoles/courses/{course_id}`
  dans `backend/app/api/v1/benevoles.py`, corps restreint au seul champ
  `name`, délègue à `admin_actions.update_course` avec le `user_id` du compte
  système (T011). Dépend de T029.
- [ ] T031 [P] [US2] Test composant : champ d'édition du nom d'épreuve dans le
  panneau de détail, affichage de l'erreur de collision, dans
  `frontend/components/benevoles/__tests__/ParticipationPanel.test.tsx`.
- [ ] T032 [US2] Étendre `components/benevoles/ParticipationPanel.tsx` avec
  l'édition du nom d'épreuve (`components/ui/input`, message d'erreur
  français sur 409). Dépend de T027, T031.
- [ ] T033 [US2] Ajouter l'appel `PATCH /benevoles/courses/{id}` dans
  `frontend/lib/api/client.ts`.

**Checkpoint**: US1, US4 et US2 fonctionnent ensemble sans régression.

---

## Phase 6: User Story 3 - Réattribution à un autre athlète (Priority: P2)

**Goal**: Un bénévole réattribue un résultat en attente à un autre athlète
existant.

**Independent Test**: `POST /api/v1/benevoles/participations/{id}/reassign`
vers un athlète existant sans résultat sur cette épreuve → 200 ; vers un
athlète qui en a déjà un → 409.

**Note** : comme pour US2, `admin_actions.reassign_participation` est déjà
livrée et testée (#117) — pas de nouveau test de cette logique métier ici.

### Tests for User Story 3

- [ ] T034 [P] [US3] Test `POST /api/v1/benevoles/participations/{id}/reassign` :
  200 (délègue à `admin_actions.reassign_participation` avec le `user_id` du
  compte système), 409 si conflit, 404 si l'athlète cible n'existe pas, 401
  sans cookie, dans `backend/tests/test_api/test_benevoles_api.py`.

### Implementation for User Story 3

- [ ] T035 [US3] Implémenter
  `POST /api/v1/benevoles/participations/{participation_id}/reassign` dans
  `backend/app/api/v1/benevoles.py`, délègue à
  `admin_actions.reassign_participation` avec le `user_id` du compte système
  (T011). Dépend de T034.
- [ ] T036 [P] [US3] Test composant : sélecteur d'athlète dans le panneau de
  détail, message d'erreur français sur conflit, dans
  `frontend/components/benevoles/__tests__/ParticipationPanel.test.tsx`.
- [ ] T037 [US3] Étendre `components/benevoles/ParticipationPanel.tsx` avec le
  sélecteur de réattribution (`components/ui/select`, recherche parmi les
  athlètes existants — réutiliser le point d'API de recherche déjà exposé aux
  admins si son schéma convient, sinon documenter l'écart en tâche suiveuse).
  Dépend de T027, T036.
- [ ] T038 [US3] Ajouter l'appel `POST /benevoles/participations/{id}/reassign`
  dans `frontend/lib/api/client.ts`.

**Checkpoint**: Les quatre user stories (US4, US1, US2, US3) fonctionnent
ensemble — les quatre gestes de l'écran sont couverts.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Vérification de bout en bout et cohérence documentaire.

- [ ] T039 Exécuter les scénarios de `quickstart.md` de bout en bout sur une
  base de dev avec #270 fusionnée.
- [ ] T040 [P] `cd backend && uv run pytest -m "not integration"` vert.
- [ ] T041 [P] `cd backend && uv run ruff check .` sans erreur.
- [ ] T042 [P] `cd frontend && npm test` vert.
- [ ] T043 [P] `cd frontend && npm run lint` sans erreur.
- [ ] T044 [P] `cd frontend && npm run build` (strict TS + RSC) sans erreur.
- [ ] T045 Ajouter une entrée pour `benevole_access.py` et le routeur
  `benevoles.py` dans `backend/AGENTS.md` (inventaire des modules), sur le
  patron de l'entrée existante pour `services/auth/`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 0 (Blocage externe)** : bloque tout — rien ne démarre avant
  confirmation que #270 est fusionnée dans `main`.
- **Setup (Phase 1)** : dépend de Phase 0 levée. Peut démarrer immédiatement
  ensuite.
- **Foundational (Phase 2)** : dépend de Setup — bloque les quatre user
  stories.
- **User Stories (Phase 3-6)** : dépendent toutes de Foundational. US4
  (accès) est un prérequis **pratique** des trois autres (chaque route est
  gardée), donc listée en premier, mais reste indépendamment testable comme
  les autres (elle ne dépend d'aucune des trois).
- **Polish (Phase 7)** : dépend des user stories retenues pour cette
  livraison.

### User Story Dependencies

- **US4 (P1, accès)** : après Foundational. Aucune dépendance sur les autres
  stories, mais ses routes gardent celles des trois autres — livrer US4 avant
  US1/US2/US3 en pratique.
- **US1 (P1, validation nominale)** : après Foundational + US4 (a besoin du
  cookie pour être testée de bout en bout, mais sa logique de service est
  indépendante).
- **US2 (P2, renommage)** et **US3 (P2, réattribution)** : après Foundational
  + US4 ; indépendantes l'une de l'autre et d'US1.

### Parallel Opportunities

- T002, T003, T004 (Setup) en parallèle.
- T005, T006, T007 (tests foundational) en parallèle ; T010 en parallèle une
  fois T007 vert.
- Au sein de chaque story, les tâches de test marquées [P] sont parallèles
  entre elles ; les tâches de composant front [P] (T017, T026, T031, T036) le
  sont aussi entre stories différentes si l'équipe a la capacité.
- T040-T044 (Polish, vérifications) toutes en parallèle.

---

## Parallel Example: User Story 1

```bash
# Tests de la story 1, en parallèle :
Task: "Test GET /api/v1/benevoles/queue in backend/tests/test_api/test_benevoles_api.py"
Task: "Test admin_actions.validate_participation in backend/tests/test_services/test_admin_actions.py"
Task: "Test POST .../validate in backend/tests/test_api/test_benevoles_api.py"
```

---

## Implementation Strategy

### MVP First (User Story 4 + User Story 1)

1. Lever le blocage Phase 0 (fusion #270 confirmée).
2. Compléter Setup + Foundational.
3. Compléter US4 (accès) — sans elle, US1 n'est pas atteignable de bout en
   bout depuis le front, même si sa logique de service est testable seule.
4. Compléter US1 (validation nominale) — **MVP** : un bénévole peut valider un
   résultat.
5. **STOP et VALIDER** : scénarios 1 et 4 de `quickstart.md`.
6. Déployer/démontrer si prêt.

### Incremental Delivery

1. Setup + Foundational → fondation prête.
2. US4 + US1 → MVP → valider → démontrer.
3. US2 (renommage) → valider → démontrer.
4. US3 (réattribution) → valider → démontrer.
5. Chaque story ajoute de la valeur sans casser les précédentes.

---

## Notes

- [P] tasks = fichiers différents, aucune dépendance.
- Le renommage d'épreuve (US2) et la réattribution (US3) ne réécrivent aucune
  logique métier déjà livrée : ils l'exposent sous une garde différente.
- Vérifier que chaque test échoue avant d'implémenter (Principe III).
- Ne pas committer par tâche sans consigne explicite de l'exécuteur du plan —
  ce `tasks.md` ne tranche pas le mode d'exécution (`executing-plans` vs
  `subagent-driven-development` restent des choix de la voie Superpowers, hors
  de portée ici puisque cette feature suit Spec Kit).
- S'arrêter à chaque checkpoint pour valider une story indépendamment.
- Éviter : tâches vagues, conflits de fichiers, dépendances inter-stories qui
  casseraient l'indépendance.
