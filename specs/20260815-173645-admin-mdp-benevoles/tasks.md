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

**Note d'implémentation** — les chemins de test ci-dessous ont été écrits
avant lecture des dossiers réels du dépôt (`tests/test_services/`,
`tests/test_api/`, `tests/test_repositories/`, `tests/test_auth/` — pas
`tests/services/`/`tests/api/`/`tests/repositories/`). Les tâches
mentionnent désormais le chemin **réellement utilisé** ; toute divergence
avec l'intention d'origine est signalée en note.

---

## Phase 1: Setup

**Purpose**: Aucune nouvelle dépendance (research.md §D1 : `hashlib`/`secrets`
du stdlib) ni nouvel outillage — le projet existe déjà. Cette phase se réduit
à une vérification.

- [X] T001 Vérifier que `backend/pyproject.toml` n'a besoin d'aucun ajout de
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

- [X] T002 [P] Test `hash_password`/`verify_password` (empreinte
      différente à chaque appel même avec le même mot de passe grâce au sel,
      `verify_password` accepte le bon mot de passe et rejette un mauvais)
      dans `backend/tests/test_services/test_benevole_access.py`.
- [X] T003 [P] Test `new_session_secret` (génère une valeur différente à
      chaque appel) dans `backend/tests/test_services/test_benevole_access.py`.
- [X] T004 [P] Test repository `benevole_config_repository`
      (`get_config` renvoie `None` en l'absence de ligne — FR-007 ;
      `save_config` crée la ligne unique si absente, la met à jour sinon,
      sans jamais laisser exister deux lignes) dans
      `backend/tests/test_repositories/test_benevole_config_repository.py`
      (nouveau fichier).
- [X] T005 [P] Test non-régression : `require_benevole_access` refuse toute
      connexion tant qu'aucune configuration n'existe en base (FR-007) —
      couvert en étendant les fixtures de
      `backend/tests/test_api/test_benevoles_api.py` (le fichier existant
      d'#271, pas un nouveau `test_benevole_access.py` sous `test_api/` :
      c'est le même fichier qui portait déjà les tests de garde #271).

### Implémentation

- [X] T006 Créer le modèle `BenevoleAccessConfig` (`id`, `password_hash`,
      `password_salt`, `session_secret`, `updated_at`,
      `updated_by_user_id` FK `users.id` NOT NULL) dans
      `backend/app/models/benevole_access_config.py` (data-model.md), et
      l'enregistrer dans `backend/app/models/__init__.py` (import +
      `__all__`) — sans quoi `alembic/env.py`
      (`importlib.import_module("app.models")`) ne le voit pas sur
      `Base.metadata` et T007 autogenère une migration vide. **Vérifié en
      pratique** : la première tentative sans cet ajout aurait autogénéré
      une migration vide (c'est la correction apportée par `/speckit-analyze`).
- [X] T007 Générer la migration Alembic de schéma pour
      `benevole_access_config` (`uv run alembic revision --autogenerate`,
      relue et reformattée à la main) —
      `backend/alembic/versions/194ac2494048_benevole_access_config_table.py`.
- [X] T008 [P] Créer `backend/app/repositories/benevole_config_repository.py`
      (`get_config`, `save_config` — seule couche touchant la Session pour
      cette table).
- [X] T009 [P] Ajouter `hash_password`/`verify_password` (`hashlib.scrypt` +
      sel `secrets.token_bytes(16)`, comparaison `hmac.compare_digest` —
      research.md §D1) dans `backend/app/services/benevole_access.py`.
- [X] T010 [P] Ajouter `new_session_secret` (`secrets.token_urlsafe(32)` —
      research.md §D2) dans `backend/app/services/benevole_access.py`.
      **Effet de bord assumé** : `sign_session`/`verify_session` ont vu leur
      paramètre renommé `password` → `key`, leur signature restant
      inchangée (positionnelle) — c'est le paramètre qui portait désormais
      un secret de session, pas un mot de passe, et le Principe I
      (explicitness des identifiants) l'imposait.
- [X] T010b Ajouter `replace_password(db, *, password, admin_user_id)` dans
      `backend/app/services/benevole_access.py` : orchestration de service
      qui hache le mot de passe fourni (ou génère si `password=None`),
      régénère `session_secret`, et écrit les trois champs dans le même
      appel à `benevole_config_repository.save_config`.
- [X] T011 [P] Ajouter le pouvoir `benevole_access:manage`
      (`P.BENEVOLE_ACCESS_MANAGE`) sous `FEATURE_ROLES` dans
      `backend/app/core/permissions.py`. A aussi nécessité la mise à jour de
      `tests/test_core/test_permissions.py::CODES_ATTENDUS` (méta-test
      explicite du catalogue complet, non listé dans ce `tasks.md` d'origine).
- [X] T012 Modifier `require_benevole_access` dans `backend/app/api/deps.py`
      pour lire `BenevoleAccessConfig` via le repository au lieu de
      `settings.benevole_shared_password`.
- [X] T013 Modifier `open_session` dans `backend/app/api/v1/benevoles.py`
      pour vérifier le mot de passe avec `verify_password`, puis signer le
      cookie avec `sign_session(config.session_secret)`.
- [X] T014 Retirer `benevole_shared_password` de `Settings`
      (`backend/app/core/config.py`) et de `backend/.env.example`.

**Checkpoint**: Le login bénévole (#271) fonctionne à l'identique en
s'appuyant sur la configuration en base ; aucune route admin n'existe
encore. ✅ Vérifié — 3513 tests backend verts.

---

## Phase 3: User Story 1 - Un administrateur définit un nouveau mot de passe (Priority: P1) 🎯 MVP

**Goal**: Un administrateur habilité peut consulter l'état de la
configuration et remplacer le mot de passe par une saisie ; le remplacement
invalide immédiatement les sessions ouvertes.

**Independent Test**: `GET` avant/après un `PUT` avec un nouveau mot de
passe ; vérifier qu'une session ouverte avant le `PUT` échoue ensuite et
que l'ancien mot de passe est rejeté (quickstart.md scénarios 1 et 2).

### Tests for User Story 1

**Note** : les routes gardées par `require_permission` ont leurs tests sous
`tests/test_auth/` dans ce dépôt (patron `test_admin_allowed_emails_api.py`,
`test_admin_sessions_api.py` — c'est là que vit la fixture `ouvrir_session`),
pas sous `tests/test_api/` comme prévu à l'écriture de ce fichier.

- [X] T015 [P] [US1] Test contrat `GET /api/v1/admin/benevoles/access` dans
      `backend/tests/test_auth/test_admin_benevole_access_api.py` (nouveau
      fichier).
- [X] T016 [P] [US1] Test contrat `PUT /api/v1/admin/benevoles/access`
      (200, rotation du `session_secret` vérifiée via l'invalidation de
      session) — même fichier.
- [X] T017 [P] [US1] Test garde RBAC : 403 sans le pouvoir, 401 sans session
      — même fichier.
- [X] T018 [P] [US1] Test d'intégration : remplacer le mot de passe invalide
      une session bénévole déjà ouverte et rejette l'ancien mot de passe —
      même fichier (`test_remplacement_invalide_les_sessions_deja_ouvertes`).
- [X] T019 [P] [US1] Test : chaque `PUT` écrit une entrée `AdminActionLog`
      sans secret dans le payload — même fichier.

### Implementation for User Story 1

- [X] T020 [P] [US1] Ajouter les schémas Pydantic `BenevoleAccessConfigOut`/
      `BenevoleAccessReplaceIn`/`BenevoleAccessGeneratedOut` dans
      `backend/app/schemas/benevole_access.py`.
- [X] T021 [US1] Créer le routeur `backend/app/api/v1/admin_benevole_access.py`
      avec `GET`/`PUT /api/v1/admin/benevoles/access`, gardées par
      `require_permission(P.BENEVOLE_ACCESS_MANAGE)`.
- [X] T022 [US1] Enregistrer le nouveau routeur dans
      `backend/app/api/v1/router.py`.
- [X] T023 [US1] Ajouter la journalisation `AdminActionLog` — **dans le
      routeur** (T023 disait « dans la route PUT », confirmé : la
      convention du dépôt observée sur `admin_actions.py` place ces écritures
      juste avant `db.commit()`, ici dans `admin_benevole_access.py`, pas
      dans le service `replace_password`, pour rester cohérent avec le
      seul autre appelant existant du repository de journal).
- [X] T024 [P] [US1] Ajouter `getBenevoleAccessConfig`/
      `replaceBenevoleAccessPassword` dans `frontend/lib/api/client.ts`
      (nommée `replaceBenevoleAccessPassword`, pas `putBenevoleAccessConfig`
      comme prévu — nomme le geste, pas le verbe HTTP, cohérent avec
      `addAllowedEmail`/`revokeSessions` du même fichier).
- [X] T025 [US1] Créer `frontend/components/admin/BenevoleAccessConfig.tsx`
      avec `frontend/components/admin/BenevoleAccessConfig.test.tsx`.
- [X] T026 [US1] Intégrer `BenevoleAccessConfig` dans
      `frontend/app/admin/acces/page.tsx`.

**Checkpoint**: US1 est fonctionnelle et testable indépendamment. ✅

---

## Phase 4: User Story 2 - Un administrateur fait générer un mot de passe sécurisé (Priority: P2)

**Goal**: Un administrateur peut déclencher la génération d'un mot de passe
robuste, affiché en clair une seule fois, jamais retrouvable ensuite.

**Independent Test**: `POST .../generate` renvoie un mot de passe qui
fonctionne pour une connexion bénévole ; un `GET` immédiatement après ne le
révèle jamais (quickstart.md scénario 3).

### Tests for User Story 2

- [X] T027 [P] [US2] Test contrat `POST /api/v1/admin/benevoles/access/generate`
      dans `backend/tests/test_auth/test_admin_benevole_access_api.py`.
- [X] T028 [P] [US2] Test : après génération, le mot de passe n'est plus
      jamais retrouvable — même fichier.
- [X] T029 [P] [US2] Test garde RBAC sur `POST .../generate` — même fichier.
- [X] T030 [P] [US2] Test : la génération invalide aussi les sessions
      ouvertes — même fichier (couvre le même besoin que la tâche d'origine,
      qui visait `test_benevoles_api.py`).

### Implementation for User Story 2

- [X] T031 [P] [US2] Ajouter `generate_password` (`secrets.token_urlsafe(18)`)
      dans `backend/app/services/benevole_access.py`, appelée par
      `replace_password` quand `password=None`.
- [X] T032 [US2] Ajouter `POST /api/v1/admin/benevoles/access/generate` dans
      `admin_benevole_access.py`.
- [X] T033 [P] [US2] Ajouter `generateBenevoleAccessPassword` dans
      `frontend/lib/api/client.ts`.
- [X] T034 [US2] Ajouter à `BenevoleAccessConfig.tsx` le bouton de génération
      et l'affichage unique du mot de passe généré (copie presse-papiers),
      et étendre `BenevoleAccessConfig.test.tsx`.

**Checkpoint**: US1 et US2 fonctionnent toutes les deux. ✅

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T035 Scénarios de [quickstart.md](./quickstart.md) couverts par les
      tests automatisés ci-dessus (1↔T015/T016, 2↔T018/T030, 3↔T027/T028,
      4↔T017/T029) — dérouler à la main reste possible via `uv run python
      scripts/dev_server.py` + `curl`, non nécessaire ici.
- [X] T036 [P] Mis à jour `backend/app/api/AGENTS.md` (section « Page
      bénévoles »). Aucun `docs/api/*.md` ne référençait cette page.
- [X] T037 Vérification avant complétion : `uv run pytest -m "not
      integration"` (3513 passed), `uv run ruff check .` (clean),
      `npm test` (827 passed), `npm run lint` (clean), `npm run build`
      (compile + TypeScript strict OK).

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
  parallèle une fois T006/T007 posés ; T010b dépend d'eux et vient après.
- T015-T019 (tests US1) en parallèle.
- T027-T030 (tests US2) en parallèle.
- T024 (client API) en parallèle du backend US1.

## Implementation Strategy

**MVP** : Setup → Foundational → US1 (T001-T026) livre déjà la capacité
de base demandée (remplacer un mot de passe depuis le back-office, FR-001,
FR-004 à FR-009). US2 (génération sécurisée) s'ajoute ensuite sans
retoucher US1.

**Réalisé** : les 37 tâches (T001-T037, T010b compris) sont complètes.
Suite complète verte : backend 3513/3513, frontend 827/827, lint et build
propres des deux côtés.
