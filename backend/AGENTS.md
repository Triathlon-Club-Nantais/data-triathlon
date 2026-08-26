# Architecture backend

Archi en couches, le flux ne traverse qu'une direction
(`api → services → repositories → DB`). Le squelette de dossiers est dans
`README.md` ; ce fichier porte les **nuances** qui ne se lisent pas dans
l'arborescence, et chaque dossier qui a ses propres pièges porte son
`AGENTS.md` (`app/api/`, `app/cli/`, `app/core/`, `app/models/`,
`app/scrapers/`, `app/services/auth/`).

- `app/main.py` — usine `create_app()` : CORS, handlers d'erreurs, montage
  routers. **L'ordre des `add_middleware` y porte du sens** : la pile s'empile à
  l'envers, donc le premier monté est le plus proche du routeur.
  `SecurityHeadersMiddleware` l'est à dessein, pour voir le schéma déjà réécrit
  par `ProxyHeadersMiddleware` (#396).
- `app/core/` — `config.py` (pydantic-settings), `logging.py`, `database.py`,
  `exceptions.py`, `time.py`, `club.py` (appartenance au TCN : match à
  l'**égalité** sur une liste de libellés — cf. #76), `discipline.py`
  (disciplines fédérales vs trail / course à pied / cyclisme, par liste
  d'**exclusion**), `counter_scope.py` (les deux listes que ces deux modules
  lisent — voir `app/core/AGENTS.md`), `http.py` (**toute** sortie
  HTTP y passe, garde SSRF sur la requête et chaque redirection — #49, #101),
  `security_headers.py` (en-têtes de sécurité sur **toute** réponse — jumeau du
  `headers()` de `frontend/next.config.ts`, parce que les backends Render sont
  joignables directement ; sans la CSP, traitée à part — #396).
- `app/models/` — SQLAlchemy **normalisé** : `Athlete`, `Course`, `Participation`,
  `PendingProvider`.
- `app/schemas/` — DTO Pydantic v2 (entrée/sortie).
- `app/repositories/` — `*_repository.py` : **seule couche qui touche la Session**.
- `app/services/` — logique métier : `mapping`, `cache` (TTL), `scrape_service`,
  `import_service`, `stats_service`, `geocode_service`, plus les batches CLI
  (`sheet_source`, `batch`, `bulk_import_service`, `rescrape_service`,
  `progress`), `auth/` (socle SSO), `benevole_access` (#271 — mot de passe
  partagé, cookie signé HMAC ; distinct du socle SSO) et `site_access` (#509 —
  mot de passe partagé du site entier, même patron, secret et table propres),
  tous deux au-dessus du socle neutre `shared_password`
  (hachage/signature HMAC communs). **Les appelants s'adressent directement à
  `shared_password`** pour ces deux calculs : les deux modules de domaine ne
  gardent que ce qui leur est propre — nom du cookie, TTL, secret de session,
  `replace_password` — leurs délégations d'une ligne ayant été supprimées en
  revue de #513.
- `app/cli/` — Typer, **couche mince** (zéro logique métier).
- `app/api/` — `deps.py` + `v1/` (routers fins : validation + délégation au service),
  agrégés dans `v1/router.py`, montés sous `/api/v1`. Une future API v2 vivra dans `v1/`→`v2/`.
- `app/scrapers/` — `registry.py` (registre **Protocol**) + un module par provider.
- `alembic/` — migrations (révision initiale = schéma complet).
- `tests/` — `test_repositories/`, `test_services/`, `test_api/`, `test_cli/`… (3656 tests).
  **La suite tourne en parallèle par défaut** (`addopts = "-n 4"`, #508) : la sortie
  de plusieurs workers s'entrelace et `--pdb` ne s'attache plus. `-n 0` rétablit
  les deux, au prix de ~23 s sur la suite complète (35 s → 58 s) — et l'ôte des
  ~1,35 s que xdist coûte à une exécution d'un seul fichier. Les tests
  `integration` héritent aussi du `-n 4` : les lancer avec `-n 0` pour ne pas
  quadrupler le débit sortant vers les fournisseurs.

**Cache TTL** — `services/cache.py` : `is_fresh(course)` → 10 min si course en
cours (une participation sans `total_time`), sinon 30 j. `scrape_service`
court-circuite le re-scraping si frais. Réglable via
`CACHE_TTL_IN_PROGRESS_SECONDS` / `CACHE_TTL_FINISHED_SECONDS`.
