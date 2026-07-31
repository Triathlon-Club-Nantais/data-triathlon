# Implementation Plan: Auth backend GitHub OAuth pour le back-office admin

**Branch**: `worktree-114-auth-backend` | **Date**: 2026-07-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/006-auth-backend-github/spec.md`

## Summary

Livrer le socle d'authentification du panneau admin (issue #114 de l'épique
#81), backend uniquement. Un unique provider : GitHub OAuth. Une seule table
nouvelle : `users`. Une session portée par un cookie `tcn_session` signé et
horodaté par `itsdangerous.URLSafeTimedSerializer` (déjà dans les transitives
FastAPI/Starlette — pas de nouvelle dépendance). Le site public reste 100 %
accessible sans connexion : ce ticket n'ajoute **aucune** protection globale et
n'aligne aucune route existante sur l'authentification.

Approche technique retenue (détail dans [research.md](./research.md)) :

- **Modèle** : `User(id, github_id, github_login, email, is_active, created_at,
  athlete_id nullable FK)`. `github_id` en `String` pour éviter le débordement
  int 32 bits. **Pas** de champ rôle (renvoyé à #115).
- **Session** : cookie `tcn_session` (`HttpOnly; SameSite=Lax; Secure` en
  prod), payload `{"uid": <int>, "v": 1}`, 7 jours par défaut. Rotation de
  `SESSION_SECRET_KEY` = kill-switch global.
- **Flux OAuth** : `GET /auth/github/authorize` (state en cookie éphémère signé)
  → GitHub → `GET /auth/github/callback` (vérification state + échange code +
  lecture `/user` puis `/user/emails` si besoin, oubli immédiat du token) →
  `Set-Cookie` + `302` vers `FRONTEND_POST_LOGIN_URL`.
- **Dépendances FastAPI** : `current_user` (obligatoire, 401 sinon),
  `current_user_optional` (accepte anonyme).
- **Zéro dépendance nouvelle en production** (`itsdangerous` déjà transitivement
  présent). `httpx` déjà utilisé pour les scrapers.

## Technical Context

**Language/Version** : Python 3.13.

**Primary Dependencies** :
- Production : FastAPI (déjà là), SQLAlchemy 2.0 sync (déjà là), Pydantic v2 +
  pydantic-settings (déjà là), Alembic (déjà là), httpx (déjà là),
  **itsdangerous** (transitivement présent via Starlette — importé
  explicitement, aucun ajout dans `pyproject.toml`).
- Dev (tests) : pytest, ruff — inchangés.

**Storage** : PostgreSQL en prod (Supabase), SQLite en dev/tests. Une seule
nouvelle table (`users`).

**Testing** : pytest, monkeypatch de `httpx.Client` pour les appels GitHub,
conformément à la convention actuelle (`test_klikego.py`). Réseau réel isolé
derrière `-m integration` (aucun test intégration livré sur ce ticket : le flux
OAuth réel n'est pas rejouable automatiquement, et l'issue ne le demande pas).

**Target Platform** : backend FastAPI déployé sur Render (Linux, Python 3.13,
Docker). Contrat cookie compatible frontend Next.js 16 (Vercel) via les rewrites
`/api/*` déjà en place.

**Project Type** : web application (backend + frontend, cf. `AGENTS.md`). Cette
sous-issue ne touche que le backend ; l'UI est livrée par #116.

**Performance Goals** : le flux OAuth complet doit se dérouler en < 2 s côté
utilisateur (réseau GitHub + un aller-retour DB) — hors périmètre à mesurer
formellement, standard OAuth. Aucun endpoint chaud sur le chemin critique
utilisateur.

**Constraints** :
- Aucune régression de latence ou de comportement sur les endpoints publics
  existants (contrainte SC-001).
- Aucun secret commité en clair (SC-003).
- La suite unitaire complète doit rester verte (SC-005).

**Scale/Scope** : le back-office cible < 10 utilisateurs à moyen terme, tous
contributeurs du club porteurs d'un compte GitHub. Aucune inscription publique.

## Constitution Check

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.0.0).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Erreurs `DomainError` en français (« Authentification non configurée. », « État CSRF invalide. », « Non authentifié. », « Autorisation GitHub refusée. », « Aucun email GitHub vérifié disponible. ») ; noms d'endpoints, colonnes DB, tests, docstrings techniques et messages `logger.*` en anglais. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | `app/api/v1/auth.py` (router mince, validation Pydantic + délégation) → `app/services/auth_service.py` (flux OAuth, encodage cookie, orchestration) → `app/repositories/user_repository.py` (**seule** couche qui touche la `Session`). Zéro requête SQL en dehors du repository. `is_tcn` non touché. |
| III | TDD sans réseau (non-négociable) | ✅ | Tests écrits **avant** l'implémentation (ordonnancement imposé dans `tasks.md`). Monkeypatch de `httpx.Client` pour tous les appels GitHub (`token`, `/user`, `/user/emails`), fixtures JSON figées sous `tests/test_auth/fixtures/`. Aucun test réseau réel — pas de marker `integration` sur ce ticket. |
| IV | Contrats API et CLI stables | ✅ | Tous les endpoints sous `/api/v1/auth/*` (respect du versionnement). Aucune modification de la sémantique ou du code de retour d'un endpoint existant. Contrat cookie documenté dans `contracts/auth-api.md` (nom, attributs, format) — c'est le contrat sur lequel #116 s'appuiera. |
| V | Neutralité par défaut des paramètres transverses | ✅ | Aucun nouveau paramètre transverse (pas de `scope`, pas de `federal_only`). La dépendance `current_user_optional` matérialise la neutralité côté FastAPI : une route existante qui l'adopterait ne changerait pas de comportement (elle *accepte* la session, elle ne l'*exige* pas). |
| VI | Simplicité / YAGNI | ✅ | Une table (`users`), quatre endpoints (`authorize`, `callback`, `logout`, `me`), deux dépendances (`current_user` / `current_user_optional`). Pas de table `sessions` (révocation immédiate non identifiée comme besoin). Pas de refresh token (session de 7 jours suffit). Pas d'abstraction `provider` prématurée (`github_id` reste `github_id` ; #114+ créera une colonne dédiée si un autre provider arrive). Pas de nouvelle dépendance en production. |

Aucun principe en ⚠️. Section « Complexity Tracking » vide.

## Project Structure

### Documentation (this feature)

```text
specs/006-auth-backend-github/
├── plan.md              # This file
├── research.md          # Phase 0 — décisions techniques et alternatives
├── data-model.md        # Phase 1 — entité User + migration
├── quickstart.md        # Phase 1 — comment ouvrir une session locale
├── contracts/
│   └── auth-api.md      # Phase 1 — contrat public des endpoints /api/v1/auth/*
├── checklists/
│   └── requirements.md  # Checklist qualité du spec (validée)
└── tasks.md             # Phase 2 output (/speckit-tasks — pas encore généré)
```

### Source Code (repository root)

Ce ticket ajoute des fichiers, ne modifie aucun contrat existant.

```text
backend/
├── app/
│   ├── api/
│   │   ├── deps.py                       # ← modifié : + current_user, + current_user_optional
│   │   └── v1/
│   │       ├── auth.py                   # ← nouveau : router mince (4 endpoints)
│   │       └── router.py                 # ← modifié : monte le router auth
│   ├── core/
│   │   └── config.py                     # ← modifié : + 6 champs (github_*, session_*, frontend_post_login_url)
│   ├── models/
│   │   ├── __init__.py                   # ← modifié : export User
│   │   └── user.py                       # ← nouveau : modèle User
│   ├── repositories/
│   │   └── user_repository.py            # ← nouveau : get_by_github_id, upsert_from_github, get
│   ├── schemas/
│   │   └── user.py                       # ← nouveau : UserRead (pour /me)
│   └── services/
│       └── auth_service.py               # ← nouveau : oauth flow, cookie sign/verify
├── alembic/
│   └── versions/
│       └── <hash>_add_users_table.py     # ← nouvelle révision
├── tests/
│   └── test_auth/                        # ← nouveau
│       ├── __init__.py
│       ├── conftest.py                   # ← fixtures propres à l'auth (settings, http mock)
│       ├── fixtures/
│       │   ├── github_user.json
│       │   └── github_user_emails.json
│       ├── test_session_cookie.py
│       ├── test_github_oauth_flow.py
│       ├── test_deps_current_user.py
│       └── test_public_routes_still_open.py
└── .env.example                          # ← modifié : + variables auth documentées

AGENTS.md                                 # ← modifié : + section « Authentification » (post-merge)
```

**Structure Decision** : projet « web application » (backend + frontend selon
`AGENTS.md`). Cette sous-issue ne touche **que** `backend/`. Le frontend
(`frontend/`) n'est pas modifié — l'UI de connexion est le périmètre de #116,
qui consommera le contrat de cookie défini ici.

## Complexity Tracking

Aucune violation à justifier — voir Constitution Check ci-dessus.
