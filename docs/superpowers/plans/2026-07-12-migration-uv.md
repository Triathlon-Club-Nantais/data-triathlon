# Migration du backend vers uv — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer pip + `requirements*.txt` par uv (`pyproject.toml` + `uv.lock`) sur le backend, de sorte que dev, CI, Docker et Render installent exactement les mêmes versions et que plus aucune commande n'exige un venv activé à la main.

**Architecture:** `backend/pyproject.toml` devient le fichier pivot : dépendances (contraintes plancher `>=`), groupe `dev` (PEP 735), config pytest et config ruff. La reproductibilité vient de `backend/uv.lock`, committé. `requirements.txt`, `requirements-dev.txt`, `pytest.ini` et `ruff.toml` disparaissent. Toutes les surfaces d'exécution (Taskfile, CI, Dockerfile, render.yaml, docs) passent en `uv run`, qui synchronise le venv avant d'exécuter.

**Tech Stack:** uv 0.11.x, Python 3.13, FastAPI/SQLAlchemy/Alembic (inchangés), pytest, ruff, Docker, GitHub Actions, Render.

**Spec source:** `docs/superpowers/specs/2026-07-12-migration-uv-design.md`

## Global Constraints

- **Périmètre :** `backend/` + les fichiers racine qui pilotent le backend (`Taskfile.yml`, `render.yaml`, `.github/workflows/ci.yml`, `README.md`, `AGENTS.md`). Le frontend (npm) n'est **pas** touché — aucune modification dans `frontend/`, ni dans le job `frontend` de la CI, ni dans le service Vercel.
- **Aucun code applicatif modifié.** `app/`, `alembic/`, `alembic.ini`, `scripts/`, `tests/` restent identiques. Cette migration ne change ni le comportement ni les tests. Si une modification de `app/` ou `tests/` semble nécessaire, c'est le signe d'une erreur de config — ne pas « réparer » le code.
- **Python 3.13 partout.** `requires-python = ">=3.13"`, `.python-version` = `3.13` (déjà le cas, inchangé), `Dockerfile` sur `python:3.13-slim`, ruff `target-version = "py313"`, docs annonçant « Python 3.11+ » corrigées.
- **`uv.lock` est committé.** Il ne va **jamais** dans `.gitignore` ni dans `.dockerignore`.
- **Contraintes plancher (`>=`), pas d'épinglage exact (`==`)** dans `pyproject.toml`. C'est `uv.lock` qui fige les versions exactes, directes *et* transitives.
- **Nombre de tests de référence : 514 passés, 23 désélectionnés** (`pytest -m "not integration"`, relevé avant migration sur les `requirements` actuels avec Python 3.13). Après migration, ce chiffre doit être identique. Un écart = régression de config, pas un test à ajuster.
- **Langue :** commentaires, `desc:` du Taskfile et documentation en **français avec accents**.
- **Commits :** Conventional Commits, un commit par tâche.
- **Aucun nouveau test.** La migration change la façon d'installer et de lancer, pas le comportement : elle se valide par l'exécution réelle de chaque surface (tests existants verts, lint propre, API qui répond, image Docker qui démarre, CI verte).

---

## Structure des fichiers

**Créés**
- `backend/pyproject.toml` — le fichier pivot : métadonnées projet, dépendances, groupe `dev`, config pytest, config ruff.
- `backend/uv.lock` — généré par `uv sync`, jamais édité à la main, committé.

**Supprimés**
- `backend/requirements.txt`, `backend/requirements-dev.txt` — remplacés par `[project.dependencies]` et `[dependency-groups]`.
- `backend/pytest.ini` — remplacé par `[tool.pytest.ini_options]`.
- `backend/ruff.toml` — remplacé par `[tool.ruff]`.

**Modifiés**
- `backend/Dockerfile` — base `python:3.13-slim`, install via uv, couche de deps cachée sur le lock.
- `Taskfile.yml` — `uv sync` + `uv run` ; le prérequis « venv activé » disparaît de l'en-tête.
- `.github/workflows/ci.yml` — job `backend` uniquement : `astral-sh/setup-uv` + `uv sync --locked`.
- `render.yaml` — `buildCommand` / `startCommand` en uv.
- `README.md`, `backend/README.md`, `AGENTS.md` — prérequis et commandes.

**Hors fichiers (Render dashboard)**
- Les `buildCommand` / `startCommand` des deux services Render existants, à mettre à jour via MCP (tâche 5).

---

### Task 1 : `pyproject.toml`, lockfile, et retrait de pip

Le cœur de la migration. À la fin de cette tâche, le backend s'installe et se teste entièrement avec uv, sans venv activé.

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/uv.lock` (généré par `uv sync`, jamais écrit à la main)
- Delete: `backend/requirements.txt`, `backend/requirements-dev.txt`, `backend/pytest.ini`, `backend/ruff.toml`

**Interfaces:**
- Consumes: rien (première tâche).
- Produces: `backend/pyproject.toml` (source des deps + config pytest + config ruff) et `backend/uv.lock`. Toutes les tâches suivantes supposent que, depuis `backend/`, ces commandes fonctionnent sans venv activé :
  - `uv sync` (dev, avec le groupe `dev`) / `uv sync --no-dev` (prod) / `uv sync --locked` (CI, échoue si le lock est périmé) / `uv sync --frozen --no-dev` (Docker, aucune re-résolution)
  - `uv run pytest -m "not integration"`, `uv run ruff check .`, `uv run uvicorn app.main:app …`, `uv run alembic …`, `uv run python …`

- [ ] **Étape 1 : Créer `backend/pyproject.toml`**

Le contenu de `pytest.ini` et de `ruff.toml` est transposé à l'identique, à **une seule exception** : `target-version` passe de `py311` à `py313`. Ne pas en profiter pour ajouter des règles de lint ou changer `addopts` — un lint plus strict ferait échouer la tâche pour une raison sans rapport avec la migration.

```toml
[project]
name = "data-triathlon-backend"
version = "0.1.0"
description = "API FastAPI des résultats de compétition du Triathlon Club Nantais"
requires-python = ">=3.13"
dependencies = [
    "fastapi[standard]>=0.115.5",
    "uvicorn[standard]>=0.32.1",
    "python-dotenv>=1.0.1",
    "pydantic>=2.10.3",
    "pydantic-settings>=2.7.0",
    "sqlalchemy>=2.0.36",
    "alembic>=1.14.0",
    "psycopg2-binary>=2.9.10",
    "httpx>=0.28.1",
    "beautifulsoup4>=4.12.3",
    "lxml>=5.3.0",
    "playwright>=1.49.0",
    "typer>=0.26.7",
    "rich>=15.0.0",
]

# PEP 735 : installé par `uv sync`, écarté par `uv sync --no-dev` (Render, Docker).
[dependency-groups]
dev = [
    "pytest>=8.3.4",
    "respx>=0.21.1",
    "ruff>=0.8.4",
]

[tool.uv]
# Le backend est une application, pas une bibliothèque : rien à builder,
# aucune installation editable. `pythonpath = ["."]` ci-dessous suffit aux tests.
package = false

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-v"
markers = [
    "integration: tests nécessitant un accès réseau réel (pytest -m integration)",
]

[tool.ruff]
line-length = 100
target-version = "py313"
# Les migrations sont autogénérées par Alembic — hors périmètre du lint.
exclude = ["alembic/versions"]

[tool.ruff.lint]
select = ["E", "F", "I", "W", "UP", "B"]
ignore = [
    "E501",  # longueur de ligne gérée par le formateur
    "B008",  # Depends(...) en argument par défaut = motif idiomatique FastAPI
]

[tool.ruff.lint.isort]
known-first-party = ["app"]
```

- [ ] **Étape 2 : Supprimer les quatre fichiers remplacés**

Tant que `pytest.ini` et `ruff.toml` existent, ils **priment** sur la config de `pyproject.toml` : les laisser en place donnerait un faux vert à l'étape suivante (on testerait l'ancienne config).

```bash
cd backend
git rm requirements.txt requirements-dev.txt pytest.ini ruff.toml
```

- [ ] **Étape 3 : Générer le lockfile et le venv, en repartant de zéro**

Supprimer le venv existant est ce qui prouve que `uv sync` sait le reconstruire seul (c'est le point 1 de la vérification du design).

```bash
cd backend
rm -rf .venv
uv sync
```

Attendu : uv résout les dépendances, écrit `uv.lock`, crée `.venv` avec **Python 3.13** (il télécharge l'interpréteur s'il manque). La dernière ligne ressemble à `Installed NN packages in …`.

Contrôle de la version de Python dans le venv :

```bash
uv run python --version
```

Attendu : `Python 3.13.x`. Si c'est autre chose, `requires-python` ou `.python-version` (qui doit contenir `3.13`) est en cause.

- [ ] **Étape 4 : Vérifier que la suite de tests est intacte**

Sans venv activé — c'est tout l'intérêt.

```bash
cd backend
uv run pytest -m "not integration" -q
```

Attendu, à l'identique du relevé d'avant-migration : `514 passed, 23 deselected`.

Si le compte diffère : la config pytest n'est pas lue depuis `pyproject.toml` (vérifier la ligne `rootdir:`/`configfile:` en tête de sortie, elle doit pointer vers `pyproject.toml`), ou un fichier `pytest.ini` traîne encore. Ne pas modifier les tests.

- [ ] **Étape 5 : Vérifier que ruff lit bien la config de `pyproject.toml`**

```bash
cd backend
uv run ruff check .
```

Attendu : `All checks passed!`.

Si des erreurs apparaissent : soit la config n'est pas lue (`uv run ruff check . --show-settings | head -20` doit montrer `line-length = 100`), soit `target-version = "py313"` a activé de nouvelles corrections `UP` (pyupgrade). Dans ce second cas, appliquer `uv run ruff check --fix .` et **inspecter le diff** : ce doit être de la modernisation de syntaxe pure (typing, f-strings). Si `--fix` touche de la logique, s'arrêter et le signaler.

- [ ] **Étape 6 : Vérifier que l'API et la CLI démarrent**

```bash
cd backend
uv run uvicorn app.main:app --port 8001 &
sleep 3
curl -fsS http://localhost:8001/api/v1/health && echo OK
kill %1
```

Attendu : une réponse JSON de santé, puis `OK`.

```bash
cd backend
uv run python -m app.cli rescrape-db --dry-run
```

Attendu : la CLI démarre et rend son bilan (elle n'a pas besoin de réseau en `--dry-run`).

- [ ] **Étape 7 : Commit**

`uv.lock` **doit** être dans le commit — c'est lui qui porte la reproductibilité.

```bash
cd /home/thomas_jarrier/Workspace/TCN/data-triathlon/.worktrees/feat-use-uv-python
git add backend/pyproject.toml backend/uv.lock
git add -u backend/
git status --short   # attendu : A pyproject.toml, A uv.lock, D requirements.txt, D requirements-dev.txt, D pytest.ini, D ruff.toml
git commit -m "feat(backend): passe à uv (pyproject + uv.lock), retire pip et requirements"
```

---

### Task 2 : Taskfile et CI

Les deux surfaces d'exécution quotidiennes : la commande locale et le garde-fou de la PR.

**Files:**
- Modify: `Taskfile.yml` (en-tête + toutes les tâches `b:*`)
- Modify: `.github/workflows/ci.yml` (job `backend` uniquement)

**Interfaces:**
- Consumes: `backend/pyproject.toml` et `backend/uv.lock` (tâche 1).
- Produces: rien que les tâches suivantes consomment.

- [ ] **Étape 1 : Retirer le prérequis « venv activé » de l'en-tête du Taskfile**

Dans `Taskfile.yml`, remplacer le bloc de commentaire :

```yaml
# Prérequis backend : venv Python activé (cf. README). Les tâches `*:install`
# installent les dépendances ; elles n'activent pas le venv à votre place.
```

par :

```yaml
# Prérequis backend : uv (https://docs.astral.sh/uv/). Aucun venv à activer :
# `uv run` synchronise l'environnement depuis uv.lock avant d'exécuter.
```

- [ ] **Étape 2 : Passer les tâches `b:*` en uv**

Toujours dans `Taskfile.yml`, remplacer chacune des commandes suivantes. Les `desc:` changent uniquement là où elles mentionnent pip.

`b:install` :

```yaml
  b:install:
    desc: 'backend : installe les dépendances (uv sync, dev inclus)'
    dir: backend
    cmds:
      - uv sync
```

`b:dev` :

```yaml
    cmds:
      - uv run uvicorn app.main:app --reload --port 8001
```

`b:migrate` :

```yaml
    cmds:
      - uv run alembic upgrade head
```

`b:migration` :

```yaml
    cmds:
      - uv run alembic revision --autogenerate -m "{{.CLI_ARGS}}"
```

`b:reset-db` :

```yaml
    cmds:
      - uv run python scripts/reset_db.py {{.CLI_ARGS}}
```

`b:test` :

```yaml
    cmds:
      - uv run pytest -m "not integration"
```

`b:test:integration` :

```yaml
    cmds:
      - uv run pytest -m integration
```

`b:test:all` :

```yaml
    cmds:
      - uv run pytest
```

`b:lint` :

```yaml
    cmds:
      - uv run ruff check .
```

`b:lint:fix` :

```yaml
    cmds:
      - uv run ruff check --fix .
```

Les tâches `f:*` (frontend) et `docker:*` ne changent pas.

- [ ] **Étape 3 : Vérifier le Taskfile**

```bash
cd /home/thomas_jarrier/Workspace/TCN/data-triathlon/.worktrees/feat-use-uv-python
task b:lint
task b:test
```

Attendu : `All checks passed!` puis `514 passed, 23 deselected`.

Contrôle qu'aucune commande pip ne subsiste :

```bash
grep -n "pip\|requirements" Taskfile.yml
```

Attendu : aucune ligne.

- [ ] **Étape 4 : Passer le job `backend` de la CI sur uv**

Dans `.github/workflows/ci.yml`, remplacer les quatre steps du job `backend` (de `actions/setup-python` à `pytest`) par :

```yaml
      - uses: astral-sh/setup-uv@v8
        with:
          enable-cache: true
          cache-dependency-glob: backend/uv.lock

      # --locked : échoue si uv.lock n'est pas à jour avec pyproject.toml.
      # C'est le garde-fou qui empêche une dépendance ajoutée sans lock de passer en revue.
      - name: Install dependencies
        run: uv sync --locked

      - name: Lint (ruff)
        run: uv run ruff check .

      - name: Tests (hors réseau)
        run: uv run pytest -m "not integration"
```

Le `defaults.run.working-directory: backend` du job est conservé — c'est lui qui fait que `uv sync` trouve `backend/pyproject.toml`. Le step `actions/checkout@v4` est conservé. **Le job `frontend` n'est pas touché.**

- [ ] **Étape 5 : Vérifier localement le comportement de `--locked`**

C'est le garde-fou de la CI : autant s'assurer qu'il ne se déclenche pas à tort sur le lock qu'on vient de committer.

```bash
cd backend
uv sync --locked
```

Attendu : la synchro passe sans erreur (le lock est à jour). Si uv répond `The lockfile is not up-to-date`, c'est que `pyproject.toml` a été modifié après le `uv lock` — relancer `uv sync` puis re-committer `uv.lock`.

- [ ] **Étape 6 : Commit**

```bash
cd /home/thomas_jarrier/Workspace/TCN/data-triathlon/.worktrees/feat-use-uv-python
git add Taskfile.yml .github/workflows/ci.yml
git commit -m "ci(backend): exécute Taskfile et CI via uv run"
```

---

### Task 3 : Dockerfile et render.yaml

Les deux surfaces de déploiement. À la fin de cette tâche, l'image se construit et le conteneur répond, pour de vrai.

**Files:**
- Modify: `backend/Dockerfile`
- Modify: `render.yaml`

**Interfaces:**
- Consumes: `backend/pyproject.toml`, `backend/uv.lock` (tâche 1).
- Produces: une image dont le venv est en `/app/.venv`, placé sur le `PATH` — donc `alembic` et `uvicorn` restent appelables sans préfixe dans le `CMD`.

- [ ] **Étape 1 : Réécrire `backend/Dockerfile`**

Trois choses à préserver du fichier actuel, que le design ne rappelle pas et qu'il serait facile de perdre : l'utilisateur **non-root** (`appuser`), `EXPOSE 8000`, et le `CMD` qui applique les migrations avant de démarrer l'API. `PYTHONDONTWRITEBYTECODE` disparaît en revanche : `UV_COMPILE_BYTECODE=1` précompile désormais le bytecode au build, ce qui est l'inverse de ce que cette variable demandait.

```dockerfile
# Image API (sans navigateurs Playwright). Le fallback Playwright pourra être isolé dans une
# image dédiée ultérieurement (voir README — Suites).
FROM python:3.13-slim

# uv est copié depuis son image officielle : version épinglée, pas d'installation à la volée.
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /bin/

ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

WORKDIR /app

RUN groupadd -r appuser && useradd -r -g appuser appuser

# Les dépendances d'abord : cette couche n'est invalidée que si le lock change.
# --frozen : aucune re-résolution silencieuse dans l'image. --no-dev : pas de pytest/ruff en prod.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Le code ensuite : le modifier ne réinstalle pas les dépendances.
COPY . .
RUN chown -R appuser:appuser /app
USER appuser

# Le venv du projet sur le PATH : alembic et uvicorn s'appellent sans préfixe.
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Applique les migrations puis démarre l'API.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

Noter ce qui a **disparu** : le `RUN apt-get install gcc libpq-dev`. C'est le pari du design — `psycopg2-binary` et `lxml` publient des wheels cp313, plus rien ne devrait compiler. L'étape suivante le tranche.

`backend/.dockerignore` contient déjà `.venv/` : le venv local n'écrasera pas celui de l'image lors du `COPY . .`. Ne rien y changer, et surtout **ne pas** y ajouter `uv.lock`, que le build doit voir.

- [ ] **Étape 2 : Construire l'image — c'est ici qu'on valide la suppression de gcc**

```bash
cd /home/thomas_jarrier/Workspace/TCN/data-triathlon/.worktrees/feat-use-uv-python
docker build -t tri-backend-uv backend/
```

Attendu : `Successfully built` / `naming to docker.io/library/tri-backend-uv`.

**Si le build échoue** sur une compilation (message du type `error: command 'gcc' failed`, `Building wheel for psycopg2` ou `fatal error: libpq-fe.h: No such file`), c'est que le pari ne tient pas pour ce paquet. Remettre alors le bloc apt, juste après le `WORKDIR /app` :

```dockerfile
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*
```

puis relancer le build. C'est la seule partie du design qui peut être revue à la baisse ; le faire n'est pas un échec de la tâche, mais **le mentionner explicitement** dans le message de commit et dans le compte rendu.

- [ ] **Étape 3 : Démarrer le conteneur et vérifier que l'API répond**

```bash
docker run --rm -d --name tri-backend-uv-check \
  -p 8000:8000 -e DATABASE_URL=sqlite:///./triathlon.db tri-backend-uv
sleep 8
curl -fsS http://localhost:8000/api/v1/health && echo " OK"
docker rm -f tri-backend-uv-check
```

Attendu : les migrations s'appliquent au démarrage, puis une réponse JSON de santé suivie de `OK`. Si le `curl` échoue, lire les logs (`docker logs tri-backend-uv-check`) avant de conclure.

- [ ] **Étape 4 : Passer `render.yaml` en uv**

Render met uv à disposition du build dès qu'un `uv.lock` est présent à la racine du service (ici `backend/`, via `rootDir`). Remplacer les deux commandes :

```yaml
    buildCommand: uv sync --frozen --no-dev
    startCommand: uv run --no-sync alembic upgrade head && uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

`--frozen` aligne le build sur l'image Docker (aucune re-résolution silencieuse) ; `--no-sync` évite que `uv run` re-synchronise l'environnement à chaque démarrage alors que le build l'a déjà figé.

Le reste du fichier (`type`, `name`, `runtime: python`, `autoDeploy: false`, `rootDir: backend`, `envVars`) est inchangé.

- [ ] **Étape 5 : Commit**

```bash
cd /home/thomas_jarrier/Workspace/TCN/data-triathlon/.worktrees/feat-use-uv-python
git add backend/Dockerfile render.yaml
git commit -m "build(backend): image Docker et Render sur uv, base python:3.13-slim"
```

---

### Task 4 : Documentation

Les commandes de la doc sont ce que lit un contributeur — les laisser en pip annulerait le bénéfice de la migration.

**Files:**
- Modify: `README.md` (prérequis, installation backend, tests)
- Modify: `backend/README.md` (prérequis, installation, Alembic, reset, API, tests)
- Modify: `AGENTS.md` (stack, bloc de commandes, conventions)

**Interfaces:**
- Consumes: les commandes établies en tâche 1.
- Produces: rien.

Règle transverse pour cette tâche : **toute commande backend s'exécute désormais sans venv, préfixée par `uv run`** (ou `uv sync` pour l'installation).

Deux choses à ne **pas** toucher, pour garder le diff sur le sujet : la mention « ≈130 tests » du `README.md` (chiffre obsolète, mais c'est un autre correctif), et tout ce qui concerne le frontend.

- [ ] **Étape 1 : `README.md` — prérequis (ligne 22)**

Remplacer `- **Python 3.11+**` par :

```markdown
- **[uv](https://docs.astral.sh/uv/)** — gère les dépendances *et* l'interpréteur Python (3.13, téléchargé au besoin)
```

- [ ] **Étape 2 : `README.md` — installation backend (section « 3. Backend (FastAPI) »)**

Remplacer le bloc de commandes par :

```bash
cd backend

uv sync                                # crée .venv (Python 3.13) et installe depuis uv.lock

uv run alembic upgrade head            # crée / met à jour le schéma
uv run uvicorn app.main:app --reload --port 8001
```

Aucun venv à activer : `uv run` synchronise l'environnement avant d'exécuter.

- [ ] **Étape 3 : `README.md` — tests backend (section « Tests unitaires (sans réseau) »)**

Remplacer le bloc backend par :

```bash
cd backend
uv sync
uv run pytest -m "not integration"   # tests par couche (≈130)
uv run ruff check .                  # lint
```

Et, dans « Tests d'intégration (réseau réel) » :

```bash
cd backend
uv run pytest -m integration
```

- [ ] **Étape 4 : `backend/README.md` — prérequis et installation**

Remplacer `- Python 3.11+` par :

```markdown
- [uv](https://docs.astral.sh/uv/) — gère les dépendances et l'interpréteur (Python 3.13)
```

et le bloc d'installation par :

```bash
cd backend
uv sync   # crée .venv (Python 3.13) + installe les dépendances depuis uv.lock
```

> `uv sync --no-dev` écarte le groupe `dev` (pytest, respx, ruff) — c'est ce que font Render et l'image Docker.

- [ ] **Étape 5 : `backend/README.md` — les quatre autres blocs de commandes**

Section « Base de données (Alembic) » :

```bash
uv run alembic upgrade head                       # applique les migrations
uv run alembic revision --autogenerate -m "..."   # nouvelle migration après modif d'un modèle
```

Section « Réinitialiser la base » :

```bash
uv run python scripts/reset_db.py            # vide + migre + seed démo
uv run python scripts/reset_db.py --no-seed  # schéma vierge seulement (rapide, hors réseau)
uv run python scripts/reset_db.py --yes      # sans confirmation interactive
uv run python scripts/seed_demo.py           # (re)seed seul, sans toucher au schéma
```

Section « Lancer l'API » :

```bash
uv run uvicorn app.main:app --reload --port 8001  # API + /docs
```

Section « Tests & qualité » :

```bash
uv run pytest -m "not integration"   # tests rapides (sans réseau) — défaut CI
uv run pytest -m integration         # tests réseau réel (scrapers)
uv run ruff check .                  # lint
```

- [ ] **Étape 6 : `AGENTS.md` — stack, commandes, conventions**

Dans la section « Stack », remplacer `- **Backend** (`backend/`) : Python 3.11+, FastAPI 0.115, …` par une ligne qui annonce Python 3.13 et uv :

```markdown
- **Backend** (`backend/`) : Python 3.13, **uv** (`pyproject.toml` + `uv.lock`), FastAPI 0.115,
  SQLAlchemy 2.0 (sync), Pydantic v2 + pydantic-settings, **Alembic** (migrations), PostgreSQL
  (Supabase) / SQLite en dev. Scraping httpx + BeautifulSoup/lxml, fallback
  Playwright. Tests pytest, ruff. API versionnée sous `/api/v1`.
```

Puis remplacer les deux blocs de commandes de la section « Commandes » (en-têtes de commentaire compris — plus de « venv activé ») :

```bash
# Backend (depuis backend/ — aucun venv à activer, uv run s'en charge)
uv sync                                            # installe les dépendances (dev incluses)
uv run uvicorn app.main:app --reload --port 8001   # API + /docs (endpoints sous /api/v1)
uv run alembic upgrade head                        # applique les migrations
uv run alembic revision --autogenerate -m "..."    # nouvelle migration après modif d'un modèle
uv run python scripts/reset_db.py                  # reset base dev SQLite (vide + migre + seed démo)
uv run python scripts/reset_db.py --no-seed --yes  # schéma vierge seul (refuse si DB non-SQLite)
uv run pytest -m "not integration"                 # tests unitaires (sans réseau) — défaut CI
uv run pytest -m integration                       # tests réseau réel (scrapers)
uv run ruff check .                                # lint

# CLI de batch (depuis backend/)
uv run python -m app.cli import-sheet --dry-run     # import de masse (Sheet) : ce qui serait importé
uv run python -m app.cli import-sheet --limit 5     # import réel — progression en direct
uv run python -m app.cli rescrape-db --limit 10     # re-scrape la DB (force=True) ; --plain, --no-progress
uv run python -m app.cli rescrape-db --json | jq    # bilan machine-lisible (stdout = JSON seul)
```

Dans la phrase qui suit ces blocs, la mention de `.env` reste ; ajouter que les dépendances et la config des outils vivent dans `backend/pyproject.toml` (lock : `backend/uv.lock`).

Enfin, section « Conventions générales », la ligne sur les tests référence `pytest.ini`, qui n'existe plus :

```markdown
- Tests unitaires **sans réseau** ; le réseau réel est isolé derrière le marker
  `integration` (déclaré dans `backend/pyproject.toml`).
```

- [ ] **Étape 7 : Vérifier qu'aucune commande pip/venv ne subsiste dans la doc**

```bash
cd /home/thomas_jarrier/Workspace/TCN/data-triathlon/.worktrees/feat-use-uv-python
grep -rn "pip install\|requirements-dev\|requirements.txt\|source .venv\|python -m venv\|pytest.ini\|ruff.toml\|Python 3.11" README.md backend/README.md AGENTS.md
```

Attendu : **aucune ligne**. Toute occurrence restante est un oubli à corriger.

Contrôle complémentaire sur l'ensemble du dépôt (le seul rappel de `requirements` autorisé est celui du design et de ce plan, dans `docs/superpowers/`) :

```bash
grep -rln "requirements-dev\|requirements.txt" --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.venv . 
```

Attendu : uniquement `docs/superpowers/specs/2026-07-12-migration-uv-design.md` et `docs/superpowers/plans/2026-07-12-migration-uv.md`.

- [ ] **Étape 8 : Commit**

```bash
cd /home/thomas_jarrier/Workspace/TCN/data-triathlon/.worktrees/feat-use-uv-python
git add README.md backend/README.md AGENTS.md
git commit -m "docs: commandes backend en uv run, Python 3.13"
```

---

### Task 5 : Services Render (hors fichier)

**Étape obligatoire, et la seule qui puisse casser la production.** Les deux services Render ont été créés hors blueprint : leurs `buildCommand` / `startCommand` vivent **dans le dashboard**, pas dans `render.yaml`. Tant qu'ils n'ont pas été mis à jour, le prochain déploiement tentera un `pip install -r requirements.txt` sur un fichier qui n'existe plus, et échouera.

**Files:** aucun. Modification via MCP Render (ou, à défaut, le dashboard).

**Interfaces:**
- Consumes: les commandes de `render.yaml` (tâche 3), qui font foi.
- Produces: deux services Render alignés sur uv.

**Prérequis :** cette tâche se fait **avant** le premier déploiement post-migration (donc avant le merge sur `main`, qui déclenche la preview via le workflow `deploy.yml`), et non après. Elle ne dépend pas du merge : les services peuvent être reconfigurés pendant que la PR est en revue — les commandes uv ne s'exécuteront qu'au prochain déploiement.

- [ ] **Étape 1 : Identifier les deux services**

Utiliser l'outil MCP `mcp__render__list_services`. Deux services web sont attendus : **`data-triathlon`** (production) et **`triathlon-backend-preview`** (preview). Relever leur `id` (format `srv-…`).

Si la liste ne renvoie rien, sélectionner d'abord l'espace de travail avec `mcp__render__list_workspaces` puis `mcp__render__select_workspace`.

- [ ] **Étape 2 : Relever les commandes actuelles (avant de les écraser)**

Pour chacun des deux `id`, appeler `mcp__render__get_service` et noter les `buildCommand` / `startCommand` en place. Attendu : quelque chose comme `pip install -r requirements.txt` et `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Les conserver dans le compte rendu : c'est le seul moyen de revenir en arrière si le déploiement échoue.

- [ ] **Étape 3 : Mettre à jour les deux services**

Pour chaque `id`, appeler `mcp__render__update_web_service` avec exactement les commandes de `render.yaml` :

- `buildCommand` : `uv sync --frozen --no-dev`
- `startCommand` : `uv run --no-sync alembic upgrade head && uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Ne toucher à **rien d'autre** : ni `rootDir` (`backend`), ni les variables d'environnement (`DATABASE_URL`), ni l'auto-deploy.

- [ ] **Étape 4 : Vérifier**

Re-appeler `mcp__render__get_service` sur les deux `id` et confirmer que les deux commandes sont bien celles ci-dessus. Attendu : aucune mention de `pip` ni de `requirements`.

- [ ] **Étape 5 : Compte rendu**

Rien à committer. Signaler dans le compte rendu : les deux services mis à jour (nom + id), les anciennes commandes (pour rollback), et le fait que la vérification réelle aura lieu au premier déploiement — la CI verte sur la PR ne couvre pas Render.

---

## Vérification finale (avant la PR)

Depuis `backend/`, sans venv activé, avec `.venv` préalablement supprimé :

| # | Commande | Attendu |
|---|---|---|
| 1 | `rm -rf .venv && uv sync` | venv recréé, `uv run python --version` → `Python 3.13.x` |
| 2 | `uv run pytest -m "not integration"` | `514 passed, 23 deselected` |
| 3 | `uv run ruff check .` | `All checks passed!` |
| 4 | `uv run uvicorn app.main:app --port 8001` | `/api/v1/health` répond, `/docs` s'affiche |
| 5 | `uv run python -m app.cli rescrape-db --dry-run` | la CLI démarre et rend son bilan |
| 6 | `docker build -t tri-backend-uv backend/` puis `docker run …` | image construite, `/api/v1/health` OK |
| 7 | `uv sync --locked` | passe (le lock est à jour avec `pyproject.toml`) |

Puis, sur la PR : **CI verte**. C'est elle qui valide le workflow — aucune simulation locale ne le fait à sa place.
