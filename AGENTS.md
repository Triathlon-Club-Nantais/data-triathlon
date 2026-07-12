# AGENTS.md — data-triathlon

App web centralisant les résultats de compétition des membres d'un club de
triathlon (TCN). On colle une URL de chronométrage → le backend scrape, stocke,
et importe en arrière-plan tous les participants de l'épreuve.

Détails install/déploiement : voir `README.md`. Ce fichier cible les agents IA.

## Pile applicative

Une seule génération, en deux briques :

- **Backend** (`backend/`) : FastAPI, archi en couches, modèle normalisé, Alembic.
- **Frontend** (`frontend/`) : Next.js 16 (App Router), TypeScript, Tailwind, shadcn/ui.

Specs de refonte (historiques) : `docs/superpowers/specs/`.

## Stack
- **Backend** (`backend/`) : Python 3.11+, FastAPI 0.115, SQLAlchemy 2.0
  (sync), Pydantic v2 + pydantic-settings, **Alembic** (migrations), PostgreSQL
  (Supabase) / SQLite en dev. Scraping httpx + BeautifulSoup/lxml, fallback
  Playwright. Tests pytest, ruff. API versionnée sous `/api/v1`.
- **Frontend** (`frontend/`) : Next.js 16 (App Router) + TypeScript + Tailwind + shadcn/ui.
- **Déploiement** : backend → Render (`render.yaml`), front → Vercel, DB → Supabase.

## Commandes

```bash
# Backend (depuis backend/, venv activé)
uvicorn app.main:app --reload --port 8001  # API + /docs (endpoints sous /api/v1)
alembic upgrade head                        # applique les migrations
alembic revision --autogenerate -m "..."    # nouvelle migration après modif d'un modèle
python scripts/reset_db.py                  # reset base dev SQLite (vide + migre + seed démo)
python scripts/reset_db.py --no-seed --yes  # schéma vierge seul (refuse si DB non-SQLite)
pytest -m "not integration"                 # tests unitaires (sans réseau) — défaut CI
pytest -m integration                       # tests réseau réel (scrapers)
ruff check .                                 # lint

# CLI de batch (depuis backend/, venv activé)
python -m app.cli import-sheet --dry-run     # import de masse (Sheet) : ce qui serait importé
python -m app.cli import-sheet --limit 5     # import réel — progression en direct
python -m app.cli rescrape-db --limit 10     # re-scrape la DB (force=True) ; --plain, --no-progress
python -m app.cli rescrape-db --json | jq    # bilan machine-lisible (stdout = JSON seul)

# Frontend (depuis frontend/)
npm run dev        # Next.js sur :3000, rewrites /api → :8001
npm run build      # build prod (strict TS + RSC)
npm test           # vitest run
npm run lint       # ESLint
```

Variable requise : `backend/.env` avec `DATABASE_URL` (voir `.env.example`). Le
schéma est géré par **Alembic** (`alembic upgrade head`).

## Architecture backend (`backend/`)

Archi en couches, le flux ne traverse qu'une direction
(`api → services → repositories → DB`) :

- `app/main.py` — usine `create_app()` : CORS, handlers d'erreurs, montage routers.
- `app/core/` — `config.py` (pydantic-settings), `logging.py`, `database.py`,
  `exceptions.py`, `time.py`, `club.py`.
- `app/models/` — SQLAlchemy **normalisé** : `Athlete`, `Course`, `Participation`,
  `PendingProvider` (voir « Modèle normalisé » plus bas).
- `app/schemas/` — DTO Pydantic v2 (entrée/sortie).
- `app/repositories/` — `*_repository.py` : **seule couche qui touche la Session**.
- `app/services/` — logique métier : `mapping`, `cache` (TTL), `scrape_service`,
  `import_service`, `stats_service`, `geocode_service`, plus les batches CLI :
  `sheet_source` (source Google Sheet), `batch` (la boucle : elle consomme
  `import_service.iter_import_event()` — le générateur de phases du SSE — et
  relaie la progression), `bulk_import_service`, `rescrape_service`, `progress`
  (Protocol `ProgressReporter` + `NullReporter`, le défaut muet).
- `app/cli/` — Typer, **couche mince** (zéro logique métier) : `commands/` (une
  commande par fichier), `progress.py` (reporters Rich/Plain, `select_reporter`),
  `reports.py` (rendu des bilans + émission).
- `app/api/` — `deps.py` + `v1/` (routers fins : validation + délégation au service),
  agrégés dans `v1/router.py`, montés sous `/api/v1`. Une future API v2 vivra dans `v1/`→`v2/`.
- `app/scrapers/` — `registry.py` (registre **Protocol**, fin des `if-else`) +
  un module par provider. `base.py` = `ScrapedResult`,
  `utils.py` = helpers de normalisation.
- `alembic/` — migrations (révision initiale = schéma complet).
- `tests/` — `test_repositories/`, `test_services/`, `test_api/`, `test_cli/`,
  `test_klikego.py`, `test_timepulse.py` (≈510 tests).

### Modèle normalisé

- **Athlete** — `UNIQUE(nom, prenom, birth_date)`.
- **Course** — `UNIQUE(name, event_date, event_type)` ; `source_url` = clé de cache TTL.
- **Participation** — `UNIQUE(course_id, bib_number)` → plus de doublons à l'import.
- **splits** en **JSON** (remplace les colonnes figées swim/t1/bike/t2/run) →
  couvre tous les sports (duathlon course1/course2, swimrun…). Temps = strings.
  Les scrapers rangent les segments dans 5 slots positionnels triathlon
  (`swim/t1/bike/t2/run` de `ScrapedResult`) ; `services/mapping.build_splits`
  ré-étiquette ces slots selon `event_type` via le gabarit
  `_SPLIT_KEYS_BY_SPORT` (ex. duathlon → `course1`/`course2`) et omet les slots
  non pertinents. *Limite* : plafonné à 5 segments — un swimrun multi-legs reste
  collapsé. Évolution future si besoin : porter une **liste ordonnée de segments
  étiquetés** dès `ScrapedResult` (touche les 7 scrapers).

### Cache TTL

`services/cache.py` : `is_fresh(course)` → 10 min si course en cours (une
participation sans `total_time`), sinon 30 j. `scrape_service` court-circuite le
re-scraping si frais. Réglable via `CACHE_TTL_IN_PROGRESS_SECONDS` /
`CACHE_TTL_FINISHED_SECONDS`.

### Sorties de la CLI (stdout parsable)

Règle structurante, pas un détail : **stdout reste parsable**. La progression sort
donc toujours sur **stderr** (Rich en terminal, lignes simples sinon — cron, CI,
redirection), et avec `--json`, le rapport texte y bascule aussi : stdout ne
contient alors **que** la ligne JSON, d'où `… --json | jq` sans découpage. Sans
`--json`, le rapport texte sort sur stdout comme attendu.

Un batch interrompu (Ctrl-C) émet son **bilan partiel** — texte et, le cas
échéant, JSON — **avant** de sortir en code **130** : le travail déjà persisté
n'est jamais perdu de vue (chaque épreuve est commitée séparément). `--no-progress`
coupe la progression (le rapport final, lui, est toujours émis) ; `--plain` force
les lignes simples même en terminal.

### Conventions scrapers

- Tout nouveau fournisseur : créer `scrapers/<nom>.py`, exposer `scrape()` (et
  `scrape_event_all()` si l'import de masse est possible), puis l'enregistrer
  dans `scrapers/registry.py` (registre Protocol). Provider inconnu → `playwright`.
- **Breizh Chrono réutilise la logique Klikego** (`klikego._parse_detail`,
  `_detect_event_type`) — ne pas dupliquer, factoriser dans `klikego.py`.
- Identification club lors d'un import épreuve : filtre `city=nantais` de l'API
  (plus fiable que le nom de club, qui varie : « TCN », « TRIATHLON CLUB NANTAIS »…).
- Les temps restent des **strings** (`"01:23:45"`), normalisés via `utils.py`.
  Splits adaptés au sport : dans `splits` (JSON) + `raw_data` (JSON).

## Architecture frontend (`frontend/`)

Next.js 16 (App Router), TypeScript strict, Tailwind CSS, shadcn/ui, consommant
`/api/v1` du backend. Tests Vitest + RTL verts. Build prod OK.

- `app/` — App Router : `dashboard`, `resultats`, `athletes/[id]`, `courses/[id]`,
  `club`, `carte`, `ajouter`, `admin`.
- `components/` — `scrape/` (ScrapeForm, ProviderDetector, ImportProgress),
  `results/` (ResultCard, ResultsList), `club/` (ClubView, AthleteDialog),
  `map/` (MapView), `dashboard/` (StatsCards, RecentCourses), `ui/` (shadcn).
- `lib/api/` — `client.ts` (appels `/api/v1`), `sse.ts` (streaming import SSE).
- `lib/types.ts` — types TypeScript partagés.
- Déploiement : Vercel, variables `BACKEND_URL` + `API_URL`.

## Conventions générales

- **Langue** : UI, commentaires et messages en **français** (avec accents).
- Commits : Conventional Commits (`feat:`, `fix:`…), déjà en place dans l'historique.
- Schéma DB : migrations **Alembic** (`alembic revision --autogenerate`
  après modif d'un modèle, puis `alembic upgrade head`).
- Tests unitaires **sans réseau** ; le réseau réel est isolé derrière le marker
  `integration` (`pytest.ini`).

## Fournisseurs supportés

Klikego, Breizh Chrono, TimePulse, Wiclax/G-Live (individuel + épreuve complète).
Types : Triathlon XS/S/M/L/XL, Duathlon XS/S/M/L, SwimRun S/M/L, Aquathlon,
Aquarun, Bike & Run.
