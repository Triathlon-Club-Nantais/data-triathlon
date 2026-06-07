# backend-v2 — Triathlon Club Results

Refonte du backend en **architecture en couches** avec un **modèle de données
normalisé** (Athlete / Course / Participation). Construit avec FastAPI +
SQLAlchemy 2.0, migrations Alembic, configuration typée et tests par couche.

> Ce dossier remplace progressivement `../backend/`. Voir le design dans
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
  scrapers/        # registre Protocol + un module par provider (porté de ../backend)
alembic/           # migrations (révision initiale = schéma complet)
tests/             # test_repositories / test_services / test_api / test_scrapers
```

Flux d'un import épreuve :
`api/scrape` → `services/import_service` → (cache TTL) → `scrapers/registry`
→ `services/mapping` (ScrapedResult → entités) → `repositories` → DB.

## Prérequis

- Python 3.11+ (testé en 3.13)
- `backend-v2/.env` avec au minimum `DATABASE_URL` (voir `.env.example`)

## Installation

```bash
cd backend-v2
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt   # requirements.txt seul en prod
```

## Base de données (Alembic)

Les tables ne sont **plus** créées au démarrage : tout passe par les migrations.

```bash
alembic upgrade head                       # applique les migrations
alembic revision --autogenerate -m "..."   # nouvelle migration après modif d'un modèle
```

## Lancer l'API

```bash
uvicorn app.main:app --reload --port 8001  # API + /docs
```

**API versionnée** : tous les endpoints sont sous `/api/v1/*` (une future v2 vivra
dans `app/api/v2/`). `GET /api/v1/health` vérifie l'API **et** la connexion DB.

## Tests & qualité

```bash
pytest -m "not integration"   # tests rapides (sans réseau) — défaut CI
pytest -m integration         # tests réseau réel (scrapers)
ruff check .                  # lint
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

## Points clés du modèle

- **Course** = (nom, date, type) unique ; `source_url` sert de clé de cache TTL.
- **Participation** unique par (course, dossard) → plus de doublons à l'import.
- **splits** (JSON) remplace les colonnes figées swim/t1/bike/t2/run → couvre tous
  les sports (duathlon course1/course2, swimrun…). Les temps restent des strings.

## Suites (hors périmètre de cette refonte)

- Adaptation du frontend React aux nouveaux endpoints.
- Factorisation des helpers internes des scrapers (`_detect_event_type`, mapping
  des splits) — différée car signatures divergentes et couverture de tests inégale.
- Isolation de Playwright dans une image Docker dédiée.
