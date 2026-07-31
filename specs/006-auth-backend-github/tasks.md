---
description: "Task list — Auth backend GitHub OAuth (#114)"
---

# Tasks: Auth backend GitHub OAuth pour le back-office admin

**Input**: Design documents from `specs/006-auth-backend-github/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/auth-api.md`, `quickstart.md`.

**Tests** : Principe III (non-négociable). Chaque user story a ses tâches de
test **avant** ses tâches d'implémentation. Un test rouge d'abord, puis vert —
`uv run pytest -m "not integration"` doit rester le seul filtre en local. Aucun
appel réseau réel.

**Organization** : tâches groupées par user story pour livraison indépendante.
US1 (auth GitHub) et US2 (non-régression publique) sont les deux P1 — les deux
sont **livrables séparément** au sens du template Speckit, mais dans la
pratique elles se testent dans la même PR : livrer US1 sans US2 laisserait un
angle mort sur SC-001 (non-régression) et une PR ne peut pas contredire un SC
inscrit dans la spec. US3 (résistance aux détournements) est P2 mais **entrelacée**
avec US1 côté code : les gardes CSRF, la signature de cookie et les rejets
d'appels GitHub échoués sont *dans les mêmes fichiers* que le flux nominal. On
teste et on livre les trois ensemble.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : peut tourner en parallèle (fichiers distincts, pas de dépendance).
- **[Story]** : US1 / US2 / US3 pour les phases de user story.
- Chemin de fichier exact dans la description.

## Path Conventions

- Backend Python : `backend/app/` (code), `backend/tests/` (tests),
  `backend/alembic/versions/` (migrations).
- Docs racine : `AGENTS.md`, `backend/.env.example`.

---

## Phase 1 : Setup (infrastructure partagée)

**But** : préparer les emplacements et les variables. Aucune logique métier.

- [X] T001 [P] Ajouter dans `backend/app/core/config.py` les 6 nouveaux champs de `Settings` (`github_oauth_client_id`, `github_oauth_client_secret`, `session_secret_key`, `session_max_age_seconds` défaut `604800`, `session_cookie_secure` défaut `True`, `frontend_post_login_url` défaut `"/"`), avec les commentaires expliquant chacun. Aucun validateur — les valeurs vides sont acceptées, l'auth renverra 503 le moment venu (cf. FR-020).
- [X] T002 [P] Documenter les 6 variables dans `backend/.env.example` avec des valeurs vides et un bloc de commentaires reprenant le §2 de `quickstart.md` (comment créer une app OAuth GitHub perso).
- [X] T003 Créer les dossiers `backend/tests/test_auth/` et `backend/tests/test_auth/fixtures/` avec un `__init__.py` vide. Ajouter deux fixtures JSON figées : `github_user.json` (réponse type de `GET https://api.github.com/user` avec `id`, `login`, `email` renseigné) et `github_user_emails.json` (réponse type de `GET https://api.github.com/user/emails` — une entrée `verified=true, primary=true`, une entrée `verified=false`).

---

## Phase 2 : Fondations (prérequis bloquants)

**But** : modèle, migration, DTO. Rien qui parle HTTP encore.

**⚠️ CRITIQUE** : aucun travail de user story ne commence tant que cette phase
n'est pas verte.

### Tests fondations (rouges d'abord)

- [X] T004 [P] Créer `backend/tests/test_auth/test_user_model.py` : test qui importe `app.models.User`, instancie avec les champs minimaux (`github_id`, `github_login`, `email`), vérifie que `is_active` vaut `True` par défaut, que `created_at` est renseigné (`utcnow`), et qu'un deuxième `User` avec le même `github_id` lève `IntegrityError` au flush. **Ajout FR-008** : assertion `{"access_token", "github_token"}.isdisjoint(User.__table__.columns.keys())` — aucune colonne ne stocke le token GitHub. Test rouge (le modèle n'existe pas encore).
- [X] T005 [P] Créer `backend/tests/test_auth/test_user_repository.py` : quatre cas — `get_by_github_id` rend `None` sur base vide ; `upsert_from_github(payload)` crée une fiche et rend `(user, True)` ; un second `upsert_from_github` avec le même `github_id` mais un `github_login` différent met à jour la fiche et rend `(user, False)` ; **cas FR-010** : `upsert_from_github(github_id="A", email="x@y")` puis `upsert_from_github(github_id="B", email="x@y")` créent deux fiches distinctes (pas d'écrasement). Test rouge.

### Implémentation fondations

- [X] T006 [US1] Créer `backend/app/models/user.py` avec le modèle SQLAlchemy exact décrit dans `data-model.md` — `github_id` `String` `UNIQUE` indexé, `github_login`, `email` indexé (non-unique), `is_active` `Boolean` défaut `True`, `created_at` `DateTime` défaut `utcnow`, `athlete_id` FK optionnelle `ON DELETE SET NULL`. Relation `athlete` `lazy="joined"`, `passive_deletes=True`.
- [X] T007 [US1] Mettre à jour `backend/app/models/__init__.py` pour exporter `User` (ajout à `__all__` et import).
- [X] T008 [US1] Générer la révision Alembic : `cd backend && uv run alembic revision --autogenerate -m "add users table"`. Relire manuellement le fichier généré : vérifier qu'**aucune** table existante n'est modifiée, que la FK a bien `ondelete="SET NULL"` (à ajouter à la main si Alembic ne l'a pas détectée), et que `downgrade()` contient uniquement `op.drop_table("users")`. Renommer le fichier avec le suffixe `_add_users_table.py`.
- [X] T009 [US1] Créer `backend/app/repositories/user_repository.py` avec trois fonctions publiques : `get(db, user_id) -> User | None`, `get_by_github_id(db, github_id: str) -> User | None`, `upsert_from_github(db, *, github_id: str, github_login: str, email: str) -> tuple[User, bool]`. **Aucune** requête SQL dans les couches supérieures (Principe II). `upsert_from_github` met à jour `github_login` et `email` en place si la fiche existe, sinon crée.
- [X] T010 [P] [US1] Créer `backend/app/schemas/user.py` avec `UserRead` (Pydantic v2, `model_config = ConfigDict(from_attributes=True)`, champs `id: int`, `email: str`, `github_login: str`, `created_at: datetime`). **Pas** de `github_id` ni de `is_active` (cf. `data-model.md`).
- [X] T011 [US1] Vérifier que T004 et T005 passent au vert : `cd backend && uv run pytest tests/test_auth/test_user_model.py tests/test_auth/test_user_repository.py -v`.

**Checkpoint** : modèle, migration et repository livrés et testés — les user
stories peuvent démarrer.

---

## Phase 3 : User Story 1 — Authentification GitHub OAuth (P1)

**Goal** : un contributeur peut compléter le flux OAuth GitHub et obtenir une
session applicative. `GET /api/v1/auth/me` renvoie sa fiche.

**Independent Test** : mocker les endpoints GitHub via monkeypatch de
`httpx.Client`, appeler `/authorize` (302 vers GitHub, cookie `tcn_oauth_state`
posé), simuler le callback (302 vers `frontend_post_login_url`, cookie
`tcn_session` posé), appeler `/me` (200 avec `UserRead`), appeler `/logout`
(204), rappeler `/me` (401).

### Tests US1 (rouges d'abord)

- [X] T012 [P] [US1] Créer `backend/tests/test_auth/test_session_cookie.py` : `sign_session` puis `verify_session` rend `uid`. Cookie manipulé (dernier caractère changé) → signature invalide (retour `None`). Cookie signé avec une **autre** `SESSION_SECRET_KEY` → invalide. Cookie signé plus de `session_max_age_seconds + 1` secondes avant → invalide (utiliser `freezegun` OU un helper qui injecte une horodate ; pas de `time.sleep`).
- [X] T013 [P] [US1] Créer `backend/tests/test_auth/test_github_oauth_flow.py` : quatre cas nominaux — (a) `GET /api/v1/auth/github/authorize` renvoie 302, `Location` pointe vers `github.com/login/oauth/authorize` avec `client_id`, `scope=user:email`, `state` non vide, `redirect_uri` calculé ; un cookie `tcn_oauth_state` est posé. (b) `GET /api/v1/auth/github/callback?code=…&state=…` avec `httpx.Client.post` et `httpx.Client.get` monkeypatchés (token + `/user` + `/user/emails`) → 302 vers `frontend_post_login_url`, cookie `tcn_session` posé, un `User` créé en base. (c) rappel du callback pour le même utilisateur → aucune fiche dupliquée (`upsert_from_github`), une nouvelle session ouverte. (d) **cas FR-014** : `POST /api/v1/auth/logout` sans cookie → 204, header `Set-Cookie` contient `tcn_session=` avec `Max-Age=0` (no-op idempotent).
- [X] T014 [P] [US1] Ajouter à `test_github_oauth_flow.py` le cas « email public absent » : `github_user.json` mocké avec `email: null`, `github_user_emails.json` mocké → callback réussit, email retenu = premier `verified=true, primary=true`.
- [X] T015 [P] [US1] Créer `backend/tests/test_auth/test_deps_current_user.py` : test d'une route de test qui utilise `current_user` — 401 sans cookie, 200 avec un cookie valide, 401 avec un cookie forgé (signature invalide), 401 avec un cookie signé pointant sur un `user_id` inexistant. Test d'une route de test qui utilise `current_user_optional` — 200 dans tous les cas ci-dessus, avec `user=None` sur les cas 1, 3, 4 et `user=<User>` sur le cas 2.

### Implémentation US1

- [X] T016 [US1] Créer `backend/app/services/auth_service.py` :
  - `sign_session(secret_key: str, user_id: int) -> str` (payload `{"uid": user_id, "v": 1}`, `URLSafeTimedSerializer`)
  - `verify_session(secret_key: str, token: str, max_age: int) -> int | None`
  - `build_authorize_url(client_id: str, redirect_uri: str, state: str) -> str`
  - `exchange_code_for_token(http: httpx.Client, *, code: str, client_id: str, client_secret: str) -> str` — `POST /login/oauth/access_token` avec `Accept: application/json`
  - `fetch_github_identity(http: httpx.Client, *, token: str) -> dict` — appels `/user` puis `/user/emails` si nécessaire, rend `{"github_id": str, "github_login": str, "email": str}` ou lève `DomainError` française (« Aucun email GitHub vérifié disponible. » quand aucun email vérifié) — cf. FR-005.
  - `sign_state(secret_key: str, state: str) -> str` / `verify_state(secret_key: str, token: str, max_age: int) -> str | None` (préfixe/salt différent de la session, cf. `contracts/auth-api.md`).
  - Aucune référence à `Session` SQLAlchemy dans ce module.
- [X] T017 [US1] Ajouter à `backend/app/api/deps.py` les fonctions `current_user(request, db=Depends(get_db), settings=Depends(settings_dep)) -> User` (401 sinon) et `current_user_optional(...) -> User | None`. Elles lisent le cookie `tcn_session`, appellent `auth_service.verify_session`, puis `user_repository.get`. Si l'utilisateur n'est pas trouvé ou `is_active=False`, comportement idem cookie invalide.
- [X] T018 [US1] Créer `backend/app/api/v1/auth.py` avec les quatre endpoints exactement conformes à `contracts/auth-api.md` :
  - `GET /auth/github/authorize` : génère `state` (`secrets.token_urlsafe(32)`), pose `tcn_oauth_state`, renvoie `RedirectResponse` 302 vers l'URL GitHub. 503 si secrets manquants (`DomainError` « Authentification non configurée. »).
  - `GET /auth/github/callback` : lit `code`/`state`/`error`, vérifie le cookie `tcn_oauth_state`, échange le code, récupère l'identité, `upsert_from_github`, signe et pose `tcn_session`, supprime `tcn_oauth_state`, redirige vers `frontend_post_login_url`. Codes d'erreur exacts du contrat.
  - `POST /auth/logout` : supprime `tcn_session` (`Max-Age=0`), 204 même sans cookie.
  - `GET /auth/me` : `Depends(current_user)` → `UserRead`.
  - Utilise un `httpx.Client()` local dans une closure `_client_factory` **injectable** — permet le monkeypatch en tests. Pas de client partagé au module.
- [X] T019 [US1] Monter le router auth dans `backend/app/api/v1/router.py` en l'ajoutant au tuple d'imports et à la boucle `for module in (...)`.
- [X] T020 [US1] Ajouter dans `app/core/exceptions.py` la classe `AuthConfigurationError(DomainError)` (status 503, message par défaut « Authentification non configurée. »). Pour les cas 400/422, utiliser `HTTPException(status_code, detail="…message français…")` directement dans le router — l'exception handler `DomainError` sérialise déjà `{"detail": message}`, et `HTTPException` FastAPI fait la même chose sans nouvelle sous-classe. **Décision A1/I1** : pas d'autre `DomainError` ajoutée.
- [X] T021 [US1] Vérifier que T012, T013, T014, T015 passent au vert : `cd backend && uv run pytest tests/test_auth/ -v`.

**Checkpoint** : US1 fonctionnelle et testée. Le flux OAuth de bout en bout est
couvert. La suite entière du dépôt doit rester verte : `cd backend && uv run pytest -m "not integration"`.

---

## Phase 4 : User Story 2 — Non-régression du site public (P1)

**Goal** : les endpoints publics existants continuent de répondre sans
authentification, comme aujourd'hui. Aucun 401 nouveau, aucune redirection.

**Independent Test** : appeler chaque endpoint public listé dans
`contracts/auth-api.md` §« Non-régression du site public » sans cookie et
vérifier le même code de retour et la même charge utile qu'avant l'introduction
de l'auth.

### Tests US2

- [X] T022 [P] [US2] Créer `backend/tests/test_auth/test_public_routes_still_open.py` — parcourir la liste des endpoints publics : `GET /api/v1/health` (200), `GET /api/v1/scrape/detect?url=...` (200), `GET /api/v1/courses` (200), `GET /api/v1/athletes` (200), `GET /api/v1/stats/*` (200 sur au moins deux endpoints). Tous **sans** cookie. Vérifier qu'aucun `Set-Cookie: tcn_session` n'est renvoyé (l'auth ne se pose pas sur les routes publiques).
- [X] T022 [P] [US2] Ajouter à `test_public_routes_still_open.py` un test négatif : `GET /api/v1/auth/me` sans cookie → 401 (borne haute — c'est l'unique endpoint qui doit répondre 401 sans session).

### Implémentation US2

Il n'y a **rien à implémenter côté US2** : la non-régression est une conséquence
de FR-017 (« pas de contrôle d'authentification global ») et de la conception
d'US1 qui n'attache l'auth qu'aux quatre endpoints `/api/v1/auth/*`. Les tâches
de test suffisent à valider la contrainte.

**Checkpoint** : US2 validée. Toutes les routes publiques répondent inchangées.

---

## Phase 5 : User Story 3 — Résistance aux détournements OAuth (P2)

**Goal** : les tentatives de forge (state absent/inconnu, cookie forgé, cookie
expiré, code GitHub invalide) sont toutes rejetées sans ouvrir de session.

**Independent Test** : chaque cas d'attaque de la spec §User Story 3 a un test
dédié. Aucun cookie `tcn_session` n'est posé, aucun `User` créé.

### Tests US3

- [X] T022 [P] [US3] Ajouter à `test_github_oauth_flow.py` les cas de refus du callback :
  - `state` absent → 400 « État CSRF invalide. »
  - `state` présent mais aucun cookie `tcn_oauth_state` → 400 idem.
  - `state` présent, cookie présent, valeurs différentes → 400 idem.
  - `state` signé plus de 10 minutes auparavant → 400 idem.
  - GitHub renvoie `error=access_denied` en query → 400 « Autorisation GitHub refusée. »
  - Échange du `code` échoue (mock du POST token renvoyant 400) → 400 idem.
  - `/user` renvoie un utilisateur sans email ET `/user/emails` renvoie une liste vide (ou aucun `verified=true`) → 422 « Aucun email GitHub vérifié disponible. »
- [X] T022 [P] [US3] Ajouter à `test_session_cookie.py` le cas rotation de `SESSION_SECRET_KEY` : un cookie signé par la clé A, vérifié avec la clé B → invalide. Vérifier dans `test_deps_current_user.py` qu'après une rotation simulée, un ancien cookie déclenche 401 sur `/me`.
- [X] T022 [P] [US3] Ajouter dans `test_github_oauth_flow.py` un test « secrets manquants » : `GITHUB_OAUTH_CLIENT_ID` vide → `GET /authorize` renvoie 503 « Authentification non configurée. » ; `SESSION_SECRET_KEY` vide → même comportement. Le site public reste 200 pendant ce test (recouper avec US2).

### Implémentation US3

Idem US2 : la conception d'US1 (T016-T018) intègre déjà tous les rejets. Ces
tâches ne demandent que des tests de non-régression sur les cas d'attaque. Si
un test échoue, corriger le service `auth_service` ou le router — pas de
nouveau fichier à créer.

**Checkpoint** : US3 validée. Toute la matrice de rejets OAuth passe.

---

## Phase 6 : Polish & documentation

- [X] T027 [P] Mettre à jour `AGENTS.md` : ajouter une section « Authentification » d'environ 30 lignes, placée après « Architecture backend » et avant « Fournisseurs supportés ». Contenu : les 4 endpoints, les 6 variables d'environnement, ce qui est protégé (rien sur ce ticket, hormis `/auth/me`), ce qui est renvoyé à #115 (rôles, RBAC, `create-admin`). Copier-coller les sections utiles de `quickstart.md`.
- [X] T028 [P] Vérifier que la suite complète est verte : `cd backend && uv run pytest -m "not integration"` et `cd backend && uv run ruff check .`.
- [X] T029 [P] Vérifier manuellement le diff de la migration Alembic (`cd backend && uv run alembic upgrade head` sur une base SQLite vide de dev, puis `uv run alembic downgrade -1`). Aucune ligne de log d'erreur ni de warning inattendu.
- [ ] T030 Rejeu du `quickstart.md` sur une base locale : créer une app OAuth GitHub perso, remplir `.env`, lancer le backend, faire le flux dans un navigateur, vérifier `curl /auth/me`. **Reporté au relecteur humain** — un job automatisé ne peut pas créer d'app OAuth GitHub ni compléter le flux dans un navigateur. Les tests couvrent le flux avec un client HTTP mocké ; le rejeu manuel valide qu'aucune brique environnementale (Render, proxy, cookie Secure) ne casse en prod.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** : aucune dépendance, peut démarrer immédiatement.
- **Foundational (Phase 2)** : dépend de T001/T002 (config). Bloque toutes les
  user stories.
- **US1 (Phase 3)** : dépend de la fin de Phase 2 (modèle et repository livrés).
- **US2 (Phase 4)** : dépend de la fin d'US1 (le router auth doit exister pour
  que les tests de non-régression puissent démarrer l'app).
- **US3 (Phase 5)** : dépend de la fin d'US1 (les rejets sont testés sur les
  mêmes endpoints).
- **Polish (Phase 6)** : dépend de toutes les user stories.

### User Story Dependencies

- **US1 (P1)** : peut démarrer dès la fin de Phase 2.
- **US2 (P1)** : peut démarrer dès la fin d'US1 (les tests appellent l'API
  entière, y compris `/auth/*`).
- **US3 (P2)** : peut démarrer dès la fin d'US1. En pratique, **US2 et US3 se
  livrent dans la même PR qu'US1** — ils testent le même code, séparer la
  livraison n'apporte rien et retarderait la validation de SC-001.

### Within Each User Story

- Tests **d'abord** (Principe III), au rouge, puis implémentation.
- Modèle / repository / DTO avant service.
- Service avant router.
- Router avant intégration.

### Parallel Opportunities

- T001/T002 en parallèle (deux fichiers indépendants).
- T004/T005 en parallèle (deux fichiers de test).
- T010 en parallèle de T006/T007/T009 (schéma indépendant du modèle et du
  repository — Pydantic ne dépend que de la présence du fichier, pas de son
  état d'exécution).
- T012/T013/T014/T015 tous en parallèle (fichiers de test distincts).
- T022/T023 en parallèle.
- T024/T025/T026 en parallèle.
- T027/T028/T029 en parallèle.

---

## Parallel Example: User Story 1

```bash
# Lancer les 4 tests d'US1 en parallèle (avant toute implémentation) :
Task: "T012 backend/tests/test_auth/test_session_cookie.py"
Task: "T013 backend/tests/test_auth/test_github_oauth_flow.py"
Task: "T014 (ajout au fichier T013 — même fichier, séquentiel)"
Task: "T015 backend/tests/test_auth/test_deps_current_user.py"

# Écrire les 3 modèles-support d'US1 en parallèle une fois les tests rouges :
Task: "T006 backend/app/models/user.py"
Task: "T010 backend/app/schemas/user.py"

# T007 (models/__init__.py) et T009 (user_repository.py) suivent T006.
```

---

## Implementation Strategy

### MVP First (US1)

1. Phase 1 (setup) → Phase 2 (fondations) → Phase 3 (US1).
2. **STOP + valider** : le flux OAuth complet fonctionne, `/me` répond, `/logout`
   invalide.
3. Passer à Phase 4 + Phase 5 (US2/US3) avant merge — obligatoire pour couvrir
   SC-001 et FR-003/004/005/012.

### Livraison incrémentale au sens Speckit

En principe, US1 seule est une MVP démontrable. En pratique dans ce dépôt :

- US1 seule (sans US2) ne peut pas être livrée car SC-001 est un critère de
  succès explicite du ticket.
- US1 seule (sans US3) ne peut pas être livrée car les rejets OAuth sont dans
  les mêmes fichiers — les tester ensemble est le seul moyen d'éviter de
  laisser des chemins d'attaque au vert.

Donc : PR unique livrant les trois user stories, dans l'ordre US1 → US2 → US3.

### Parallel Team Strategy

Ce ticket est un job d'une seule personne (ou d'un seul agent) sur une seule
session : les user stories n'ont pas assez de découplage pour être partagées
entre plusieurs contributeurs. La parallélisation utile est **intra-story**
(tests en parallèle, modèles en parallèle) — pas inter-story.

---

## Notes

- **Tests avant tout** (Principe III). Toute déviation bloque le passage à
  `/speckit-analyze`.
- Aucune dépendance nouvelle en production. `itsdangerous` est déjà là
  transitivement (via Starlette) ; on l'importe explicitement, sans l'ajouter à
  `pyproject.toml`.
- La migration Alembic doit ajouter **uniquement** la table `users` — toute
  modification d'une table existante dans la révision autogénérée est un signal
  à corriger avant merge (FR-018).
- Un `git diff` de la PR doit contenir **zéro** secret en clair (SC-003).
