# backend — Triathlon Club Results

Backend en **architecture en couches** avec un **modèle de données
normalisé** (Athlete / Course / Participation). Construit avec FastAPI +
SQLAlchemy 2.0, migrations Alembic, configuration typée et tests par couche.

> Design d'origine :
> `../docs/superpowers/specs/2026-06-07-refactoring-backend-architecture-design.md`.

## Architecture

```
app/
  main.py          # usine create_app() : CORS, handlers d'erreurs, montage des routers
  core/            # config (pydantic-settings), logging, database, exceptions, time, club
  models/          # SQLAlchemy : Athlete, Course, Participation, PendingProvider
  schemas/         # DTO Pydantic (entrée/sortie)
  repositories/    # accès données — seule couche qui touche la Session
  services/        # logique métier : mapping, cache TTL, scrape, import, stats, geocode
  api/
    deps.py        # dépendances partagées (version-agnostiques)
    v1/            # routers FastAPI fins de la v1 — montés sous /api/v1
      router.py    # agrège tous les routers v1
  scrapers/        # registre Protocol + un module par provider
alembic/           # migrations (révision initiale = schéma complet)
tests/             # test_repositories / test_services / test_api / test_scrapers
```

Flux d'un import épreuve :
`api/scrape` → `services/import_service` → (cache TTL) → `scrapers/registry`
→ `services/mapping` (ScrapedResult → entités) → `repositories` → DB.

## Prérequis

- [uv](https://docs.astral.sh/uv/) — gère les dépendances et l'interpréteur (Python 3.13)
- `backend/.env` avec au minimum `DATABASE_URL` (voir `.env.example`)

## Installation

```bash
cd backend
uv sync   # crée .venv (Python 3.13) + installe les dépendances depuis uv.lock
```

> `uv sync --frozen --no-dev` écarte le groupe `dev` (pytest, respx, ruff) — c'est ce que font Render et l'image Docker.

## Base de données (Alembic)

Les tables ne sont **plus** créées au démarrage : tout passe par les migrations.

```bash
uv run alembic upgrade head                       # applique les migrations
uv run alembic revision --autogenerate -m "..."   # nouvelle migration après modif d'un modèle
```

### Réinitialiser la base (dev — SQLite uniquement)

`scripts/reset_db.py` vide la base, réapplique les migrations, puis ré-importe
un jeu de données démo réel (toutes disciplines). **Garde-fou** : le script
refuse de s'exécuter si `DATABASE_URL` n'est pas SQLite (jamais sur Supabase).

```bash
uv run python scripts/reset_db.py            # vide + migre + seed démo
uv run python scripts/reset_db.py --no-seed  # schéma vierge seulement (rapide, hors réseau)
uv run python scripts/reset_db.py --yes      # sans confirmation interactive
uv run python scripts/seed_demo.py           # (re)seed seul, sans toucher au schéma
```

## Lancer l'API

```bash
uv run python scripts/dev_server.py  # API + /docs, premier port libre à partir de 8001
```

Le port est choisi au démarrage (8001 s'il est libre, sinon le suivant) et publié
dans `.dev-backend.json` à la racine du worktree : c'est ainsi que `npm run dev`
branche le frontend sur **ce** backend plutôt que sur celui d'un autre worktree.
`DEV_BACKEND_PORT=8005` force un port ; `uvicorn app.main:app --reload --port 8001`
reste utilisable pour un lancement brut, sans publication.

**API versionnée** : tous les endpoints sont sous `/api/v1/*` (une future v2 vivra
dans `app/api/v2/`). `GET /api/v1/health` vérifie l'API **et** la connexion DB.

## Tests & qualité

```bash
uv run pytest -m "not integration"   # tests rapides (sans réseau) — défaut CI
uv run pytest -m integration         # tests réseau réel (scrapers)
uv run ruff check .                  # lint
```

## Configuration (variables d'environnement)

| Variable | Défaut | Rôle |
|----------|--------|------|
| `DATABASE_URL` | `sqlite:///./triathlon.db` | Connexion DB (Supabase en prod) |
| `CORS_ORIGINS` | localhost:3000,5173 | Origines autorisées (CSV, **restreint**) |
| `LOG_LEVEL` | `INFO` | Niveau de log |
| `LOG_JSON` | `false` | Logs JSON (ingestion Render/Datadog) |
| `CACHE_TTL_IN_PROGRESS_SECONDS` | `600` | TTL cache course en cours (10 min) |
| `CACHE_TTL_FINISHED_SECONDS` | `2592000` | TTL cache course terminée (30 j) |
| `AUTH_SESSION_SECRET_KEY` | *(vide)* | Signe le jeton d'état du parcours. **≥ 32 caractères** ou le démarrage échoue ; vide = authentification non configurée |
| `AUTH_GITHUB_CLIENT_ID` | *(vide)* | Application OAuth GitHub |
| `AUTH_GITHUB_CLIENT_SECRET` | *(vide)* | Application OAuth GitHub |
| `AUTH_ALLOWED_EMAILS` | *(vide)* | Adresses autorisées, en CSV. **Vide interdit toute connexion** — jamais « tout le monde » |
| `AUTH_REDIRECT_BASE_URL` | *(vide)* | Origine de l'**interface** (jamais celle de l'API) : destination de retour, base de `/login?error=…` et du `redirect_uri` envoyé au fournisseur. **Sans défaut** — un défaut localhost faisait passer pour configuré un déploiement qui l'oubliait, et l'échec tombait alors chez GitHub |
| `AUTH_COOKIE_SECURE` | `true` | `false` en développement sans TLS — retire alors le préfixe `__Host-` du nom des cookies |
| `AUTH_SESSION_TTL_DAYS` | `7` | Durée de session, sans prolongation glissante |
| `AUTH_STATE_TTL_SECONDS` | `600` | Durée de vie du jeton d'état (10 min) |

Une installation **sans** ces variables démarre normalement : le site public est
intact et `GET /api/v1/auth/methods` rend `[]`. Mise en route locale complète
(application OAuth comprise) : `specs/20260801-145428-auth-socle-sso/quickstart.md`.

## Points clés du modèle

- **Course** = (nom, date, type) unique ; `source_url` sert de clé de cache TTL.
- **Participation** unique par (course, dossard) → plus de doublons à l'import.
- **splits** (JSON) remplace les colonnes figées swim/t1/bike/t2/run → couvre tous
  les sports (duathlon course1/course2, swimrun…). Les temps restent des strings.

## Suites (pistes d'amélioration)

- Factorisation des helpers internes des scrapers (`_detect_event_type`, mapping
  des splits) — différée car signatures divergentes et couverture de tests inégale.
