# Migration du backend vers uv — design

**Date** : 2026-07-12
**Branche** : `feat/use-uv-python`
**Périmètre** : `backend/` uniquement (le frontend reste sur npm)

## Problème

Le backend s'installe aujourd'hui avec `pip` + `requirements.txt` /
`requirements-dev.txt`, dans un venv que le contributeur crée et active à la
main. Trois conséquences :

- **Pas de lockfile.** Les `==` figent les dépendances directes, mais rien ne
  fige les transitives : deux installations à deux dates peuvent diverger.
- **Le venv est un prérequis manuel.** Le `Taskfile.yml` le dit explicitement
  (« Prérequis backend : venv Python activé ») ; on peut travailler avec des
  dépendances périmées sans s'en rendre compte.
- **La version de Python n'est cohérente nulle part** : `.python-version` et la
  CI disent 3.13, le `Dockerfile` construit sur `python:3.11-slim`, `ruff.toml`
  cible `py311`, `AGENTS.md` annonce « Python 3.11+ ».

## Solution retenue

Migration complète vers **uv** : `pyproject.toml` + `uv.lock` deviennent la
source de vérité ; `requirements.txt` et `requirements-dev.txt` disparaissent.
Toutes les commandes passent par `uv run`, qui synchronise le venv avant
d'exécuter — l'environnement ne peut plus dériver.

### Alternatives écartées

- **uv comme simple installateur** (`uv pip install -r requirements.txt`) :
  gagne la vitesse, mais ni lockfile ni gestion de l'interpréteur. Le principal
  problème resterait entier.
- **pyproject + `uv export` vers un requirements.txt** pour Render/Docker :
  filet de sécurité inutile — Render supporte uv nativement (voir plus bas), et
  un fichier généré qu'il faut penser à régénérer est une source de dérive de
  plus.

## Conception

### 1. `backend/pyproject.toml` — le fichier pivot

```toml
[project]
name = "data-triathlon-backend"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [                # les 14 lignes de l'ex-requirements.txt :
  "fastapi[standard]>=0.115.5", "uvicorn[standard]>=0.32.1", "python-dotenv>=1.0.1",
  "pydantic>=2.10.3", "pydantic-settings>=2.7.0", "sqlalchemy>=2.0.36",
  "alembic>=1.14.0", "psycopg2-binary>=2.9.10", "httpx>=0.28.1",
  "beautifulsoup4>=4.12.3", "lxml>=5.3.0", "playwright>=1.49.0",
  "typer>=0.26.7", "rich>=15.0.0",
]

[dependency-groups]
dev = ["pytest>=8.3.4", "respx>=0.21.1", "ruff>=0.8.4"]   # PEP 735

[tool.uv]
package = false
```

- **Contraintes plancher (`>=`) et non plus épinglages exacts (`==`).** La
  reproductibilité vient désormais de `uv.lock`, committé, qui fige les versions
  exactes — directes *et* transitives — pour dev, CI et prod.
- **Groupe `dev` (PEP 735)** : `uv sync` l'installe par défaut, `uv sync --no-dev`
  l'écarte (build Render et Docker).
- **`package = false`** : le backend est une application, pas une bibliothèque.
  Rien à builder, aucune installation editable ; `pytest.ini` fait déjà le
  `pythonpath = .` nécessaire.

### 2. Configs d'outils regroupées dans `pyproject.toml`

`pytest.ini` → `[tool.pytest.ini_options]` et `ruff.toml` → `[tool.ruff]` ; les
deux fichiers sont supprimés. Contenu transposé à l'identique, à une exception :
`target-version` passe de `py311` à `py313`. `alembic.ini` reste à part
(Alembic ne lit pas `pyproject.toml`).

### 3. Python 3.13 partout

`requires-python = ">=3.13"`, `.python-version` inchangé (3.13), `Dockerfile` sur
`python:3.13-slim`, `ruff` sur `py313`, `AGENTS.md` corrigé. Effet secondaire
utile : uv télécharge lui-même l'interpréteur s'il manque, donc contribuer ne
demande plus d'avoir Python 3.13 installé au préalable.

### 4. `uv run` partout

Le `Taskfile.yml` perd son prérequis « venv activé » :

| Tâche | Avant | Après |
|---|---|---|
| `b:install` | `pip install -r requirements-dev.txt` | `uv sync` |
| `b:dev` | `uvicorn app.main:app --reload --port 8001` | `uv run uvicorn …` |
| `b:migrate` / `b:migration` | `alembic …` | `uv run alembic …` |
| `b:reset-db` | `python scripts/reset_db.py` | `uv run python scripts/reset_db.py` |
| `b:test*` | `pytest …` | `uv run pytest …` |
| `b:lint*` | `ruff check …` | `uv run ruff check …` |

Même traitement pour la CLI de batch (`uv run python -m app.cli …`) et pour
toutes les commandes citées dans `README.md`, `backend/README.md` et `AGENTS.md`.

### 5. CI (`.github/workflows/ci.yml`, job `backend`)

`actions/setup-python` + cache pip sont remplacés par `astral-sh/setup-uv`
(cache activé), suivi de `uv sync --locked`. Le flag `--locked` fait **échouer la
CI si `uv.lock` n'est pas à jour avec `pyproject.toml`** : c'est le garde-fou qui
empêche une dépendance ajoutée sans lock de passer en revue. Lint et tests
deviennent `uv run ruff check .` et `uv run pytest -m "not integration"`.

Le job `frontend` n'est pas touché.

### 6. Render

Render supporte uv nativement : la présence d'un `uv.lock` à la racine du service
(ici `backend/`, via `rootDir`) suffit à mettre uv à disposition du build.

- `render.yaml` : `buildCommand: uv sync --no-dev`,
  `startCommand: uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- **Étape obligatoire, hors fichier** : les deux services (`data-triathlon` en
  prod, `triathlon-backend-preview`) ont été créés hors blueprint ; leurs
  `buildCommand` / `startCommand` sont stockés **dans le dashboard Render** et ne
  sont pas relus depuis `render.yaml`. Ils doivent être mis à jour (MCP Render ou
  dashboard) **avant** le premier déploiement post-migration, sinon le build
  échoue sur un `requirements.txt` qui n'existe plus.

### 7. `backend/Dockerfile`

```dockerfile
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev          # couche de deps, invalidée par le seul lock
COPY . .
ENV PATH="/app/.venv/bin:$PATH"
```

Copier `pyproject.toml` + `uv.lock` **avant** le code source garde la couche de
dépendances en cache tant que le lock ne bouge pas. `--frozen` interdit toute
re-résolution silencieuse dans l'image.

Simplification tentée : **supprimer l'installation apt de `gcc` et `libpq-dev`**.
`psycopg2-binary` et `lxml` publient des wheels cp313 ; plus rien ne devrait
compiler. À valider par un `docker build` réel — si ça casse, on les remet, et
c'est la seule partie du design qui peut être revue à la baisse.

## Vérification

La migration n'ajoute aucun test : elle change la façon d'installer et de lancer,
pas le comportement. Elle est validée par l'exécution réelle de chaque surface :

1. `uv sync` depuis un `backend/.venv` supprimé → venv recréé, Python 3.13.
2. `uv run pytest -m "not integration"` → même nombre de tests verts qu'avant la
   migration (relevé sur `main` au préalable), sans venv activé.
3. `uv run ruff check .` → propre (config lue depuis `pyproject.toml`).
4. `uv run uvicorn app.main:app --port 8001` → l'API répond, `/docs` s'affiche.
5. `uv run python -m app.cli rescrape-db --dry-run` → la CLI démarre.
6. `docker build backend/` → image construite ; conteneur démarré, `/health` OK.
7. CI verte sur la PR (c'est elle qui valide le workflow, pas une simulation locale).

## Hors périmètre

- Le frontend (npm) — inchangé.
- `alembic.ini`, les migrations, tout code applicatif — inchangés.
- La publication du backend comme package installable (`package = false` acté).
