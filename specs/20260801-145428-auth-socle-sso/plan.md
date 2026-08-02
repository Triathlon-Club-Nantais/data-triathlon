# Implementation Plan: Socle d'authentification SSO pour le back-office admin

**Branch**: `20260801-145428-auth-socle-sso` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260801-145428-auth-socle-sso/spec.md`

**Sondage faisant autorité** : [`docs/superpowers/specs/2026-08-01-auth-librairies-sondage.md`](../../docs/superpowers/specs/2026-08-01-auth-librairies-sondage.md).
Il **prime** sur ce plan. Toute divergence se tranche en re-sondant, jamais en raisonnant.

## Summary

Ouvrir une session applicative par délégation à GitHub, sans jamais détenir de mot de passe, et
laisser le site public strictement intact. Trois tables (`users`, `identities`, `user_sessions`),
un registre de fournisseurs d'identité derrière un Protocol dont le contrat **n'énumère pas** les
mécanismes, une session portée par un jeton opaque dont la base ne garde que l'empreinte, et un
écran de connexion qui se construit à partir des moyens que le backend déclare.

L'approche technique est arbitrée par le sondage : `authlib.integrations.httpx_client.OAuth2Client`,
**synchrone** et héritant de `httpx.Client`, ce qui permet d'y injecter le transport gardé du projet
et donc de faire passer l'intégralité du trafic OAuth par le contrôle de destination de #101 —
sans surcharge, sans code recopié, et sans contaminer d'`async` une base de code qui n'en a aucun.

## Technical Context

**Language/Version**: Python 3.13 (backend) · TypeScript strict, Next.js 16 App Router (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 **sync**, Pydantic v2, pydantic-settings, Alembic.
**Ajout** : `authlib` (BSD-3), qui apporte `cryptography` et `joserfc` en transitif. `joserfc` est
employé **directement** pour signer le jeton d'état court. `itsdangerous` — la dépendance qu'ajoutait
la PR #159 — devient inutile.

**Storage**: PostgreSQL (Supabase) en production, SQLite en développement et en test.

**Testing**: pytest (backend) · Vitest + Testing Library (frontend). Couture réseau : `transport=`
sur le client OAuth, remplacé par `httpx.MockTransport` — aucun monkeypatch de symbole global.

**Target Platform**: backend sur Render, frontend sur Vercel, l'interface proxifiant `/api/*`.

**Project Type**: application web, backend et frontend dans le même dépôt.

**Performance Goals**: aucune dégradation du site public. Le retour de parcours coûte **au plus
deux** allers-retours réseau vers GitHub. Une requête authentifiée coûte une lecture indexée plus
une jointure.

**Constraints**:
- Le limiteur de threads AnyIO est mesuré à **40** et toutes les routes du projet sont `def` : un
  retour de parcours coûteux est un levier de déni de service **sur le site public**. D'où l'ordre
  imposé — toute validation locale avant le premier octet réseau (FR-025).
- **Toute** sortie HTTP de `app/` passe par le contrôle de destination (#101), garanti par le
  méta-test AST existant, qu'il faut **étendre** : `OAuth2Client` lui est aujourd'hui invisible.
- Le backend reste **intégralement synchrone**. Aucune route `async def` n'est introduite.
- httpx réémet le corps de la requête sur une redirection 307/308 : le client OAuth pose
  `follow_redirects=False`, le corps de l'échange de jeton portant le `client_secret`.

**Scale/Scope**: une dizaine de contributeurs, quelques centaines de sessions au plus. 3 tables,
5 endpoints, 2 dépendances FastAPI, 1 page et 1 composant côté interface.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants, tables, colonnes, tests, docstrings et logs en anglais ; messages de `DomainError`, libellés d'interface et documents produit en français. Les codes d'erreur du retour de parcours sont **anglais** (`state_mismatch`…), comme tous les paramètres de query du dépôt (`scope`, `federal_only`, `seasons`) ; leur traduction française vit dans l'interface, sur le modèle de `PROVIDER_LABELS`. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | `api → services/auth → repositories`. `current_user` traverse `services/auth/session.py` et **n'appelle jamais** un repository directement — c'est précisément le court-circuit que commet la PR #159, dont le router appelle `user_repository`. Les services portent la transaction, les repositories seuls construisent les requêtes : la lecture retenue est celle déjà pratiquée par `import_service` et `scrape_service`. |
| III | TDD sans réseau (non-négociable) | ✅ | Tests écrits avant l'implémentation. Réseau remplacé par `httpx.MockTransport` injecté en `transport=`, sur charges utiles GitHub capturées sous `tests/fixtures/`. Aucun test `integration` n'est ajouté : le parcours OAuth exige un navigateur et un consentement humain, il relève du `quickstart.md`. |
| IV | Contrats API et CLI stables | ✅ | Cinq endpoints **nouveaux** sous `/api/v1/auth/*`. Aucun contrat existant n'est modifié, aucun champ retiré, aucun code de retour changé. Aucune commande CLI ajoutée. |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre transverse de lecture n'est introduit. À ne pas confondre avec la posture **fail-closed** de la liste d'autorisation : le Principe V vise les filtres de lecture, où « neutre » signifie « non filtré » ; pour un contrôle d'accès, le défaut sûr est « fermé », et l'inverse serait une faille, pas une neutralité. |
| VI | Simplicité / YAGNI | ⚠️ | **Deux écarts justifiés** en Complexity Tracking : le Protocol et son registre pour un unique fournisseur en production, et l'ajout de trois dépendances runtime là où une seule suffirait à un flux GitHub écrit à la main. |

### Re-check après conception (Phase 1)

Les six verdicts sont **inchangés**. La conception a en revanche produit trois précisions qui
n'étaient pas acquises au premier passage :

- **Principe II** — la frontière `flow.py` / `session.py` / `provisioning.py` est arrêtée. La
  politique de provisionnement (certification de l'adresse, liste d'autorisation, résolution
  d'identité) est **extraite** de `flow.py` : c'est elle qui grossira avec les rôles, l'invitation
  et la restriction de domaine, et la laisser dans l'orchestration du parcours ferait de `flow.py`
  un objet-dieu à la première évolution.
- **Principe IV** — un point de contrat est figé explicitement : `GET /auth/me` rend **401** pour un
  anonyme, et non « 200 avec un corps nul ». En changer plus tard inverserait une sémantique, ce que
  le principe proscrit ; un test le verrouille dès maintenant.
- **Principe VI** — l'écart reste circonscrit aux deux lignes de Complexity Tracking. La conception
  a **retiré** trois colonnes (`last_seen_at`, `user_agent`, `revoked_at`), une dépendance directe
  (`itsdangerous`, remplacée par `joserfc` qui arrive de toute façon), une dépendance FastAPI
  (`current_user_optional`, sans consommateur) et la commande CLI de purge (le dépôt n'a aucun
  ordonnanceur). Rien n'a été ajouté au périmètre.

### Reprise après la clarification du 2026-08-02 (FR-041, SC-014)

La session de clarification a ajouté une contrainte **négative** sur le modèle : le rôle de #115
sera relatif à une **organisation**, et ne doit donc pas être porté par `users`. Trois conséquences,
toutes déjà répercutées :

- `data-model.md` — la mention « accueille sans restructuration : `role` » est **remplacée** : la
  table `users` reste au contraire *inchangée* par #115, le rôle vivant dans une association
  `(user, organisation, role)`. C'est le raisonnement déjà tenu pour le futur mot de passe, placé
  sur `identities` plutôt qu'en colonne sur `users`.
- `contracts/auth-api.md` — la réserve porte désormais sur la **forme** du futur champ : un scalaire
  `"role": "admin"` inverserait la sémantique le jour où un utilisateur a des rôles différents dans
  deux organisations, ce que le Principe IV proscrit de changer après coup.
- **Aucun changement de périmètre ni de code** : FR-041 n'ajoute ni table, ni colonne, ni endpoint,
  ni dépendance. Elle interdit une forme future, elle ne construit rien — le Principe VI est donc
  servi, pas mis à l'épreuve. Aucune tâche de `tasks.md` n'est invalidée.

## Project Structure

### Documentation (this feature)

```text
specs/20260801-145428-auth-socle-sso/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── auth-api.md      # Phase 1 output
├── checklists/
│   └── requirements.md  # /speckit-specify output
└── tasks.md             # /speckit-tasks output — NOT created here
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── core/
│   │   ├── config.py             # MODIFIÉ : 8 réglages auth_*
│   │   ├── exceptions.py         # MODIFIÉ : AuthUnavailableError (503, message français)
│   │   └── http.py               # MODIFIÉ : guarded_transport() exposé publiquement
│   ├── models/
│   │   ├── __init__.py           # MODIFIÉ : enregistre les 3 tables sur Base.metadata
│   │   ├── user.py               # NOUVEAU
│   │   ├── identity.py           # NOUVEAU
│   │   └── user_session.py       # NOUVEAU
│   ├── repositories/
│   │   ├── user_repository.py    # NOUVEAU
│   │   ├── identity_repository.py# NOUVEAU
│   │   └── session_repository.py # NOUVEAU
│   ├── services/auth/
│   │   ├── idp/
│   │   │   ├── base.py           # NOUVEAU : Protocol + AuthorizationRequest + ExternalIdentity
│   │   │   ├── registry.py       # NOUVEAU : registre, register(), enabled_methods()
│   │   │   └── github.py         # NOUVEAU : GithubIdentityProvider (Authlib + transport gardé)
│   │   ├── state.py              # NOUVEAU : signature/vérification du jeton d'état (joserfc)
│   │   ├── session.py            # NOUVEAU : open / resolve / revoke, hachage du jeton
│   │   ├── provisioning.py       # NOUVEAU : resolve_user (email vérifié, allowlist, résolution)
│   │   └── flow.py               # NOUVEAU : start_login / complete_login
│   ├── schemas/auth.py           # NOUVEAU : DTO
│   └── api/
│       ├── deps.py               # MODIFIÉ : current_user
│       └── v1/
│           ├── auth.py           # NOUVEAU : router mince
│           └── router.py         # MODIFIÉ : montage
├── alembic/versions/             # NOUVEAU : une révision, 3 tables
├── tests/
│   ├── test_core_http.py         # MODIFIÉ : détecteur AST étendu à OAuth2Client / HTTPTransport
│   ├── test_config.py            # MODIFIÉ : parsing CSV d'AUTH_ALLOWED_EMAILS
│   └── test_auth/                # NOUVEAU : conftest, fixtures, suites
├── pyproject.toml                # MODIFIÉ : authlib
└── uv.lock                       # MODIFIÉ : régénéré dans le même commit

frontend/
├── app/
│   ├── login/page.tsx            # NOUVEAU
│   └── admin/layout.tsx          # NOUVEAU : garde d'accès (validation réelle)
├── components/
│   ├── auth/UserMenu.tsx         # NOUVEAU
│   └── layout/TcnTopbar.tsx      # MODIFIÉ : desktop ET tiroir mobile
├── lib/
│   ├── api/client.ts             # MODIFIÉ : ApiError porteur du statut
│   ├── api/server.ts             # MODIFIÉ : ajout de serverFetchAuthed, serverFetch intact
│   ├── queries/auth.ts           # NOUVEAU : useSession
│   ├── constants.ts              # MODIFIÉ : libellés français des codes d'erreur
│   └── types.ts                  # MODIFIÉ : SessionUser, AuthMethod
└── (tests colocalisés *.test.tsx)

AGENTS.md                         # MODIFIÉ : section « Authentification » (AC7 de #114)
render.yaml, backend/.env.example, backend/README.md, docs/ci-cd.md, .worktreeinclude  # MODIFIÉS
```

**Structure Decision**: application web, structure existante du dépôt conservée. Le seul dossier
nouveau du backend est `app/services/auth/`, avec son sous-dossier `idp/`. Ce nom est délibéré :
« provider » désigne déjà un **chronométreur** dans tout le dépôt (`PendingProvider`,
`registry.provider_names()`, `--provider`, `PROVIDER_LABELS`, `GET /scrape/detect`). Employer le
même mot pour un fournisseur d'identité créerait un second sens et un second `registry.py`
homonyme. D'où `idp/` côté code et `GET /api/v1/auth/methods` côté contrat.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| **Protocol `IdentityProvider` + registre pour un seul fournisseur en production** | Décision explicite de l'utilisateur (évolutivité demandée : autres SSO, puis mot de passe), et préparation de #115. Le contrat retenu n'énumère **pas** les mécanismes : `authorize()` rend un `round_trip` opaque que le flux signe sans le lire, ce qui permet à OIDC d'y ranger son `nonce` sans toucher au contrat, au flux, ni au fournisseur GitHub. | L'alternative — un module `github.py` appelé directement par `flow.py`, sans Protocol ni registre, le Protocol étant extrait à l'arrivée du **second** fournisseur réel — est celle que recommande le Rationale du Principe VI : le registre des scrapers a été extrait **après** que quatorze fournisseurs eurent révélé les coutures, pas avant le premier. Elle est rejetée sur arbitrage utilisateur, et le coût du report était pourtant nul, les tables `users`/`identities` portant déjà l'essentiel de l'évolutivité. **L'écart assumé est celui-ci** : l'abstraction est posée avant son second cas, et sa seule autre implémentation est une doublure de test — donc elle ne prouve rien par elle-même. Atténuation retenue : livrer d'emblée la signature qui survit à OIDC, plutôt qu'une signature calquée sur GitHub qu'il faudrait casser au second fournisseur. |
| **Trois dépendances runtime (`authlib`, `cryptography`, `joserfc`) au lieu d'une** | La contrainte n'est pas fonctionnelle mais **structurelle** : `AGENTS.md` impose que toute sortie HTTP traverse le contrôle de destination de #101. `OAuth2Client` hérite de `httpx.Client`, donc `transport=` y descend nativement — c'est la seule des trois bibliothèques sondées qui satisfasse cette règle **à la lettre et dans l'esprit**, sans fork ni recopie. `joserfc`, qui vient avec, remplace `itsdangerous` pour le jeton d'état : la dépendance directe nette est **une seule**. | Écrire le flux à la main (~40 lignes, comme la PR #159) traverserait le garde tout aussi bien et n'ajouterait rien : c'est l'alternative sérieuse. Elle est rejetée sur arbitrage utilisateur (« utiliser les paquets existants et bien utilisés de l'écosystème »), et parce qu'elle laisserait PKCE, l'échange de jeton et la validation d'`id_token` — indispensable au premier fournisseur OIDC — à écrire et à maintenir soi-même. `fastapi-sso` et `httpx-oauth` sont rejetés sur faits mesurés, cf. le sondage. |
