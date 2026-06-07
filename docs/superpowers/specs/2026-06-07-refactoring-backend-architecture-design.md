# Refactoring backend — architecture en couches + modèle normalisé

> Design validé le 2026-06-07. Cible : nouveau backend `backend-v2/` en couches,
> modèle normalisé Athlete/Course/Participation, SQLAlchemy 2.0 sync.

## Contexte

Le MVP `data-triathlon` est fonctionnel mais le backend (`backend/`, ~3 800 lignes)
porte la dette typique d'un MVP : routers qui font tout (DB + logique + sérialisation),
modèle `Result` dénormalisé (1 ligne = 1 participation), registre scraper en `if-else`,
aucune couche service/repository, pas de config centralisée, pas de logging, pas de
migrations, pas de tests sur les routers.

## Décisions validées

- **Ambition** : architecture en couches **+ modèle normalisé** (Athlete / Course / Participation).
- **ORM** : SQLAlchemy 2.0 (sync) — pas de Tortoise/async.
- **Emplacement** : nouveau dossier `backend-v2/` ; l'ancien `backend/` reste déprécié.
- **Données** : on repart à zéro (re-scraping), pas de migration des données prod.
- **Contrat API** : nouveaux endpoints propres ; frontend adapté plus tard (hors scope).
- **Cache TTL dynamique** : inclus (10 min en cours / 30 j terminé).
- **Transverse** : config pydantic-settings, logging + erreurs, Alembic, tests + CI.

## Architecture cible

```
backend-v2/app/
  main.py                 # create_app()
  core/      config.py logging.py database.py exceptions.py club.py
  models/    athlete.py course.py participation.py pending_provider.py
  schemas/   athlete.py course.py participation.py scrape.py stats.py
  repositories/ athlete_repo.py course_repo.py participation_repo.py pending_provider_repo.py
  services/  scrape_service.py import_service.py mapping.py cache.py stats_service.py geocode_service.py
  api/       deps.py health.py scrape.py athletes.py courses.py participations.py stats.py admin.py
  scrapers/  base.py registry.py klikego.py breizhchrono.py timepulse.py wiclax.py
             prolivesport.py sportinnovation.py playwright_fallback.py utils.py
backend-v2/alembic/ + alembic.ini
backend-v2/tests/ conftest.py test_scrapers/ test_repositories/ test_services/ test_api/
.github/workflows/ci.yml
```

## Modèle normalisé

- **Athlete** : id, nom, prenom, gender, birth_date?, club?, created_at — UNIQUE(nom, prenom, birth_date).
- **Course** : id, source_url, provider, name, event_date?, event_type, is_relay, scraped_at, created_at — UNIQUE(name, event_date, event_type).
- **Participation** : id, athlete_id, course_id, club, category, bib_number, rank_overall/category/gender,
  total_time (str), status, splits (JSON), raw_data (JSON), created_at — UNIQUE(course_id, bib_number).
- **PendingProvider** : porté tel quel.

Les temps restent des strings normalisées (`scrapers/utils.normalize_time`). `splits` JSON
remplace les colonnes figées (corrige le gap duathlon course1/course2).

## Couches

- **api/** : routers fins (validation + délégation au service).
- **services/** : logique métier ; `scrape_service` = détection → cache TTL → scrape → mapping → repos.
- **repositories/** : seule couche qui touche la Session SQLAlchemy.
- **mapping.py** : ScrapedResult → upsert (Athlete, Course) + create Participation.
- **schemas/** : DTO Pydantic v2.

## Scrapers

Modules providers portés quasi tels quels (produisent déjà `ScrapedResult`). Améliorations :
registre Protocol (fin des `if-else`), `detect_event_type`/`split_athlete_name`/split map
centralisés dans `utils.py`, retry/backoff + logging réseau.

## Cache TTL (PRD F1)

`services/cache.py` : `is_fresh(course)` → TTL 10 min si course en cours (une participation
sans `total_time`), sinon 30 j. `scrape_service` court-circuite le re-scraping si frais.

## Endpoints

`POST /api/scrape`, `/scrape/event`, `/scrape/event/stream`, `GET /scrape/detect`,
`GET /api/athletes[/{id}]`, `GET /api/courses[/{id}]`, `/courses/events`,
`GET /api/participations`, `GET /api/stats[/events-geo]`, `*/api/admin/pending-providers`,
`GET /api/health` (vérifie la DB).

## Transverse

- **Config** : `Settings(BaseSettings)` — database_url, cors_origins (restreint), log_level, TTLs.
- **Logging** : `setup_logging()`, `getLogger(__name__)` par module.
- **Erreurs** : exceptions domaine + handlers FastAPI + rollback explicite import en masse.
- **Alembic** : révision initiale, suppression de `create_all()` au démarrage.
- **Tests** : conftest SQLite mémoire + TestClient ; réseau réel derrière marker `integration`.
- **CI** : `.github/workflows/ci.yml` → `pytest -m "not integration"` + `ruff`.

## Plan d'exécution

1. Squelette + socle. 2. Modèle + Alembic. 3. Scrapers + registre. 4. Services.
5. API + schemas. 6. Finitions. 7. (hors scope) bascule frontend.

## Vérification

- `alembic upgrade head` (SQLite vierge) → 4 tables.
- `uvicorn app.main:app` → `/docs` + `/api/health` état DB.
- `pytest -m "not integration"` vert.
- 2 imports successifs de la même URL → 2e `imported:0, skipped:N` (UNIQUE respecté).
- Re-scrape immédiat court-circuité par le cache TTL.

## Hors scope

Adaptation frontend, migration données prod, auth, file de tâches async, TypeScript.
