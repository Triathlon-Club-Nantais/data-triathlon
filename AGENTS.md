# AGENTS.md — data-triathlon

App web centralisant les résultats de compétition des membres d'un club de
triathlon (TCN). On colle une URL de chronométrage → le backend scrape, stocke,
et importe en arrière-plan tous les participants de l'épreuve.

Détails install/déploiement : voir `README.md`. Ce fichier cible les agents IA.

## État du projet — migration en cours

Le dépôt contient **deux générations** de chaque brique. Bien repérer la cible :

| Brique | En production | Cible (refonte) | Statut |
|--------|---------------|-----------------|--------|
| Backend | `backend/` (déployé Render) | `backend-v2/` | v2 codée (130 tests verts), **pas encore déployée** |
| Frontend | `frontend/` (déployé Vercel) | `frontend-v2/` | **spec seulement**, pas encore codée |

- **Nouveau développement backend → `backend-v2/`** (archi en couches, modèle
  normalisé). `backend/` reste **déprécié** mais en prod jusqu'à la bascule :
  n'y faire que les correctifs urgents.
- `frontend-v2/` n'existe pas encore : seules la spec et le plan sont écrits
  (`docs/superpowers/specs/2026-06-07-frontend-v2-nextjs-design.md`,
  `docs/superpowers/plans/2026-06-07-frontend-v2-nextjs.md`).
- Specs de refonte : `docs/superpowers/specs/`.

## Stack
- **Backend v2** (`backend-v2/`) : Python 3.11+, FastAPI 0.115, SQLAlchemy 2.0
  (sync), Pydantic v2 + pydantic-settings, **Alembic** (migrations), PostgreSQL
  (Supabase) / SQLite en dev. Scraping httpx + BeautifulSoup/lxml, fallback
  Playwright. Tests pytest, ruff. API versionnée sous `/api/v1`.
- **Backend v1** (`backend/`, déprécié) : même stack, sans couches ni Alembic
  (tables via `create_all()` au démarrage).
- **Frontend** (`frontend/`) : React 18 + Vite 6, JSX, pas de TypeScript, pas
  de lib UI. **frontend-v2** (planifié) : Next.js + TypeScript + Tailwind + shadcn/ui.
- **Déploiement** : backend → Render (`render.yaml`), front → Vercel, DB → Supabase.

## Commandes

```bash
# Backend v2 (depuis backend-v2/, venv activé) — CIBLE
uvicorn app.main:app --reload --port 8001  # API + /docs (endpoints sous /api/v1)
alembic upgrade head                        # applique les migrations (plus de create_all)
alembic revision --autogenerate -m "..."    # nouvelle migration après modif d'un modèle
pytest -m "not integration"                 # tests unitaires (sans réseau) — défaut CI
pytest -m integration                       # tests réseau réel (scrapers)
ruff check .                                 # lint

# Backend v1 (depuis backend/, déprécié)
uvicorn main:app --reload --port 8001       # tables créées au démarrage (pas d'Alembic)
pytest -m "not integration"

# Frontend (depuis frontend/)
npm run dev        # Vite sur :3000, proxy /api → :8001
npm run build      # build prod
```

Variable requise : `<backend>/.env` avec `DATABASE_URL` (voir `.env.example`).
En v2, le schéma est géré par **Alembic** (`alembic upgrade head`) ; en v1, les
tables sont créées automatiquement au démarrage.

## Architecture backend v2 (`backend-v2/`) — cible

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
  `import_service`, `stats_service`, `geocode_service`.
- `app/api/` — `deps.py` + `v1/` (routers fins : validation + délégation au service),
  agrégés dans `v1/router.py`, montés sous `/api/v1`. Une future v2 vivra dans `v1/`→`v2/`.
- `app/scrapers/` — `registry.py` (registre **Protocol**, fin des `if-else`) +
  un module par provider (porté de `backend/`). `base.py` = `ScrapedResult`,
  `utils.py` = helpers de normalisation.
- `alembic/` — migrations (révision initiale = schéma complet).
- `tests/` — `test_repositories/`, `test_services/`, `test_api/`, `test_klikego.py`,
  `test_timepulse.py` (130 tests).

### Modèle normalisé (v2)

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

### Cache TTL (v2)

`services/cache.py` : `is_fresh(course)` → 10 min si course en cours (une
participation sans `total_time`), sinon 30 j. `scrape_service` court-circuite le
re-scraping si frais. Réglable via `CACHE_TTL_IN_PROGRESS_SECONDS` /
`CACHE_TTL_FINISHED_SECONDS`.

## Architecture backend v1 (`backend/`) — déprécié

- `main.py` — app FastAPI, CORS, montage des routers.
- `database.py` — engine + session SQLAlchemy. `models.py` — `Result`, `PendingProvider`.
- `routers/` — `scrape.py` (`POST /api/scrape`, `/api/scrape/event`),
  `results.py` (CRUD `/api/results`), `admin.py` (providers non supportés signalés).
- `scrapers/` — **registre central dans `__init__.py`** :
  `detect_provider(url)`, `scrape(url, bib)`, `scrape_event_all(url)`.
  Un module par fournisseur : `klikego.py`, `breizhchrono.py`, `timepulse.py`,
  `wiclax.py`, + `playwright_fallback.py` (provider par défaut).
  `base.py` = dataclass `ScrapedResult`. `utils.py` = `normalize_time/rank`.
- `scripts/` — `audit.py`, `seed_demo.py` (utilitaires hors runtime).

### Conventions scrapers

- Tout nouveau fournisseur : créer `scrapers/<nom>.py`, exposer `scrape()` (et
  `scrape_event_all()` si l'import de masse est possible), puis l'enregistrer
  dans le registre. **En v2** : `scrapers/registry.py` (registre Protocol). **En
  v1** : les 3 fonctions de `scrapers/__init__.py`. Provider inconnu → `playwright`.
- **Breizh Chrono réutilise la logique Klikego** (`klikego._parse_detail`,
  `_detect_event_type`) — ne pas dupliquer, factoriser dans `klikego.py`.
- Identification club lors d'un import épreuve : filtre `city=nantais` de l'API
  (plus fiable que le nom de club, qui varie : « TCN », « TRIATHLON CLUB NANTAIS »…).
- Les temps restent des **strings** (`"01:23:45"`), normalisés via `utils.py`.
  Splits adaptés au sport : **en v2** dans `splits` (JSON) + `raw_data` (JSON) ;
  **en v1** dans les colonnes dédiées + `raw_data` (JSON).

## Architecture frontend (`frontend/`)

> Une refonte `frontend-v2/` (Next.js + TypeScript + Tailwind + shadcn/ui) est
> spécifiée mais **pas encore codée** — voir `docs/superpowers/`.

- `App.jsx` — onglets + déclenche l'import épreuve en arrière-plan après save.
- `api/client.js` — appels `/api/*`. `constants.js` — constantes partagées.
- `components/` — `ScrapeForm` (scrape + édition + save, saisie manuelle si
  provider non supporté), `ResultsList` + `ResultCard`, `EventGroupList`,
  `ClubView` (stats club), `AdminView` (providers signalés).

## Conventions générales

- **Langue** : UI, commentaires et messages en **français** (avec accents).
- Commits : Conventional Commits (`feat:`, `fix:`…), déjà en place dans l'historique.
- Schéma DB — **v2** : migrations **Alembic** (`alembic revision --autogenerate`
  après modif d'un modèle, puis `alembic upgrade head`). **v1** (déprécié) :
  édition `models.py`, recréation auto sur DB vierge (migration prod manuelle).
- Tests unitaires **sans réseau** ; le réseau réel est isolé derrière le marker
  `integration` (`pytest.ini`).

## Fournisseurs supportés

Klikego, Breizh Chrono, TimePulse, Wiclax/G-Live (individuel + épreuve complète).
Types : Triathlon S/M/L/XL, Duathlon XS/S/M/L, SwimRun S/M/L, Aquathlon,
Aquarun, Bike & Run.
