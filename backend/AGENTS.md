# Architecture backend

Archi en couches, le flux ne traverse qu'une direction
(`api → services → repositories → DB`). Le squelette de dossiers est dans
`README.md` ; ce fichier porte les **nuances** qui ne se lisent pas dans
l'arborescence, et chaque dossier qui a ses propres pièges porte son
`AGENTS.md` (`app/api/`, `app/cli/`, `app/core/`, `app/models/`,
`app/scrapers/`, `app/services/auth/`).

- `app/main.py` — usine `create_app()` : CORS, handlers d'erreurs, montage routers.
- `app/core/` — `config.py` (pydantic-settings), `logging.py`, `database.py`,
  `exceptions.py`, `time.py`, `club.py` (appartenance au TCN : **liste blanche**
  de libellés, match à l'égalité — cf. #76), `discipline.py` (disciplines
  fédérales vs trail / course à pied / cyclisme), `http.py` (**toute** sortie
  HTTP y passe, garde SSRF sur la requête et chaque redirection — #49, #101).
- `app/models/` — SQLAlchemy **normalisé** : `Athlete`, `Course`, `Participation`,
  `PendingProvider`.
- `app/schemas/` — DTO Pydantic v2 (entrée/sortie).
- `app/repositories/` — `*_repository.py` : **seule couche qui touche la Session**.
- `app/services/` — logique métier : `mapping`, `cache` (TTL), `scrape_service`,
  `import_service`, `stats_service`, `geocode_service`, plus les batches CLI
  (`sheet_source`, `batch`, `bulk_import_service`, `rescrape_service`,
  `progress`) et `auth/` (socle SSO).
- `app/cli/` — Typer, **couche mince** (zéro logique métier).
- `app/api/` — `deps.py` + `v1/` (routers fins : validation + délégation au service),
  agrégés dans `v1/router.py`, montés sous `/api/v1`. Une future API v2 vivra dans `v1/`→`v2/`.
- `app/scrapers/` — `registry.py` (registre **Protocol**) + un module par provider.
- `alembic/` — migrations (révision initiale = schéma complet).
- `tests/` — `test_repositories/`, `test_services/`, `test_api/`, `test_cli/`… (≈745 tests).

**Cache TTL** — `services/cache.py` : `is_fresh(course)` → 10 min si course en
cours (une participation sans `total_time`), sinon 30 j. `scrape_service`
court-circuite le re-scraping si frais. Réglable via
`CACHE_TTL_IN_PROGRESS_SECONDS` / `CACHE_TTL_FINISHED_SECONDS`.
