# Tour backend — data-triathlon

Bienvenue. Ce parcours te fait ouvrir, dans le bon ordre, les fichiers qui
comptent pour contribuer au **backend** (FastAPI + SQLAlchemy + scrapers + CLI).

> **Tu n'es pas le bon profil ?** Si tu vas toucher au front (Next.js, App
> Router, composants React) ou aux deux couches, relance `/onboard` en
> choisissant `fullstack` ou `frontend` — les parcours diffèrent.

Chaque étape pointe **vers un fichier**. La source de vérité opérationnelle
reste `AGENTS.md` à la racine : ce parcours n'en recopie pas les détails, il
te dit **quels §§ y lire** et **dans quel ordre**.

## 1. La stack en 30 secondes

Python 3.13, dépendances via **uv** (pas de `pip`, pas de venv — `uv run`
s'en charge), FastAPI, **SQLAlchemy 2.0 synchrone** (pas d'async côté DB),
Pydantic v2 + `pydantic-settings`, **Alembic**, **pytest**. Versions et
commandes exhaustives : `AGENTS.md` §Stack et §Commandes. Si tu n'en
retiens qu'une chose : le flux va toujours dans un sens, `api → services
→ repositories → DB`, et seule la couche `repositories` touche `Session`.

## 2. AGENTS.md — la carte du terrain

Pour un profil backend, lis dans cet ordre :

- §Architecture backend — la topologie des dossiers.
- §Modèle normalisé — les 4 tables et pourquoi `splits` est un JSON.
- §Cache TTL — quand on re-scrape, quand on court-circuite.
- §Portée club et disciplines — les paramètres `scope=club` et
  `federal_only`, avec la leçon #76 (défauts neutres).
- §Sorties de la CLI (stdout parsable) — contrats de sortie, codes 0/1/2/130.
- §Conventions scrapers — comment ajouter un provider proprement.

Ces sections t'évitent 90 % des mauvais réflexes.

## 3. La constitution v1.1.0

Fichier : `.specify/memory/constitution.md`. Six principes non-négociables.
Deux méritent un flag rouge : **Principe II — couches à sens unique**
(un router n'ouvre pas de session, un service ne construit pas de SQL, une
**seule** définition de `is_tcn` / `tcn_clause` dans `app/core/club.py` —
trois listes divergentes = bug #76) et **Principe III — TDD sans réseau,
NON-NÉGOCIABLE** (httpx mocké avec **`respx`**, fixtures dans
`backend/tests/fixtures/`, réseau réel isolé derrière le marker
`integration`). Les quatre autres (langue, contrats API/CLI, neutralité
des paramètres, YAGNI) se lisent d'une traite.

## 4. Le point d'entrée : `create_app()`

Fichier : `backend/app/main.py`. La fabrique de l'application FastAPI. Tu y
verras le montage du CORS, les handlers d'erreurs custom, et l'agrégation
des routers sous `/api/v1`. C'est le fichier où tu regardes en cas de
« pourquoi l'endpoint X ne répond pas » — souvent, il n'est pas monté.

## 5. Le cœur : `app/core/`

Ouvre ces quatre-là :

- `backend/app/core/config.py` — `pydantic-settings`, lit `.env`, expose
  `settings`. C'est ici que tu ajoutes une variable d'env typée.
- `backend/app/core/database.py` — création du moteur SQLAlchemy, `SessionLocal`,
  `get_db()` (la dépendance FastAPI).
- `backend/app/core/club.py` — **l'invariant `is_tcn` / `tcn_clause`**.
  Une seule définition dans tout le dépôt, une **liste blanche** de libellés,
  match à l'égalité. Ne la réimplémente **jamais** ailleurs (front, scraper,
  autre service). Lecture obligatoire du §Portée club dans AGENTS.md.
- `backend/app/core/discipline.py` — disciplines fédérales vs. hors-fédération
  (trail, course à pied, cyclisme). Alimente le paramètre `federal_only`.

## 6. Les modèles SQLAlchemy

Fichier : `backend/app/models/` — quatre modèles : `athlete.py`
(`UNIQUE(nom, prenom, birth_date)`), `course.py` (`UNIQUE(name, event_date,
event_type)`, `source_url` = clé de cache TTL), `participation.py`
(`UNIQUE(course_id, bib_number)`, champ `splits` en **JSON** — pas des
colonnes figées, pour couvrir n'importe quel sport), `pending_provider.py`
(URLs de providers non encore supportés). Limite de segments dépassable
pour RaceResult (segments étiquetés) : détails et panel dans
`AGENTS.md` §Modèle normalisé.

## 7. Les DTO Pydantic

Fichier : `backend/app/schemas/` — les schémas d'entrée/sortie. Un DTO
n'est **pas** un modèle SQLAlchemy : c'est ce que ton endpoint accepte ou
renvoie. Tu passeras souvent par ici pour ajouter un champ à une réponse
d'API. Regarde `course.py` et `participation.py` pour le patron.

## 8. Les repositories

Fichier : `backend/app/repositories/course_repository.py` (ou
`participation_repository.py`). **La seule couche autorisée à toucher
`Session`.** Signature type : `def get_by_url(db: Session, url: str) ->
Course | None`. Aucune logique métier ici, uniquement des accès. Si tu es
tenté d'écrire une requête SQL dans un service : relis le principe II.

## 9. Les services

Le vrai lieu de la logique métier. Quatre à ouvrir en priorité :

- `backend/app/services/mapping.py` — `build_splits` + gabarit
  `_SPLIT_KEYS_BY_SPORT` : ré-étiquette les 5 slots positionnels d'un
  `ScrapedResult` selon `event_type` (duathlon → `course1`/`course2`…).
- `backend/app/services/cache.py` — `is_fresh(course)` : 10 min en cours,
  30 j sinon. `scrape_service` court-circuite le re-scrape si frais.
- `backend/app/services/import_service.py` — **le cœur du pipeline** :
  générateur de phases, réutilisé par le SSE côté API. Toute intégration
  nouvelle passe par ici.
- `backend/app/services/stats_service.py` — agrégation en lecture, bon
  exemple d'un service pur qui compose plusieurs repositories.

## 10. Les routers API

Fichier : `backend/app/api/v1/`. Ouvre `stats.py`, `courses.py`, et
`scrape.py` (le SSE d'import). Routers **fins** : validation Pydantic +
délégation immédiate au service. Aucun `select(...)` ici, aucun
`db.commit()`. `router.py` agrège tout et est monté sous `/api/v1` par
`create_app()`. Une future rupture de contrat vivra dans un `v2/` frère
(principe IV).

C'est ce que **toi** tu vas exposer : quand tu ajoutes un endpoint, tu écris
un router fin, tu passes par un service, et tu documentes le contrat.

## 11. Un scraper à ouvrir

Fichier : `backend/app/scrapers/klikego.py`. Regarde `_parse_detail` et
`_detect_event_type` : c'est la logique factorisée que Breizh Chrono
réutilise (`breizhchrono.py` importe depuis ici — ne la duplique pas). Puis
`backend/app/scrapers/registry.py` : le registre Protocol qui a remplacé les
`if-else` de dispatch. Enregistrement d'un nouveau provider = un
`scrape_event_all()` + une entrée dans `registry.py`. Voir §Conventions
scrapers.

Provider inconnu → fallback `playwright_fallback.py`.

## 12. La CLI batch

Fichier : `backend/app/cli/` — Typer, couche mince. `commands/` (une
commande par fichier, zéro logique métier — elle vit dans les services
`sheet_source`, `batch`, `bulk_import_service`, `rescrape_service`),
`progress.py` (reporters Rich / Plain), `reports.py` (`emit_outcome`, seul
endroit qui imprime le résultat final avec le bon code), `validators.py`
(rejette une option invalide **avant** tout travail — code 2).

Deux invariants (détails §Sorties de la CLI) : **stdout reste parsable**
(progression sur stderr ; avec `--json`, stdout ne contient **que** la
ligne JSON) ; **codes de sortie** `0` succès (même partiel ou « rien à
faire »), `1` échec total, `2` erreur d'usage, `130` Ctrl-C (prioritaire
sur `1`).

La boucle de rejeu d'échecs sans fichier d'état doit rester possible :

```bash
uv run python -m app.cli import-sheet --json \
  | jq -r '.failures[].url' \
  | uv run python -m app.cli rescrape-db --urls-from -
```

## 13. Les migrations Alembic

Fichier : `backend/alembic/versions/`. Cadre :

1. Tu modifies un modèle dans `app/models/`.
2. `uv run alembic revision --autogenerate -m "..."` — génère un fichier
   sous `versions/`.
3. **Relecture manuelle obligatoire** — l'autogenerate rate parfois un
   index, un `server_default`, une contrainte nommée. Commit après
   relecture.
4. `uv run alembic upgrade head` pour appliquer localement.

Jamais de `Base.metadata.create_all()` en dehors de `scripts/reset_db.py`.

## 14. Les tests

Fichier : `backend/tests/`. La structure calque les couches :
`test_repositories/`, `test_services/`, `test_api/`, `test_cli/`, plus un
`test_<provider>.py` par scraper (fixtures HTML/JSON dans `fixtures/`).

Deux commandes à connaître :

- `uv run pytest -m "not integration"` — défaut CI, tests unitaires, **sans
  réseau** (respx mocke httpx). C'est ce que tu lances avant chaque commit.
- `uv run pytest -m integration` — réseau réel, jamais en CI, à lancer
  localement avant de toucher à un scraper.

Rappel principe III : une nouvelle logique métier commence par un test
rouge, pas par du code.

## 15. Pour attaquer ta première contribution

Lis `docs/WORKFLOW-IA.md` (court) pour choisir ta voie : **Speckit** ou
**Superpowers** pour une vraie feature (les deux mènent au même résultat,
on ne les croise jamais), ou **sans plan** pour un bugfix ou 1-2
fichiers. Suggestion de première tâche : un endpoint de lecture simple
(un compteur, un filtre supplémentaire sur `stats`, un tri sur les
courses). Lance `/speckit-specify`, laisse-toi guider par
`/speckit-clarify` puis `/speckit-plan`. Tu toucheras dans l'ordre : un
schéma, un router, un service, un repository, des tests — exactement le
sens du flux. Bon voyage.
