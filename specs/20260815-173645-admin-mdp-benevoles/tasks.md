# Tasks: Gestion admin du mot de passe partagé bénévoles

**Input**: Design documents from `/specs/20260815-173645-admin-mdp-benevoles/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md)

**Tests**: TDD non-négociable (Principe III) — chaque tâche d'implémentation
backend est précédée de sa tâche de test, à faire échouer avant d'écrire le
code (cf. `test-driven-development`).

**Organization**: Groupé par user story ; Foundational porte tout ce qui est
partagé par les deux stories (modèle, migration, repository, permission,
hachage, bascule de `require_benevole_access`/`open_session`).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: fichiers différents, sans dépendance entre elles
- **[Story]**: US1 ou US2 (aucun label en Setup/Foundational/Polish)

## Path Conventions

Application web existante : `backend/app/`, `backend/tests/`, `frontend/`.

---

## Phase 1: Setup

**Purpose**: Aucune nouvelle dépendance (research.md §D1 : `hashlib`/`secrets`
du stdlib) ni nouvel outillage — le projet existe déjà. Cette phase se réduit
à une vérification.

- [ ] T001 Vérifier que `backend/pyproject.toml` n'a besoin d'aucun ajout de
      dépendance (confirmer l'absence de `bcrypt`/`argon2-cffi`/`passlib`,
      comme constaté en research.md §D1) — aucune modification attendue.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Socle partagé par US1 et US2 — modèle, migration, repository,
pouvoir RBAC, primitives de hachage/génération, et bascule des deux points
d'entrée bénévoles existants (#271) vers la configuration en base.

**⚠️ CRITICAL**: Aucune des deux user stories ne peut démarrer avant la fin
de cette phase.

### Tests (à écrire et faire échouer avant l'implémentation)

- [ ] T002 [P] Test `hash_password`/`verify_password` (empreinte
      différente à chaque appel même avec le même mot de passe grâce au sel,
      `verify_password` accepte le bon mot de passe et rejette un mauvais,
      comparaison en temps constant) dans
      `backend/tests/services/test_benevole_access.py`.
- [ ] T003 [P] Test `new_session_secret` (génère une valeur différente à
      chaque appel, longueur/entropie suffisante) dans
      `backend/tests/services/test_benevole_access.py`.
- [ ] T004 [P] Test repository `benevole_config_repository`
      (`get_config` renvoie `None` en l'absence de ligne — FR-007 ;
      `save_config` crée la ligne unique si absente, la met à jour sinon,
      sans jamais laisser exister deux lignes) dans
      `backend/tests/repositories/test_benevole_config_repository.py`.
- [ ] T005 [P] Test non-régression : `require_benevole_access` (via
      `backend/app/api/deps.py`) refuse toute connexion tant qu'aucune
      configuration n'existe en base (FR-007, remplace l'ancien test sur
      `settings.benevole_shared_password` vide) dans
      `backend/tests/api/test_benevole_access.py` (étend le fichier
      existant d'#271).

### Implémentation

- [ ] T006 Créer le modèle `BenevoleAccessConfig` (`id`, `password_hash`,
      `password_salt`, `session_secret`, `updated_at`,
      `updated_by_user_id` FK `users.id` NOT NULL) dans
      `backend/app/models/benevole_access_config.py` (data-model.md).
- [ ] T007 Générer la migration Alembic de schéma pour
      `benevole_access_config` (`uv run alembic revision --autogenerate`)
      dans `backend/alembic/versions/` (dépend de T006).
- [ ] T008 [P] Créer `backend/app/repositories/benevole_config_repository.py`
      (`get_config`, `save_config` — seule couche touchant la Session pour
      cette table) pour faire passer T004 (dépend de T006).
- [ ] T009 [P] Ajouter `hash_password`/`verify_password` (`hashlib.scrypt` +
      sel `secrets.token_bytes(16)`, comparaison `hmac.compare_digest` —
      research.md §D1) dans `backend/app/services/benevole_access.py` pour
      faire passer T002.
- [ ] T010 [P] Ajouter `new_session_secret` (`secrets.token_urlsafe(32)` —
      research.md §D2) dans `backend/app/services/benevole_access.py` pour
      faire passer T003.
- [ ] T011 [P] Ajouter le pouvoir `benevole_access:manage`
      (`P.BENEVOLE_ACCESS_MANAGE`) sous `FEATURE_ROLES` dans
      `backend/app/core/permissions.py` (research.md §D4, patron
      `allowed_emails:manage`/`sessions:revoke`).
- [ ] T012 Modifier `require_benevole_access` dans
      `backend/app/api/deps.py` pour lire `BenevoleAccessConfig` via le
      repository (T008) au lieu de `settings.benevole_shared_password`,
      vérifier le cookie avec `verify_session(session_secret, ...)` et
      rester fail-closed si aucune configuration n'existe (fait passer T005 ;
      dépend de T008, T009, T010).
- [ ] T013 Modifier `open_session` dans `backend/app/api/v1/benevoles.py`
      pour vérifier le mot de passe soumis avec `verify_password` contre
      `password_hash`/`password_salt`, puis signer le cookie avec
      `sign_session(session_secret, ...)` au lieu du mot de passe en clair
      (dépend de T008, T009, T010).
- [ ] T014 Retirer `benevole_shared_password` de `Settings`
      (`backend/app/core/config.py`) et de `backend/.env.example` —
      dernière tâche de la phase, une fois que plus rien ne le lit (dépend
      de T012, T013).

**Checkpoint**: Le login bénévole (#271) fonctionne à l'identique en
s'appuyant sur la configuration en base ; aucune route admin n'existe
encore.

---

## Phase 3: User Story 1 - Un administrateur définit un nouveau mot de passe (Priority: P1) 🎯 MVP

**Goal**: Un administrateur habilité peut consulter l'état de la
configuration et remplacer le mot de passe par une saisie ; le remplacement
invalide immédiatement les sessions ouvertes.

**Independent Test**: `GET` avant/après un `PUT` avec un nouveau mot de
passe ; vérifier qu'une session ouverte avant le `PUT` échoue ensuite et
que l'ancien mot de passe est rejeté (quickstart.md scénarios 1 et 2).

### Tests for User Story 1

- [ ] T015 [P] [US1] Test contrat `GET /api/v1/admin/benevoles/access`
      (200 avec `configured: false` en l'absence de configuration ; 200
      avec `configured: true` + `updated_at`/`updated_by` après un
      remplacement ; ne renvoie jamais le mot de passe ni son empreinte)
      dans `backend/tests/api/test_admin_benevole_access.py`.
- [ ] T016 [P] [US1] Test contrat `PUT /api/v1/admin/benevoles/access`
      (200, même forme que `GET`, rotation du `session_secret`) dans
      `backend/tests/api/test_admin_benevole_access.py`.
- [ ] T017 [P] [US1] Test garde RBAC : les deux routes renvoient 403 pour
      un utilisateur du back-office sans `benevole_access:manage` et 401
      sans session back-office (FR-005, SC-004) dans
      `backend/tests/api/test_admin_benevole_access.py`.
- [ ] T018 [P] [US1] Test d'intégration : remplacer le mot de passe
      invalide une session bénévole déjà ouverte et rejette l'ancien mot de
      passe à la connexion suivante (FR-006, SC-002, quickstart.md
      scénario 2) dans `backend/tests/api/test_benevoles_api.py`.
- [ ] T019 [P] [US1] Test : chaque `PUT` écrit une entrée
      `AdminActionLog` (`benevole_access.password_replace`,
      `entity_type="benevole_access_config"`, `entity_id=1`) dont le
      payload ne contient ni le mot de passe, ni le hachage, ni le sel, ni
      le secret de session (FR-009) dans
      `backend/tests/api/test_admin_benevole_access.py`.

### Implementation for User Story 1

- [ ] T020 [P] [US1] Ajouter les schémas Pydantic
      `BenevoleAccessConfigOut`/`BenevoleAccessReplaceIn` (contracts/api.md
      — validation de longueur minimale sur `password`) dans
      `backend/app/schemas/benevole_access.py`.
- [ ] T021 [US1] Créer le routeur
      `backend/app/api/v1/admin_benevole_access.py` avec les routes `GET`
      et `PUT /api/v1/admin/benevoles/access`, gardées par
      `require_permission(P.BENEVOLE_ACCESS_MANAGE)` route par route,
      résolvant `updated_by` par jointure sur `User.display_name` (dépend
      de T008, T009, T010, T011, T020 ; fait passer T015, T016, T017).
- [ ] T022 [US1] Enregistrer le nouveau routeur dans l'agrégateur de routes
      `/api/v1` (dépend de T021).
- [ ] T023 [US1] Ajouter la journalisation `AdminActionLog` dans la route
      `PUT` (mêmes conventions que `admin_sessions.py`/
      `admin_allowed_emails.py`, payload sans secret — fait passer T019 ;
      dépend de T021).
- [ ] T024 [P] [US1] Ajouter `getBenevoleAccessConfig`/
      `putBenevoleAccessConfig` dans `frontend/lib/api/client.ts`.
- [ ] T025 [US1] Créer `frontend/components/admin/BenevoleAccessConfig.tsx`
      (état courant via `GET`, formulaire de remplacement manuel via
      `PUT`, confirmation visuelle du remplacement — FR-001) avec
      `frontend/components/admin/BenevoleAccessConfig.test.tsx` (dépend de
      T024).
- [ ] T026 [US1] Intégrer `BenevoleAccessConfig` dans
      `frontend/app/admin/acces/page.tsx`, gardé par le pouvoir
      `benevole_access:manage` (dépend de T025).

**Checkpoint**: US1 est fonctionnelle et testable indépendamment — un
administrateur peut consulter et remplacer le mot de passe depuis le
back-office.

---

## Phase 4: User Story 2 - Un administrateur fait générer un mot de passe sécurisé (Priority: P2)

**Goal**: Un administrateur peut déclencher la génération d'un mot de passe
robuste, affiché en clair une seule fois, jamais retrouvable ensuite.

**Independent Test**: `POST .../generate` renvoie un mot de passe qui
fonctionne pour une connexion bénévole ; un `GET` immédiatement après ne le
révèle jamais (quickstart.md scénario 3).

### Tests for User Story 2

- [ ] T027 [P] [US2] Test contrat `POST /api/v1/admin/benevoles/access/generate`
      (200, `{"password": <24 caractères>, "updated_at", "updated_by"}`,
      le mot de passe généré fonctionne pour
      `POST /api/v1/benevoles/session` — FR-002, FR-003) dans
      `backend/tests/api/test_admin_benevole_access.py`.
- [ ] T028 [P] [US2] Test : après génération, aucun `GET` ni aucune autre
      route ne renvoie jamais le mot de passe généré (FR-004, SC-003) dans
      `backend/tests/api/test_admin_benevole_access.py`.
- [ ] T029 [P] [US2] Test garde RBAC : 403/401 sur `POST .../generate`
      dans les mêmes conditions que T017 dans
      `backend/tests/api/test_admin_benevole_access.py`.
- [ ] T030 [P] [US2] Test : la génération invalide aussi les sessions
      bénévoles déjà ouvertes, comme un remplacement manuel (FR-006) dans
      `backend/tests/api/test_benevoles_api.py`.

### Implementation for User Story 2

- [ ] T031 [P] [US2] Ajouter `generate_password`
      (`secrets.token_urlsafe(18)`, research.md §D5) dans
      `backend/app/services/benevole_access.py`.
- [ ] T032 [US2] Ajouter la route
      `POST /api/v1/admin/benevoles/access/generate` dans
      `admin_benevole_access.py` (génère, hache, stocke, journalise comme
      T023, renvoie le mot de passe en clair une seule fois — dépend de
      T021, T023, T031 ; fait passer T027, T028, T029, T030).
- [ ] T033 [P] [US2] Ajouter `generateBenevoleAccessPassword` dans
      `frontend/lib/api/client.ts`.
- [ ] T034 [US2] Ajouter à `BenevoleAccessConfig.tsx` le bouton de
      génération sécurisée et l'affichage unique du mot de passe généré
      (copie presse-papiers, avertissement qu'il ne sera plus jamais
      affiché — FR-003) et étendre
      `BenevoleAccessConfig.test.tsx` (dépend de T025, T033).

**Checkpoint**: US1 et US2 fonctionnent toutes les deux, indépendamment et
ensemble.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [ ] T035 Dérouler manuellement les 4 scénarios de
      [quickstart.md](./quickstart.md).
- [ ] T036 [P] Mettre à jour `backend/app/api/AGENTS.md` (section « Page
      bénévoles ») et tout `docs/api/*.md` pertinent pour documenter les 3
      nouvelles routes et le retrait de `BENEVOLE_SHARED_PASSWORD`.
- [ ] T037 Vérification avant complétion :
      `cd backend && uv run pytest -m "not integration" && uv run ruff check .`
      puis `cd frontend && npm test && npm run lint && npm run build`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: aucune dépendance.
- **Foundational (Phase 2)**: dépend de Setup — bloque les deux user
  stories.
- **US1 (Phase 3)**: dépend de Foundational uniquement.
- **US2 (Phase 4)**: dépend de Foundational ; réutilise le routeur créé par
  US1 (T021, T023) — non indépendante au niveau fichier, mais
  indépendamment testable une fois US1 livrée (patron autorisé par le
  template : « may integrate with US1 »).
- **Polish (Phase 5)**: dépend de US1 et US2.

### Parallel Opportunities

- T002-T005 (tests Foundational) en parallèle.
- T008-T011 (repository, hachage, secret de session, permission) en
  parallèle une fois T006/T007 posés.
- T015-T019 (tests US1) en parallèle.
- T027-T030 (tests US2) en parallèle.
- T024 (client API) en parallèle du backend US1.

## Implementation Strategy

**MVP** : Setup → Foundational → US1 (T001-T026) livre déjà la capacité
de base demandée (remplacer un mot de passe depuis le back-office, FR-001,
FR-004 à FR-009). US2 (génération sécurisée) s'ajoute ensuite sans
retoucher US1.
