---

description: "Task list — Socle d'authentification SSO pour le back-office admin (#114)"
---

# Tasks: Socle d'authentification SSO pour le back-office admin

**Input**: Design documents from `specs/20260801-145428-auth-socle-sso/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/auth-api.md](./contracts/auth-api.md),
[quickstart.md](./quickstart.md)

**Sondage faisant autorité** :
[`docs/superpowers/specs/2026-08-01-auth-librairies-sondage.md`](../../docs/superpowers/specs/2026-08-01-auth-librairies-sondage.md)

**Tests**: Le Principe III de la constitution v1.1.0 est **non-négociable** — TDD sans réseau.
Toute tâche de test porte la mention **(rouge)** et **doit échouer** avant que sa tâche
d'implémentation ne soit entreprise. Aucune dérogation n'est demandée pour cette feature.

**Organization**: tâches groupées par user story. Chaque story est implémentable et testable
indépendamment.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable (fichiers distincts, aucune dépendance sur une tâche inachevée)
- **[Story]** : US1, US2, US3 — voir [spec.md](./spec.md)

## Path Conventions

Application web : `backend/app/`, `backend/tests/`, `frontend/`. Chemins réels dans
[plan.md](./plan.md) §Project Structure.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: dépendances, configuration, et — d'abord — **refermer l'angle mort du garde SSRF**.
Rien d'autre ne peut commencer tant qu'une sortie HTTP Authlib peut échapper au contrôle de
destination.

- [X] T001 Ajouter `authlib` aux `dependencies` de `backend/pyproject.toml` (jamais dans `[dependency-groups] dev`, que `--no-dev` écarterait en production) et régénérer `backend/uv.lock` par `uv lock` — **dans le même commit**, la CI tournant en `uv sync --locked` et Docker/Render en `--frozen`
- [X] T002 Étendre le détecteur AST de `backend/tests/test_core_http.py` : ajouter aux tests de niveau les cas `from authlib.integrations.httpx_client import OAuth2Client` → `[2]` et `httpx.HTTPTransport()` → `[2]` **(rouge)**
- [X] T003 Faire passer T002 : dans `backend/tests/test_core_http.py`, ajouter `HTTPTransport`/`AsyncHTTPTransport` à `_VERBES_HTTPX` et faire résoudre à `_httpx_nu` les liaisons du module `authlib.integrations.httpx_client` (verbes `OAuth2Client`, `AsyncOAuth2Client`, `OAuth1Client`)
- [X] T004 Exposer `guarded_transport(inner=None)` publiquement dans `backend/app/core/http.py` et faire `client()` l'appeler, pour qu'il n'existe qu'**une seule** construction du garde ; ajuster l'allowlist de fichiers de `test_meta_aucun_httpx_nu_dans_app` si nécessaire
- [X] T005 [P] Ajouter `AuthUnavailableError(DomainError)` à `backend/app/core/exceptions.py` — `status_code = 503`, message **français** (clause « Cas mixte — les `DomainError` » du Principe I)
- [X] T006 [P] Ajouter à `backend/tests/test_config.py` les tests de parsing CSV d'`AUTH_ALLOWED_EMAILS` et le refus d'une clé de signature de moins de 32 caractères **(rouge)**
- [X] T007 Faire passer T006 : ajouter les 8 réglages `auth_*` à `backend/app/core/config.py`, `auth_allowed_emails` en `Annotated[list[str], NoDecode]` avec validateur `mode="before"` calqué sur `_split_cors`

**Checkpoint** : `uv run pytest -m "not integration"` vert, `uv run ruff check .` propre. Le garde
voit désormais `OAuth2Client`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: modèles, migration, repositories et isolation des tests. Bloquant pour **toutes** les
user stories.

- [X] T008 Créer `backend/tests/test_auth/conftest.py` avec une fixture **autouse** qui pose les réglages par `monkeypatch.setenv` et appelle `get_settings.cache_clear()` **avant et après** chaque test — `get_settings()` est `@lru_cache` et lit `.env`, sinon le secret d'un développeur ferait passer les tests pour la mauvaise raison (motif déjà présent dans `backend/tests/test_migrations.py`)
- [X] T009 [P] Capturer sous `backend/tests/test_auth/fixtures/` les charges utiles GitHub réelles : réponse d'échange de jeton, `/user` avec adresse publique, `/user` **sans** adresse publique, et `/user/emails` (dont une adresse non vérifiée)
- [X] T010 [P] Écrire `backend/tests/test_auth/test_models.py` : contraintes `uq_identity_provider_subject` et `uq_user_session_token`, `users.email` **non unique** (deux utilisateurs peuvent porter la même adresse — FR-003), `created_at` alimenté par `utcnow` **(rouge)**
- [X] T011 Créer `backend/app/models/user.py`, `identity.py`, `user_session.py` selon [data-model.md](./data-model.md), et **les enregistrer dans `backend/app/models/__init__.py`** — `backend/tests/conftest.py` fait `import app.models` puis `create_all`, sans quoi les tables n'existent pas en test
- [X] T012 Générer la révision Alembic (`uv run alembic revision --autogenerate`), la **relire à la main**, vérifier l'absence d'`ondelete` sur `users.athlete_id`, la présence des contraintes nommées, et l'**absence de toute colonne de rôle sur `users`** (FR-041, SC-014 : le rôle de #115 est relatif à une organisation et vivra dans une association, pas ici) ; étendre `backend/tests/test_migrations.py` au cycle `upgrade` → `downgrade` → `upgrade`
- [X] T013 [P] Écrire `backend/tests/test_auth/test_repositories.py` **(rouge)** : résolution par `(provider, subject)`, création d'un **nouvel** utilisateur sur adresse déjà connue, rafraîchissement de l'adresse, unicité de `token_hash`, suppression d'une session, suppression des sessions expirées
- [X] T014 Créer `backend/app/repositories/user_repository.py`, `identity_repository.py`, `session_repository.py` — **seule** couche à construire des requêtes ; les services portent la transaction, conformément à `import_service` et `scrape_service`

**Checkpoint** : modèles, migration et repositories verts. Aucune user story n'est encore
implémentée.

---

## Phase 3: User Story 2 — Le site public reste intégralement accessible sans compte (Priority: P1)

**Goal**: garantir qu'aucune ressource publique existante n'exige de session, avant, pendant et
après l'introduction de l'authentification.

**Independent Test**: dérouler l'intégralité des parcours publics sans jamais se connecter et
constater l'identité des comportements avec l'état antérieur.

**Placée avant US1 bien qu'également P1** : c'est le filet. Elle ne coûte que des tests, elle est
exécutable immédiatement, et elle doit rester verte pendant tout le reste. L'écrire après aurait
laissé une régression passer inaperçue pendant l'implémentation.

- [X] T015 [P] [US2] Écrire `backend/tests/test_auth/test_public_routes_still_open.py` : **inventorier les routes de l'application** depuis `app.routes` plutôt que d'en tenir une liste à la main, et vérifier que chacune répond sans cookie — une liste manuelle vieillirait en silence
- [X] T016 [US2] Ajouter au même fichier un test vérifiant qu'aucune dépendance globale n'est montée sur l'application ni sur les routers existants — la protection future de #115 doit être posée route par route, jamais par un `dependencies=` global qui fermerait le site public sans qu'on le voie

**Checkpoint** : US2 est vert et le restera. Toute tâche ultérieure qui le casse est un défaut, pas
un progrès.

---

## Phase 4: User Story 1 — Un contributeur du club ouvre une session (Priority: P1)

**Goal**: dérouler le parcours nominal de bout en bout — connexion, session persistante, identité
affichée, déconnexion d'un seul appareil.

**Independent Test**: se connecter dans un navigateur, vérifier l'identité affichée, rafraîchir,
se déconnecter, vérifier que l'accès authentifié est refermé.

### Tests (rouges) — services

- [X] T017 [P] [US1] `backend/tests/test_auth/test_state.py` **(rouge)** : signature et relecture du jeton d'état, rejet sur mauvaise clé, rejet à expiration, `round_trip` restitué **verbatim** sans être interprété, `provider` restitué
- [X] T018 [P] [US1] `backend/tests/test_auth/test_session.py` **(rouge)** : le jeton rendu fait au moins 43 caractères, la base ne contient **que** son SHA-256, l'invariant à trois conditions (existe / non expirée / utilisateur actif), la désactivation ferme immédiatement, la déconnexion ne ferme **que** cette session
- [X] T019 [P] [US1] `backend/tests/test_auth/test_provisioning.py` **(rouge)** : résolution par `(provider, subject)` seul, **création d'un nouvel utilisateur** quand l'adresse existe déjà sous une autre identité, rafraîchissement de l'adresse d'une identité connue, aucune liaison implicite
- [X] T020 [P] [US1] `backend/tests/test_auth/test_registry.py` **(rouge)** : enregistrement d'une **doublure par fixture**, déroulé complet du flux sur cette doublure, et test normatif « le registre importé à froid ne contient que `github` »
- [X] T021 [P] [US1] `backend/tests/test_auth/test_github_provider.py` **(rouge)**, sur `httpx.MockTransport` et les fixtures de T009 : URL d'autorisation portant `state` + `code_challenge` + `code_challenge_method=S256`, échange de jeton, identité, **repli sur `/user/emails`** quand l'adresse publique est absente, et sélection de l'adresse **vérifiée** et primaire
- [X] T022 [US1] `backend/tests/test_auth/test_flow.py` **(rouge)** : `start_login` puis `complete_login` de bout en bout sur la doublure, ouverture de session, et suppression opportuniste des sessions expirées de l'utilisateur

### Tests (rouges) — API et contrat

- [X] T023 [P] [US1] `backend/tests/test_auth/test_api_methods.py` **(rouge)** : `GET /auth/methods` rend `[{slug,label}]` quand configuré, et `[]` quand la liste d'autorisation est vide ou l'authentification non configurée
- [X] T024 [P] [US1] `backend/tests/test_auth/test_api_flow.py` **(rouge)** : `authorize` rend 302 et pose le cookie d'état ; `callback` nominal rend 302 vers la destination configurée, pose le cookie de session et **efface** le cookie d'état ; `provider` inconnu rend 404
- [X] T025 [P] [US1] `backend/tests/test_auth/test_api_me_logout.py` **(rouge)** : `GET /auth/me` rend 200 avec session et **401** sans (jamais « 200 avec corps nul » — point de contrat figé) ; `POST /auth/logout` rend 204 et reste **idempotent** sans cookie
- [X] T026 [P] [US1] `backend/tests/test_auth/test_cookies.py` **(rouge)** : préfixe `__Host-` quand `secure` est actif, nom **dérivé** sans préfixe quand il ne l'est pas, `HttpOnly`, `SameSite=Lax`, `Path=/`, et **jamais** d'attribut `Domain`
- [X] T027 [P] [US1] `backend/tests/test_auth/test_cache_headers.py` **(rouge)** : **toutes** les réponses de `/api/v1/auth/*` portent `Cache-Control: no-store` et `Vary: Cookie`

### Implémentation — backend

- [X] T028 [P] [US1] Créer `backend/app/services/auth/idp/base.py` : `ExternalIdentity` (dont `email_verified`), `AuthorizationRequest(url, round_trip)` et le Protocol `IdentityProvider` — la signature **n'énumère aucun mécanisme**, `round_trip` est opaque
- [X] T029 [US1] Créer `backend/app/services/auth/idp/registry.py` : registre, `register()`, `get()`, `enabled_methods()`. La doublure de test **n'y est jamais enregistrée au niveau module**
- [X] T030 [US1] Créer `backend/app/services/auth/idp/github.py` : `OAuth2Client` construit avec `transport=guarded_transport()`, `follow_redirects=False` (httpx réémet le corps sur 307/308, et ce corps porte le `client_secret`), `timeout` explicite et `code_challenge_method="S256"` — **sans lequel `create_authorization_url` ignore silencieusement le `code_verifier`**
- [X] T031 [P] [US1] Créer `backend/app/services/auth/state.py` : signature et vérification du jeton d'état en JWS HS256 via `joserfc`
- [X] T032 [P] [US1] Créer `backend/app/services/auth/session.py` : génération du jeton opaque, hachage, ouverture, résolution (invariant à trois conditions), suppression
- [X] T033 [US1] Créer `backend/app/services/auth/provisioning.py` : `resolve_user(db, identity)` — refus d'une adresse non certifiée, **puis** liste d'autorisation, **puis** résolution par `(provider, subject)`
- [X] T034 [US1] Créer `backend/app/services/auth/flow.py` : `start_login()` et `complete_login()`, qui orchestrent registre, état, provisionnement et session sans jamais construire de requête
- [X] T035 [P] [US1] Créer `backend/app/schemas/auth.py` : `AuthMethodRead`, `SessionUserRead` (sérialisation `…Z` de `created_at`, comme les DTO existants)
- [X] T036 [US1] Ajouter `current_user` à `backend/app/api/deps.py` — passe par `services/auth/session.py`, **jamais** par un repository directement (le court-circuit que commet la PR #159)
- [X] T037 [US1] Créer `backend/app/api/v1/auth.py` (router mince, les 5 endpoints) avec la dépendance de router posant `Cache-Control: no-store` et `Vary: Cookie`, et le monter dans `backend/app/api/v1/router.py`

### Tests (rouges) et implémentation — frontend

- [X] T038 [P] [US1] Écrire `frontend/lib/__tests__/api-error.test.ts` **(rouge)** : une réponse non-OK lève une erreur **portant le statut HTTP** (aujourd'hui un `Error` nu, un 401 est indiscernable d'un 500)
- [X] T039 [US1] Introduire `ApiError` dans `frontend/lib/api/client.ts` et ajouter `SessionUser` / `AuthMethod` à `frontend/lib/types.ts`
- [X] T040 [P] [US1] Écrire `frontend/lib/queries/auth.test.ts` **(rouge)** : `useSession()` rend `null` sur 401 sans propager d'erreur, et l'utilisateur sur 200
- [X] T041 [US1] Créer `frontend/lib/queries/auth.ts` (`useSession`) et sa clé dans `frontend/lib/queries/keys.ts`
- [X] T042 [P] [US1] Écrire `frontend/app/login/page.test.tsx` **(rouge)** : un bouton **par méthode rendue par l'API**, et un message explicite quand la liste est vide — aucune méthode n'est codée en dur
- [X] T043 [US1] Créer `frontend/app/login/page.tsx`
- [X] T044 [P] [US1] Étendre `frontend/components/layout/TcnTopbar.test.tsx` **(rouge)** : « Se connecter » si anonyme, menu utilisateur si connecté, **dans le bloc desktop et dans le tiroir mobile**
- [X] T045 [US1] Créer `frontend/components/auth/UserMenu.tsx` et le poser aux **deux** endroits de `frontend/components/layout/TcnTopbar.tsx` — toute action de cette barre y est déclarée deux fois
- [X] T046 [P] [US1] Écrire le test de garde de `frontend/app/admin/layout.tsx` **(rouge)** : redirection vers `/login` sans session, rendu des enfants avec session
- [X] T047 [US1] Ajouter `serverFetchAuthed()` à `frontend/lib/api/server.ts` — **sans modifier `serverFetch`**, que six pages publiques en rendu serveur utilisent. Pas de test rouge propre : son unique consommateur est le layout de T048, dont T046 couvre les deux comportements (redirection sans session, rendu avec session). Si le helper gagne un second consommateur, il gagne son test
- [X] T048 [US1] Créer `frontend/app/admin/layout.tsx` (garde par validation réelle, pas un `middleware.ts`)

**Checkpoint** : le parcours nominal est déroulable dans un navigateur (cf. [quickstart.md](./quickstart.md)
§4). US2 doit toujours être vert.

---

## Phase 5: User Story 3 — Les tentatives illégitimes sont refusées lisiblement (Priority: P2)

**Goal**: chaque refus ramène sur la page de connexion avec un message français, sans jamais
afficher de page de données techniques ni laisser d'utilisateur enregistré.

**Independent Test**: provoquer chaque cas de refus et vérifier le message affiché, l'absence de
session et l'absence d'utilisateur créé.

### Tests (rouges)

- [X] T049 [P] [US3] `backend/tests/test_auth/test_state_rejection.py` **(rouge)**, un cas par forme : cookie d'état absent, signature altérée, expiré, `state` ne correspondant pas, **rejoué**, et **émis pour un autre fournisseur** que le segment d'URL — tous rendent `state_mismatch`
- [X] T050 [P] [US3] `backend/tests/test_auth/test_identity_rejection.py` **(rouge)** : adresse non certifiée → `email_unverified` ; adresse hors liste → `account_not_allowed` ; et dans les deux cas **aucun utilisateur ni aucune identité en base**
- [X] T051 [P] [US3] `backend/tests/test_auth/test_provider_errors.py` **(rouge)** : refus de consentement → `provider_error` ; fournisseur injoignable ou réponse inexploitable → `provider_unavailable`
- [X] T052 [P] [US3] `backend/tests/test_auth/test_not_configured.py` **(rouge)** : `authorize` rend **503** avec un message français quand l'authentification n'est pas configurée, et le site public reste intact
- [X] T053 [US3] `backend/tests/test_auth/test_no_network_before_validation.py` **(rouge)** : sur **chacun** des chemins d'échec local, le transport ne voit **aucune** requête — l'ordre du contrat n'est pas une préférence de style, c'est ce qui empêche un retour de parcours de saturer le pool de 40 threads et d'emporter le site public
- [X] T054 [US3] `backend/tests/test_auth/test_state_cleared.py` **(rouge)**, paramétré sur **tous** les chemins de sortie du callback, succès compris : le cookie d'état est effacé
- [X] T055 [P] [US3] `backend/tests/test_auth/test_error_codes_closed_set.py` **(rouge)** : le paramètre `error` n'est **jamais** autre chose qu'une des cinq valeurs du contrat — aucun message du fournisseur, aucune donnée d'entrée
- [X] T056 [P] [US3] `frontend/app/login/page.test.tsx` étendu **(rouge)** : chaque code d'erreur s'affiche en **français**, et un code inconnu retombe sur un message générique sans être rendu verbatim

### Implémentation

- [X] T057 [US3] Implémenter dans `backend/app/api/v1/auth.py` l'ordre contractuel du callback (validation locale → effacement de l'état → présence du `code` → réseau) et la redirection vers `/login?error=<code>` sur **tous** les chemins d'échec
- [X] T058 [US3] Définir l'ensemble fermé des codes d'erreur côté backend et lever `AuthUnavailableError` là où l'authentification n'est pas configurée
- [X] T059 [US3] Ajouter les libellés **français** des codes d'erreur à `frontend/lib/constants.ts`, sur le modèle de `PROVIDER_LABELS`, et les afficher dans `frontend/app/login/page.tsx`

### Filet transverse (après T057-T059)

- [X] T067 [US3] `backend/tests/test_auth/test_no_secret_logged.py` (**FR-038**) : dérouler le callback nominal **et chacun** des chemins d'échec sous `caplog`, et vérifier qu'aucun enregistrement ne contient le `client_secret`, le jeton de session en clair, ni le paramètre `code`. **Pas de mention (rouge)** : c'est un filet de non-régression comme T015/T016, pas un comportement à faire advenir — il doit passer dès le premier jet et le rester. Placé après T057 parce qu'il déroule le callback, qui doit exister

**Checkpoint** : les trois user stories sont vertes, `uv run pytest -m "not integration"` et
`npm test` passent.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T060 [P] Ajouter la section « **Authentification** » à `AGENTS.md` (**AC7 de l'issue #114**) : les trois tables, l'invariant jeton opaque / empreinte, le registre `idp/` et la collision de vocabulaire avec « provider » (chronométreur), les 8 réglages `AUTH_*`, le fait qu'**aucune route existante n'est protégée** et que la garde `/admin` est **d'interface seulement**, l'obligation de passer par `core.http.guarded_transport()`, et le piège multi-worktree. **Trois points supplémentaires, chacun non devinable depuis le code** : (a) le rôle de #115 est relatif à une **organisation** et ne se pose donc **pas** en colonne sur `users` (FR-041) ; (b) la **fermeture en masse des sessions** est une procédure, pas un outil — désactiver le compte pour un utilisateur, supprimer toutes les sessions enregistrées pour la totalité (FR-016) ; (c) une **rotation de `AUTH_SESSION_SECRET_KEY` ne ferme aucune session**, le jeton étant opaque et vérifié en base plutôt que signé — croire l'inverse ferait tenir une fuite pour colmatée
- [X] T061 [P] Ajouter les 8 réglages `AUTH_*` à `backend/.env.example`, secrets laissés vides
  — posé **à la main par le mainteneur** : l'accès aux fichiers `.env*` était refusé par
  les permissions de la session d'implémentation.
- [X] T062 [P] Ajouter les `AUTH_*` à `render.yaml` en `sync: false`, avec `generateValue: true` pour `AUTH_SESSION_SECRET_KEY` ; documenter les valeurs par environnement dans `docs/ci-cd.md`, dont la décision sur les déploiements de prévisualisation (dont l'URL change à chaque exécution, donc sans URL de retour stable)
- [X] T063 [P] Ajouter les 8 variables au tableau de `backend/README.md`
- [X] T064 [P] Ajouter à `.worktreeinclude`, en face de la ligne `.env`, l'avertissement miroir de celui de `.env.local` : n'y figer ni `AUTH_REDIRECT_BASE_URL` ni les identifiants OAuth, qui visent un worktree précis
- [X] T065 Vérification finale : `cd backend && uv run pytest -m "not integration"` et `uv run ruff check .`, puis `cd frontend && npm test`, `npm run lint` et `npm run build`
- [ ] T066 Dérouler [quickstart.md](./quickstart.md) **à la main dans un navigateur** — création de l'application OAuth GitHub et consentement humain ne sont pas automatisables. **Cette tâche est déléguée au relecteur** et ne peut pas être cochée par un agent

---

## Dependencies

```text
Phase 1 (Setup)          ──> bloque tout
   T002 → T003 → T004        (le garde avant le premier appel Authlib)
   T006 → T007
Phase 2 (Foundational)   ──> bloque toutes les stories
   T008, T009 → T010 → T011 → T012
                T013 → T014
Phase 3 (US2, P1)        ──> indépendante ; à faire tôt, doit rester verte ensuite
Phase 4 (US1, P1)        ──> dépend des phases 1 et 2
   T017-T027 (rouges) → T028-T037 (backend) → T038-T048 (frontend)
   T028 → T029 → T030
   T031, T032 → T033 → T034 → T036 → T037
   T039 → T041 → T043 → T045
Phase 5 (US3, P2)        ──> dépend d'US1 (les endpoints doivent exister)
   T049-T056 (rouges) → T057-T059 → T067 (filet, déroule le callback)
Phase 6 (Polish)         ──> dépend de tout
```

**T067 est numéroté hors séquence** : ajouté après la clarification du 2026-08-02, il appartient à
la **Phase 5** et s'exécute après T059, malgré un identifiant supérieur à ceux de la Phase 6. Les
identifiants existants n'ont pas été décalés — ils sont cités dans ce bloc de dépendances, dans les
opportunités de parallélisation et dans l'historique de la branche. **L'ordre fait foi ici, pas le
numéro.**

**Ordre de livraison des stories** : US2 → US1 → US3. US2 précède parce qu'elle est le filet ;
US3 suit US1 parce qu'un refus suppose un parcours.

## Parallel Opportunities

- **Phase 1** : T005 et T006 en parallèle de T002-T004.
- **Phase 2** : T009 et T010 en parallèle ; T013 en parallèle de T010-T012.
- **Phase 4, tests** : T017 à T021 sont **cinq fichiers distincts**, tous parallélisables ; T023 à
  T027 de même.
- **Phase 4, implémentation** : T028, T031, T032 et T035 touchent des fichiers distincts.
- **Phase 5, tests** : T049, T050, T051, T052, T055 et T056 sont parallélisables ; T053 et T054 ne
  le sont pas, ils portent sur le router. **T067 non plus** : il déroule le callback, donc il vient
  après T057-T059.
- **Phase 6** : T060 à T064 sont cinq fichiers distincts, tous parallélisables.

## Implementation Strategy

**MVP** = Phase 1 + Phase 2 + Phase 3 (US2) + Phase 4 (US1). À ce stade, un contributeur autorisé
se connecte, la session tient, la déconnexion fonctionne, et le site public est prouvé intact.
US3 durcit les refus — indispensable avant tout déploiement, mais non bloquant pour démontrer la
feature.

**Incréments livrables** :

1. **Phases 1-2** — aucune fonctionnalité visible, mais le garde SSRF est refermé et le schéma
   existe. Commit possible, suite verte.
2. **Phase 3** — le filet de non-régression. Commit.
3. **Phase 4** — la feature est démontrable dans un navigateur. Commit.
4. **Phase 5** — les refus sont lisibles et l'ordre d'exécution est verrouillé. Commit.
5. **Phase 6** — documentation et configuration de déploiement. Commit.

**Deux garde-fous d'exécution**, tirés d'AGENTS.md :

- l'**étape 4 « Project Setup Verification » de `/speckit-implement` est à ne pas dérouler** : elle
  ajoute des motifs génériques aux fichiers d'ignore existants, hors périmètre de toute feature, et
  toucher au `.gitignore` de la racine change ce que `.worktreeinclude` recopie ;
- les hooks git de Spec Kit committent via `git add .`, donc **tout le worktree** : les commits sont
  faits à la main, en ciblant les fichiers.
