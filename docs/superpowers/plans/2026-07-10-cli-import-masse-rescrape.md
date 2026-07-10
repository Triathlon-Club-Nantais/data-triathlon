# CLI Typer — import de masse & rescrape DB : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter un module CLI Typer (`backend/app/cli.py`) exposant `import-sheet` (amorçage de la base depuis le Google Sheet des adhérents) et `rescrape-db` (rafraîchissement de tous les events en DB avec bypass du cache TTL).

**Architecture:** CLI mince par-dessus les services existants. Aucune logique de scraping ni d'accès DB direct : la CLI ouvre une `Session` via une fabrique et délègue à `import_service`/`course_repository` (archi en couches `cli → services → repositories → DB`). Trois modifications chirurgicales hors CLI rendent l'orchestration possible (flag `force`, `session_scope()`, `iter_all()`) ; tout le reste vit dans `app/cli.py`.

**Tech Stack:** Python 3.11+, Typer, httpx, csv (stdlib), SQLAlchemy 2.0, pytest.

## Global Constraints

- **Cible** : `backend/` uniquement. Toutes les commandes s'exécutent depuis `backend/` avec le venv activé (`.venv/bin/python` ou `source .venv/bin/activate`).
- **Langue** : code, commentaires, messages et docstrings en **français** (avec accents).
- **Commits** : Conventional Commits (`feat:`, `fix:`…).
- **Tests unitaires sans réseau** : monkeypatch de `import_service.import_event` (orchestration CLI) et de `registry.detect_provider` (détection). Jamais d'accès réseau réel. Fixture `db_session` SQLite en mémoire (`tests/conftest.py`).
- **`force`** : `False` par défaut → comportement API SSE / `/scrape/event` **inchangé**. `rescrape-db` passe `force=True`, `import-sheet` garde `force=False`.
- **`ruff check .` propre** à la fin de chaque tâche qui touche du code.
- **Dépendance Typer** : version installée en transitif = `typer==0.26.7`. On la déclare explicitement à cette version dans `requirements.txt`.
- **URL par défaut du Sheet** (export CSV public, sans auth) :
  `https://docs.google.com/spreadsheets/d/1rtiVRFOQUGcaWCTDPTR4xA9UL22UsWosKjsYMcRMsew/export?format=csv&gid=1961918487`
- **En-tête de la colonne des liens** : `Donne-nous un lien pour accéder aux résultats.` — sélection par nom d'en-tête, repli sur l'index 9 (10ᵉ colonne).

## File Structure

Fichiers **modifiés** (changements chirurgicaux hors CLI) :

- `backend/app/services/import_service.py` — ajoute `force: bool = False` à `import_event` et `iter_import_event`.
- `backend/app/core/database.py` — ajoute le context manager `session_scope()`.
- `backend/app/repositories/course_repository.py` — ajoute `iter_all(db, *, provider=None, older_than_days=None)`.
- `backend/requirements.txt` — déclare `typer==0.26.7`.

Fichiers **créés** :

- `backend/app/cli.py` — module Typer : helpers purs (`normalize_url`, `dedupe_links`, `parse_sheet_csv`, `is_supported`), cœurs orchestrateurs (`run_import_sheet`, `run_rescrape_db`), rendus (`render_sheet_report`, `render_rescrape_report`), et les deux commandes Typer.
- `backend/tests/test_cli.py` — tests des helpers, de l'orchestration et du dry-run.

Fichiers de test **modifiés/créés** :

- `backend/tests/test_services/test_import_service.py` — test du flag `force`.
- `backend/tests/test_core/test_session_scope.py` — test de `session_scope()`.
- `backend/tests/test_repositories/test_course_repository.py` — test de `iter_all()`.

---

### Task 1 : Flag `force` sur l'import

Rend le bypass du cache TTL possible : quand `force=True`, on saute l'appel à `_cached_result` (seul point qui consulte `cache.is_fresh`). Défaut `False` → API SSE inchangée.

**Files:**
- Modify: `backend/app/services/import_service.py:132-155` (`import_event`) et `:158-172` (début `iter_import_event`)
- Test: `backend/tests/test_services/test_import_service.py`

**Interfaces:**
- Produces :
  - `import_service.import_event(db: Session, url: str, settings: Settings, force: bool = False) -> dict`
  - `import_service.iter_import_event(db: Session, url: str, settings: Settings, force: bool = False) -> Iterator[dict]`

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter à la fin de `backend/tests/test_services/test_import_service.py` :

```python
def test_force_bypasse_le_cache_ttl(db_session, patch_scraper):
    """Avec force=True, on re-scrape même si la course est fraîche (cache non expiré)."""
    patch_scraper([_result("1", "DUPONT")])
    import_service.import_event(db_session, URL, _settings())

    # Course fraîche → sans force, le cache court-circuite le re-scraping.
    out = import_service.import_event(db_session, URL, _settings())
    assert out.get("cached") is True

    # Avec force=True → re-scrape malgré la fraîcheur ; le dossard 2 est nouveau.
    patch_scraper([_result("1", "DUPONT"), _result("2", "MARTIN")])
    out = import_service.import_event(db_session, URL, _settings(), force=True)
    assert out == {"imported": 1, "skipped": 1}
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

Run: `.venv/bin/python -m pytest tests/test_services/test_import_service.py::test_force_bypasse_le_cache_ttl -v`
Expected: FAIL — `TypeError: import_event() got an unexpected keyword argument 'force'`

- [ ] **Step 3 : Implémenter le flag dans `import_event`**

Dans `backend/app/services/import_service.py`, remplacer la signature et le début de `import_event` :

```python
def import_event(db: Session, url: str, settings: Settings, force: bool = False) -> dict:
    """Import complet (bloquant). Renvoie {imported, skipped, [cached]}.

    force=True saute le cache TTL (`_cached_result`) → le scraping a toujours lieu.
    """
    url = _validate_url(url)

    if not force:
        cached = _cached_result(db, url, settings)
        if cached is not None:
            return cached

    results = _scrape_all(url)
```

- [ ] **Step 4 : Implémenter le flag dans `iter_import_event`**

Dans le même fichier, remplacer la signature et le bloc de cache de `iter_import_event` :

```python
def iter_import_event(
    db: Session, url: str, settings: Settings, force: bool = False
) -> Iterator[dict]:
    """
    Générateur de progression pour le SSE. Émet des dicts de phase :
      {phase: scraping} → {phase: saving, progress, total, imported, skipped}
      → {phase: done, …}   (ou {phase: error, message})

    force=True saute le cache TTL (`_cached_result`).
    """
    try:
        url = _validate_url(url)
    except InvalidUrlError as exc:
        yield {"phase": "error", "message": exc.message}
        return

    if not force:
        cached = _cached_result(db, url, settings)
        if cached is not None:
            yield {"phase": "done", "total": cached["skipped"], **cached}
            return
```

- [ ] **Step 5 : Lancer le test pour vérifier qu'il passe (et non-régression)**

Run: `.venv/bin/python -m pytest tests/test_services/test_import_service.py -v`
Expected: PASS — le nouveau test + tous les existants verts.

- [ ] **Step 6 : Lint + commit**

```bash
.venv/bin/ruff check app/services/import_service.py tests/test_services/test_import_service.py
git add app/services/import_service.py tests/test_services/test_import_service.py
git commit -m "feat(import): flag force pour bypasser le cache TTL"
```

---

### Task 2 : Context manager `session_scope()`

Ouvre/ferme une `Session` ORM hors requête FastAPI, pour la CLI.

**Files:**
- Modify: `backend/app/core/database.py` (ajout après `get_db`)
- Test: `backend/tests/test_core/test_session_scope.py` (créer)

**Interfaces:**
- Consumes : `SessionLocal` (déjà défini dans `database.py`)
- Produces : `database.session_scope() -> ContextManager[Session]`

- [ ] **Step 1 : Écrire le test qui échoue**

Créer `backend/tests/test_core/test_session_scope.py` :

```python
def test_session_scope_yield_puis_ferme(monkeypatch):
    """session_scope() fournit une Session et la ferme à la sortie du bloc."""
    from app.core import database

    fermee = {"v": False}

    class FakeSession:
        def close(self):
            fermee["v"] = True

    monkeypatch.setattr(database, "SessionLocal", lambda: FakeSession())

    with database.session_scope() as db:
        assert isinstance(db, FakeSession)
        assert fermee["v"] is False

    assert fermee["v"] is True


def test_session_scope_ferme_meme_en_cas_d_erreur(monkeypatch):
    from app.core import database

    fermee = {"v": False}

    class FakeSession:
        def close(self):
            fermee["v"] = True

    monkeypatch.setattr(database, "SessionLocal", lambda: FakeSession())

    try:
        with database.session_scope():
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    assert fermee["v"] is True
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

Run: `.venv/bin/python -m pytest tests/test_core/test_session_scope.py -v`
Expected: FAIL — `AttributeError: module 'app.core.database' has no attribute 'session_scope'`

- [ ] **Step 3 : Implémenter `session_scope`**

Dans `backend/app/core/database.py`, ajouter les imports en tête de fichier (après `import sqlite3`) :

```python
import contextlib
from collections.abc import Iterator
```

Puis ajouter à la fin du fichier, après `get_db()` :

```python
@contextlib.contextmanager
def session_scope() -> Iterator[Session]:
    """Ouvre une Session hors requête HTTP (CLI, scripts) et la ferme à la sortie."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4 : Lancer le test pour vérifier qu'il passe**

Run: `.venv/bin/python -m pytest tests/test_core/test_session_scope.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5 : Lint + commit**

```bash
.venv/bin/ruff check app/core/database.py tests/test_core/test_session_scope.py
git add app/core/database.py tests/test_core/test_session_scope.py
git commit -m "feat(core): context manager session_scope pour usage hors HTTP"
```

---

### Task 3 : Parcours de toutes les courses — `course_repository.iter_all`

Renvoie toutes les `Course` (non paginé), filtrables par `provider` et par ancienneté de `scraped_at`, pour alimenter `rescrape-db` sans fuite de requêtes ORM hors repository.

**Files:**
- Modify: `backend/app/repositories/course_repository.py` (imports en tête + ajout d'`iter_all` à la fin)
- Test: `backend/tests/test_repositories/test_course_repository.py` (ajout)

**Interfaces:**
- Produces : `course_repository.iter_all(db: Session, *, provider: str | None = None, older_than_days: int | None = None) -> list[Course]`

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter à la fin de `backend/tests/test_repositories/test_course_repository.py` :

```python
def test_iter_all_filtre_par_provider_et_anciennete(db_session):
    from datetime import timedelta

    from app.core.time import utcnow

    vieux = course_repository.get_or_create(
        db_session, name="Vieux", event_date=date(2025, 1, 1),
        event_type="triathlon-m", provider="klikego",
    )
    vieux.scraped_at = utcnow() - timedelta(days=40)
    frais = course_repository.get_or_create(
        db_session, name="Frais", event_date=date(2026, 1, 1),
        event_type="triathlon-m", provider="timepulse",
    )
    frais.scraped_at = utcnow()
    db_session.flush()

    tous = course_repository.iter_all(db_session)
    assert {c.name for c in tous} == {"Vieux", "Frais"}

    klikego = course_repository.iter_all(db_session, provider="klikego")
    assert {c.name for c in klikego} == {"Vieux"}

    anciens = course_repository.iter_all(db_session, older_than_days=30)
    assert {c.name for c in anciens} == {"Vieux"}
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

Run: `.venv/bin/python -m pytest tests/test_repositories/test_course_repository.py::test_iter_all_filtre_par_provider_et_anciennete -v`
Expected: FAIL — `AttributeError: module 'app.repositories.course_repository' has no attribute 'iter_all'`

- [ ] **Step 3 : Implémenter `iter_all`**

Dans `backend/app/repositories/course_repository.py`, remplacer la ligne d'import du haut :

```python
from datetime import date
```

par :

```python
from datetime import date, timedelta
```

Puis ajouter à la fin du fichier :

```python
def iter_all(
    db: Session,
    *,
    provider: str | None = None,
    older_than_days: int | None = None,
) -> list[Course]:
    """Toutes les courses (non paginé), filtrables par provider et ancienneté de scraped_at.

    Alimente le rescrape en masse ; l'accès DB reste confiné au repository.
    """
    q = db.query(Course)
    if provider:
        q = q.filter(Course.provider == provider)
    if older_than_days is not None:
        cutoff = utcnow() - timedelta(days=older_than_days)
        q = q.filter(Course.scraped_at < cutoff)
    return q.order_by(Course.event_date.desc().nullslast(), Course.name).all()
```

*(`utcnow` est déjà importé en haut du fichier : `from app.core.time import utcnow`.)*

- [ ] **Step 4 : Lancer le test pour vérifier qu'il passe (et non-régression)**

Run: `.venv/bin/python -m pytest tests/test_repositories/test_course_repository.py -v`
Expected: PASS — nouveau test + existants verts.

- [ ] **Step 5 : Lint + commit**

```bash
.venv/bin/ruff check app/repositories/course_repository.py tests/test_repositories/test_course_repository.py
git add app/repositories/course_repository.py tests/test_repositories/test_course_repository.py
git commit -m "feat(repo): course_repository.iter_all filtrable pour le rescrape en masse"
```

---

### Task 4 : Module CLI — squelette Typer + helpers purs

Crée `app/cli.py` avec l'app Typer et les 4 helpers purs (sans réseau ni DB) :
normalisation d'URL, déduplication, parsing CSV, test de support provider. Déclare `typer` dans `requirements.txt`.

**Files:**
- Create: `backend/app/cli.py`
- Modify: `backend/requirements.txt`
- Test: `backend/tests/test_cli.py` (créer)

**Interfaces:**
- Consumes : `registry.detect_provider(url: str) -> str`
- Produces :
  - `cli.normalize_url(url: str) -> str`
  - `cli.dedupe_links(links: list[str]) -> list[str]`
  - `cli.parse_sheet_csv(csv_text: str) -> tuple[list[str], int]` — renvoie `(liens_http, nb_lignes_sans_lien)`
  - `cli.is_supported(url: str) -> bool`
  - `cli.LINK_HEADER: str`, `cli.LINK_COLUMN_FALLBACK_INDEX: int`, `cli.DEFAULT_SHEET_URL: str`
  - `cli.app` (objet `typer.Typer`)

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer `backend/tests/test_cli.py` :

```python
from app import cli


def test_normalize_url_trim_casse_slash_fragment():
    variantes = [
        "  https://WWW.Klikego.COM/resultats/event/1/#top  ",
        "https://www.klikego.com/resultats/event/1",
    ]
    assert cli.normalize_url(variantes[0]) == cli.normalize_url(variantes[1])


def test_normalize_url_conserve_la_query():
    a = cli.normalize_url("https://www.klikego.com/e?heat=42")
    b = cli.normalize_url("https://www.klikego.com/e?heat=7")
    assert a != b  # la query distingue deux heats


def test_dedupe_collapse_les_variantes_normalisees():
    links = [
        "https://www.klikego.com/resultats/event/1",
        "https://www.klikego.com/resultats/event/1/",    # slash final
        "https://WWW.KLIKEGO.COM/resultats/event/1",      # casse host
        "https://www.klikego.com/resultats/event/1#top",  # fragment
        "https://www.klikego.com/resultats/event/2",
    ]
    assert cli.dedupe_links(links) == [
        "https://www.klikego.com/resultats/event/1",
        "https://www.klikego.com/resultats/event/2",
    ]


def test_parse_sheet_csv_extrait_la_colonne_par_en_tete():
    csv_text = (
        "Horodateur,Nom,Donne-nous un lien pour accéder aux résultats.\n"
        "x,Jean,https://www.klikego.com/resultats/event/1\n"
        "x,Paul,\n"          # Paul : ligne avec contenu mais sans lien
        ",,\n"                # ligne vide → ignorée
    )
    links, sans_lien = cli.parse_sheet_csv(csv_text)
    assert links == ["https://www.klikego.com/resultats/event/1"]
    assert sans_lien == 1


def test_parse_sheet_csv_repli_sur_index_9_si_en_tete_absent():
    header = ",".join(f"c{i}" for i in range(10))
    row = ",".join(["x"] * 9 + ["https://www.timepulse.fr/e/1"])
    links, _ = cli.parse_sheet_csv(f"{header}\n{row}\n")
    assert links == ["https://www.timepulse.fr/e/1"]


def test_is_supported_playwright_est_faux(monkeypatch):
    from app.scrapers import registry

    monkeypatch.setattr(registry, "detect_provider", lambda url: "playwright")
    assert cli.is_supported("http://x") is False

    monkeypatch.setattr(registry, "detect_provider", lambda url: "klikego")
    assert cli.is_supported("http://x") is True
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.cli'`

- [ ] **Step 3 : Créer `app/cli.py` (squelette + helpers)**

Créer `backend/app/cli.py` :

```python
"""
Outillage CLI (Typer) : import de masse depuis le Google Sheet & rescrape DB.

CLI mince par-dessus les services : aucune logique de scraping ni d'accès DB
direct. Invocable depuis backend/ :
    python -m app.cli import-sheet --dry-run
    python -m app.cli rescrape-db --dry-run
"""
import csv
import io
import logging
from urllib.parse import urlparse, urlunparse

import typer

from app.scrapers import registry

logger = logging.getLogger(__name__)

DEFAULT_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1rtiVRFOQUGcaWCTDPTR4xA9UL22UsWosKjsYMcRMsew/export?format=csv&gid=1961918487"
)
LINK_HEADER = "Donne-nous un lien pour accéder aux résultats."
LINK_COLUMN_FALLBACK_INDEX = 9  # 10e colonne, repli si l'en-tête n'est pas trouvé

app = typer.Typer(help="Outillage d'import de masse et de rescrape.")


def normalize_url(url: str) -> str:
    """Normalise pour la déduplication : trim, host en minuscule, slash final et
    fragment supprimés. La query est conservée (elle distingue deux heats)."""
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((scheme, netloc, path, parsed.params, parsed.query, ""))


def dedupe_links(links: list[str]) -> list[str]:
    """Dédoublonne par URL normalisée en conservant l'ordre et la forme d'origine."""
    seen: set[str] = set()
    out: list[str] = []
    for url in links:
        key = normalize_url(url)
        if key not in seen:
            seen.add(key)
            out.append(url)
    return out


def parse_sheet_csv(csv_text: str) -> tuple[list[str], int]:
    """Extrait la colonne des liens du CSV. Renvoie (liens_http, nb_lignes_sans_lien).

    Sélection par nom d'en-tête (LINK_HEADER), repli sur l'index 9. Les lignes
    entièrement vides sont ignorées ; une ligne non vide sans lien http est comptée
    dans nb_lignes_sans_lien.
    """
    rows = list(csv.reader(io.StringIO(csv_text)))
    if not rows:
        return [], 0
    header = rows[0]
    try:
        col = header.index(LINK_HEADER)
    except ValueError:
        col = LINK_COLUMN_FALLBACK_INDEX

    links: list[str] = []
    sans_lien = 0
    for row in rows[1:]:
        value = row[col].strip() if col < len(row) else ""
        if value.startswith("http"):
            links.append(value)
        elif any(cell.strip() for cell in row):
            sans_lien += 1
    return links, sans_lien


def is_supported(url: str) -> bool:
    """Supporté pour l'import de masse ⇔ le provider détecté n'est pas playwright."""
    return registry.detect_provider(url) != "playwright"


if __name__ == "__main__":
    app()
```

- [ ] **Step 4 : Déclarer `typer` dans requirements.txt**

Dans `backend/requirements.txt`, ajouter la ligne suivante à la fin :

```
typer==0.26.7
```

- [ ] **Step 5 : Lancer les tests pour vérifier qu'ils passent**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6 : Lint + commit**

```bash
.venv/bin/ruff check app/cli.py tests/test_cli.py
git add app/cli.py tests/test_cli.py requirements.txt
git commit -m "feat(cli): squelette Typer + helpers (normalize, dedupe, parse CSV, détection)"
```

---

### Task 5 : Commande `import-sheet`

Cœur orchestrateur `run_import_sheet` (testable sans réseau) + rendu + commande Typer qui télécharge le CSV et ouvre la session.

**Files:**
- Modify: `backend/app/cli.py` (ajout `dataclass`, `run_import_sheet`, `render_sheet_report`, `_download_csv`, commande `import-sheet`)
- Test: `backend/tests/test_cli.py` (ajout)

**Interfaces:**
- Consumes : `import_service.import_event(db, url, settings, force=False) -> dict`, `session_scope()`, `get_settings()`, helpers de Task 4
- Produces :
  - `cli.SheetOutcome` (dataclass : `imported`, `skipped`, `errors`, `ignored_by_host: dict[str, int]`, `rows_without_link: int`, `unique_supported: int`)
  - `cli.run_import_sheet(db, csv_text, settings, *, dry_run=False, limit=None, only_provider=None, delay=1.0) -> SheetOutcome`
  - `cli.render_sheet_report(outcome: SheetOutcome, *, dry_run: bool) -> str`

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à `backend/tests/test_cli.py` (en tête, compléter les imports) :

```python
from app.core.config import Settings


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)
```

Puis ajouter les tests :

```python
def test_run_import_sheet_compteurs_et_rapport(db_session, monkeypatch):
    from app.scrapers import registry
    from app.services import import_service

    monkeypatch.setattr(
        registry, "detect_provider",
        lambda url: "klikego" if "klikego" in url else "playwright",
    )
    calls = []

    def _import(db, url, settings, force=False):
        calls.append((url, force))
        return {"imported": 2, "skipped": 1}

    monkeypatch.setattr(import_service, "import_event", _import)

    csv_text = (
        "a,Donne-nous un lien pour accéder aux résultats.\n"
        "x,https://www.klikego.com/e/1\n"
        "x,https://www.klikego.com/e/1/\n"        # doublon du précédent
        "x,https://inconnu.example/e/2\n"          # non supporté
        "x,\n"                                      # sans lien
    )
    out = cli.run_import_sheet(db_session, csv_text, _settings(), delay=0.0)

    assert out.imported == 2
    assert out.skipped == 1
    assert out.errors == 0
    assert out.rows_without_link == 1
    assert out.ignored_by_host == {"inconnu.example": 1}
    assert out.unique_supported == 1
    # 1 seul lien supporté unique, importé avec force=False
    assert calls == [("https://www.klikego.com/e/1", False)]


def test_run_import_sheet_un_echec_n_interrompt_pas_le_batch(db_session, monkeypatch):
    from app.scrapers import registry
    from app.services import import_service

    monkeypatch.setattr(registry, "detect_provider", lambda url: "klikego")

    def _import(db, url, settings, force=False):
        if "boom" in url:
            raise RuntimeError("échec scrape")
        return {"imported": 1, "skipped": 0}

    monkeypatch.setattr(import_service, "import_event", _import)

    csv_text = (
        "a,Donne-nous un lien pour accéder aux résultats.\n"
        "x,https://www.klikego.com/boom\n"
        "x,https://www.klikego.com/ok\n"
    )
    out = cli.run_import_sheet(db_session, csv_text, _settings(), delay=0.0)
    assert out.errors == 1
    assert out.imported == 1


def test_run_import_sheet_dry_run_ne_scrape_pas(db_session, monkeypatch):
    from app.scrapers import registry
    from app.services import import_service

    monkeypatch.setattr(registry, "detect_provider", lambda url: "klikego")
    appels = []
    monkeypatch.setattr(
        import_service, "import_event",
        lambda *a, **k: appels.append(1) or {"imported": 0, "skipped": 0},
    )

    csv_text = (
        "a,Donne-nous un lien pour accéder aux résultats.\n"
        "x,https://www.klikego.com/e/1\n"
    )
    out = cli.run_import_sheet(db_session, csv_text, _settings(), dry_run=True, delay=0.0)
    assert appels == []
    assert out.unique_supported == 1


def test_run_import_sheet_only_provider_restreint(db_session, monkeypatch):
    from app.scrapers import registry
    from app.services import import_service

    monkeypatch.setattr(
        registry, "detect_provider",
        lambda url: "klikego" if "klikego" in url else "timepulse",
    )
    calls = []
    monkeypatch.setattr(
        import_service, "import_event",
        lambda db, url, settings, force=False: calls.append(url) or {"imported": 1, "skipped": 0},
    )

    csv_text = (
        "a,Donne-nous un lien pour accéder aux résultats.\n"
        "x,https://www.klikego.com/e/1\n"
        "x,https://www.timepulse.fr/e/2\n"
    )
    out = cli.run_import_sheet(
        db_session, csv_text, _settings(), only_provider="klikego", delay=0.0
    )
    assert calls == ["https://www.klikego.com/e/1"]
    assert out.imported == 1
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run: `.venv/bin/python -m pytest tests/test_cli.py -k import_sheet -v`
Expected: FAIL — `AttributeError: module 'app.cli' has no attribute 'run_import_sheet'`

- [ ] **Step 3 : Implémenter le cœur, le rendu et la commande**

Dans `backend/app/cli.py`, compléter les imports en tête :

```python
import csv
import io
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from urllib.parse import urlparse, urlunparse

import httpx
import typer

from app.core.config import get_settings
from app.core.database import session_scope
from app.scrapers import registry
from app.services import import_service
```

Ajouter la dataclass et les fonctions, **avant** le bloc `if __name__ == "__main__":** :

```python
@dataclass
class SheetOutcome:
    """Bilan d'un import-sheet."""
    imported: int = 0
    skipped: int = 0
    errors: int = 0
    rows_without_link: int = 0
    unique_supported: int = 0
    ignored_by_host: dict[str, int] = field(default_factory=dict)


def _host(url: str) -> str:
    return (urlparse(url).netloc or "").lower() or "(inconnu)"


def run_import_sheet(
    db,
    csv_text: str,
    settings,
    *,
    dry_run: bool = False,
    limit: int | None = None,
    only_provider: str | None = None,
    delay: float = 1.0,
) -> SheetOutcome:
    """Détecte, dédoublonne et importe les liens supportés du CSV du Sheet.

    En dry-run : ne scrape rien, ne persiste rien, ne temporise pas.
    Les liens non supportés vont au rapport (ignored_by_host) ; jamais une erreur.
    """
    links, rows_without_link = parse_sheet_csv(csv_text)
    unique = dedupe_links(links)

    supported: list[str] = []
    ignored_by_host: dict[str, int] = {}
    for url in unique:
        if is_supported(url):
            if only_provider and registry.detect_provider(url) != only_provider:
                continue
            supported.append(url)
        else:
            host = _host(url)
            ignored_by_host[host] = ignored_by_host.get(host, 0) + 1

    if limit is not None:
        supported = supported[:limit]

    outcome = SheetOutcome(
        rows_without_link=rows_without_link,
        unique_supported=len(supported),
        ignored_by_host=ignored_by_host,
    )
    if dry_run:
        return outcome

    for i, url in enumerate(supported):
        try:
            res = import_service.import_event(db, url, settings, force=False)
            outcome.imported += res.get("imported", 0)
            outcome.skipped += res.get("skipped", 0)
        except Exception as exc:
            outcome.errors += 1
            logger.warning("Échec import %s : %s", url, exc)
        if delay and i < len(supported) - 1:
            time.sleep(delay)

    return outcome


def render_sheet_report(outcome: SheetOutcome, *, dry_run: bool) -> str:
    """Rapport texte lisible : compteurs + table des ignorés groupés par host."""
    lignes = []
    titre = "IMPORT SHEET (dry-run)" if dry_run else "IMPORT SHEET"
    lignes.append(f"=== {titre} ===")
    lignes.append(f"Liens supportés uniques : {outcome.unique_supported}")
    lignes.append(f"Lignes sans lien        : {outcome.rows_without_link}")
    if not dry_run:
        lignes.append(f"Importées : {outcome.imported}")
        lignes.append(f"Ignorées  : {outcome.skipped}")
        lignes.append(f"En erreur : {outcome.errors}")
    if outcome.ignored_by_host:
        lignes.append("Liens non supportés (suivis dans #33) :")
        for host, count in sorted(outcome.ignored_by_host.items()):
            lignes.append(f"  - {host} : {count}")
    return "\n".join(lignes)


def _download_csv(url: str) -> str:
    """Télécharge le CSV public du Sheet (httpx, sans auth)."""
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text


@app.command("import-sheet")
def import_sheet(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Détecte et dédoublonne sans scraper ni persister."
    ),
    limit: int | None = typer.Option(None, "--limit", help="Borne le nombre d'épreuves."),
    only_provider: str | None = typer.Option(
        None, "--only-provider", help="Restreint à un provider (ex. klikego)."
    ),
    sheet_url: str = typer.Option(
        DEFAULT_SHEET_URL, "--sheet-url", envvar="IMPORT_SHEET_URL",
        help="Override la source CSV.",
    ),
    delay: float = typer.Option(
        1.0, "--delay", help="Pause de politesse entre scrapes réels (s)."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Rapport machine-lisible en plus du texte."
    ),
) -> None:
    """Amorce la base depuis le Google Sheet des adhérents."""
    settings = get_settings()
    csv_text = _download_csv(sheet_url)
    with session_scope() as db:
        outcome = run_import_sheet(
            db, csv_text, settings,
            dry_run=dry_run, limit=limit, only_provider=only_provider, delay=delay,
        )
    typer.echo(render_sheet_report(outcome, dry_run=dry_run))
    if json_output:
        typer.echo(json.dumps(asdict(outcome), ensure_ascii=False))
```

- [ ] **Step 4 : Lancer les tests pour vérifier qu'ils passent**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: PASS (helpers de Task 4 + 4 nouveaux tests import-sheet)

- [ ] **Step 5 : Vérifier `--help` de la commande**

Run: `.venv/bin/python -m app.cli import-sheet --help`
Expected: affiche l'aide avec les options `--dry-run`, `--limit`, `--only-provider`, `--sheet-url`, `--delay`, `--json`.

- [ ] **Step 6 : Lint + commit**

```bash
.venv/bin/ruff check app/cli.py tests/test_cli.py
git add app/cli.py tests/test_cli.py
git commit -m "feat(cli): commande import-sheet (dédup, filtrage, rapport)"
```

---

### Task 6 : Commande `rescrape-db`

Cœur orchestrateur `run_rescrape_db` (force=True) + rendu + commande Typer.

**Files:**
- Modify: `backend/app/cli.py` (ajout `RescrapeOutcome`, `run_rescrape_db`, `render_rescrape_report`, commande `rescrape-db`)
- Test: `backend/tests/test_cli.py` (ajout)

**Interfaces:**
- Consumes : `course_repository.iter_all(db, *, provider=None, older_than_days=None)`, `import_service.import_event(..., force=True)`, `session_scope()`, `get_settings()`
- Produces :
  - `cli.RescrapeOutcome` (dataclass : `imported`, `skipped`, `errors`, `total`, `dry_run_urls: list[str]`)
  - `cli.run_rescrape_db(db, settings, *, dry_run=False, older_than=None, provider=None, limit=None, delay=1.0) -> RescrapeOutcome`
  - `cli.render_rescrape_report(outcome: RescrapeOutcome, *, dry_run: bool) -> str`

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à `backend/tests/test_cli.py` :

```python
def test_run_rescrape_force_et_compte(db_session, monkeypatch):
    from datetime import date

    from app.repositories import course_repository
    from app.services import import_service

    course_repository.get_or_create(
        db_session, name="A", event_date=date(2026, 1, 1),
        event_type="triathlon-m", source_url="https://k/1", provider="klikego",
    )
    db_session.flush()

    calls = []

    def _import(db, url, settings, force=False):
        calls.append((url, force))
        return {"imported": 3, "skipped": 0}

    monkeypatch.setattr(import_service, "import_event", _import)

    out = cli.run_rescrape_db(db_session, _settings(), delay=0.0)
    assert out.total == 1
    assert out.imported == 3
    assert out.errors == 0
    # force=True : c'est le cœur de la commande
    assert calls == [("https://k/1", True)]


def test_run_rescrape_dry_run_liste_sans_scraper(db_session, monkeypatch):
    from datetime import date

    from app.repositories import course_repository
    from app.services import import_service

    course_repository.get_or_create(
        db_session, name="A", event_date=date(2026, 1, 1),
        event_type="triathlon-m", source_url="https://k/1", provider="klikego",
    )
    db_session.flush()

    appels = []
    monkeypatch.setattr(import_service, "import_event", lambda *a, **k: appels.append(1))

    out = cli.run_rescrape_db(db_session, _settings(), dry_run=True, delay=0.0)
    assert appels == []
    assert out.dry_run_urls == ["https://k/1"]
    assert out.total == 1


def test_run_rescrape_ignore_les_courses_sans_url(db_session, monkeypatch):
    from datetime import date

    from app.repositories import course_repository
    from app.services import import_service

    course_repository.get_or_create(
        db_session, name="SansUrl", event_date=date(2026, 1, 1),
        event_type="triathlon-m", source_url="", provider="klikego",
    )
    db_session.flush()

    appels = []
    monkeypatch.setattr(import_service, "import_event", lambda *a, **k: appels.append(1))

    out = cli.run_rescrape_db(db_session, _settings(), delay=0.0)
    assert out.total == 0
    assert appels == []


def test_run_rescrape_un_echec_n_interrompt_pas_le_batch(db_session, monkeypatch):
    from datetime import date

    from app.repositories import course_repository
    from app.services import import_service

    course_repository.get_or_create(
        db_session, name="Boom", event_date=date(2026, 1, 1),
        event_type="triathlon-m", source_url="https://k/boom", provider="klikego",
    )
    course_repository.get_or_create(
        db_session, name="Ok", event_date=date(2026, 1, 2),
        event_type="triathlon-m", source_url="https://k/ok", provider="klikego",
    )
    db_session.flush()

    def _import(db, url, settings, force=False):
        if "boom" in url:
            raise RuntimeError("échec")
        return {"imported": 1, "skipped": 0}

    monkeypatch.setattr(import_service, "import_event", _import)

    out = cli.run_rescrape_db(db_session, _settings(), delay=0.0)
    assert out.total == 2
    assert out.errors == 1
    assert out.imported == 1
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run: `.venv/bin/python -m pytest tests/test_cli.py -k rescrape -v`
Expected: FAIL — `AttributeError: module 'app.cli' has no attribute 'run_rescrape_db'`

- [ ] **Step 3 : Implémenter le cœur, le rendu et la commande**

Dans `backend/app/cli.py`, ajouter l'import du repository aux imports du haut :

```python
from app.repositories import course_repository
```

Ajouter la dataclass et les fonctions, **avant** le bloc `if __name__ == "__main__":** :

```python
@dataclass
class RescrapeOutcome:
    """Bilan d'un rescrape-db."""
    total: int = 0
    imported: int = 0
    skipped: int = 0
    errors: int = 0
    dry_run_urls: list[str] = field(default_factory=list)


def run_rescrape_db(
    db,
    settings,
    *,
    dry_run: bool = False,
    older_than: int | None = None,
    provider: str | None = None,
    limit: int | None = None,
    delay: float = 1.0,
) -> RescrapeOutcome:
    """Re-scrape toutes les courses en DB avec force=True (bypass du cache TTL).

    Ne retient que les courses ayant une source_url (clé de re-scraping).
    En dry-run : liste les URLs sans scraper ni persister.
    """
    courses = course_repository.iter_all(
        db, provider=provider, older_than_days=older_than
    )
    courses = [c for c in courses if c.source_url]
    if limit is not None:
        courses = courses[:limit]

    outcome = RescrapeOutcome(
        total=len(courses),
        dry_run_urls=[c.source_url for c in courses],
    )
    if dry_run:
        return outcome

    for i, course in enumerate(courses):
        try:
            res = import_service.import_event(db, course.source_url, settings, force=True)
            outcome.imported += res.get("imported", 0)
            outcome.skipped += res.get("skipped", 0)
        except Exception as exc:
            outcome.errors += 1
            logger.warning("Échec rescrape %s : %s", course.source_url, exc)
        if delay and i < len(courses) - 1:
            time.sleep(delay)

    return outcome


def render_rescrape_report(outcome: RescrapeOutcome, *, dry_run: bool) -> str:
    """Rapport texte lisible pour rescrape-db."""
    lignes = []
    titre = "RESCRAPE DB (dry-run)" if dry_run else "RESCRAPE DB"
    lignes.append(f"=== {titre} ===")
    lignes.append(f"Courses ciblées : {outcome.total}")
    if dry_run:
        for url in outcome.dry_run_urls:
            lignes.append(f"  - {url}")
    else:
        lignes.append(f"Importées : {outcome.imported}")
        lignes.append(f"Ignorées  : {outcome.skipped}")
        lignes.append(f"En erreur : {outcome.errors}")
    return "\n".join(lignes)


@app.command("rescrape-db")
def rescrape_db(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Liste les courses sans scraper ni persister."
    ),
    older_than: int | None = typer.Option(
        None, "--older-than", help="Ne re-scrape que les courses plus vieilles que N jours."
    ),
    provider: str | None = typer.Option(
        None, "--provider", help="Restreint à un provider."
    ),
    limit: int | None = typer.Option(None, "--limit", help="Borne le nombre de courses."),
    delay: float = typer.Option(
        1.0, "--delay", help="Pause de politesse entre scrapes (s)."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Rapport machine-lisible en plus du texte."
    ),
) -> None:
    """Re-scrape tous les events en DB (force=True, bypass du cache TTL)."""
    settings = get_settings()
    with session_scope() as db:
        outcome = run_rescrape_db(
            db, settings,
            dry_run=dry_run, older_than=older_than, provider=provider,
            limit=limit, delay=delay,
        )
    typer.echo(render_rescrape_report(outcome, dry_run=dry_run))
    if json_output:
        typer.echo(json.dumps(asdict(outcome), ensure_ascii=False))
```

- [ ] **Step 4 : Lancer les tests pour vérifier qu'ils passent**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: PASS (tous les tests CLI)

- [ ] **Step 5 : Vérifier `--help`**

Run: `.venv/bin/python -m app.cli rescrape-db --help`
Expected: affiche l'aide avec `--dry-run`, `--older-than`, `--provider`, `--limit`, `--delay`, `--json`.

- [ ] **Step 6 : Lint + commit**

```bash
.venv/bin/ruff check app/cli.py tests/test_cli.py
git add app/cli.py tests/test_cli.py
git commit -m "feat(cli): commande rescrape-db (force=True, bypass cache TTL)"
```

---

### Task 7 : Vérification finale (acceptance)

Vérifie l'ensemble des critères d'acceptation de la spec sur la suite complète.

**Files:** aucun (vérification).

- [ ] **Step 1 : Suite de tests unitaires complète (sans réseau)**

Run: `.venv/bin/python -m pytest -m "not integration"`
Expected: PASS — l'intégralité de la suite verte (≈130 tests existants + nouveaux).

- [ ] **Step 2 : Lint global**

Run: `.venv/bin/ruff check .`
Expected: `All checks passed!`

- [ ] **Step 3 : Smoke `--dry-run` sur base de dev**

Prérequis : `backend/.env` avec `DATABASE_URL` SQLite (voir `.env.example`) et base migrée (`alembic upgrade head`).

Run: `.venv/bin/python -m app.cli rescrape-db --dry-run`
Expected: affiche `=== RESCRAPE DB (dry-run) ===` + le nombre de courses ciblées (0 si base vide), **sans** aucun scrape ni écriture.

- [ ] **Step 4 : Vérifier le point d'entrée module**

Run: `.venv/bin/python -m app.cli --help`
Expected: liste les deux commandes `import-sheet` et `rescrape-db`.

- [ ] **Step 5 : Commit final si nécessaire**

Si des ajustements ont été faits :

```bash
git add -A
git commit -m "chore(cli): vérification finale des critères d'acceptation"
```

---

## Self-Review

**1. Couverture de la spec :**

| Critère d'acceptation (spec) | Tâche(s) |
| --- | --- |
| Module CLI Typer, 2 commandes, invocable depuis `backend/` | 4, 5, 6 (+ 7 smoke) |
| `import-sheet` lit CSV public, dédoublonne, importe supportés, rapport non supportés / sans lien | 4 (parse/dedup), 5 (orchestration + rapport) |
| `rescrape-db` re-scrape tous les events avec bypass effectif du cache (flag `force`) | 1 (force), 3 (iter_all), 6 (orchestration) |
| `--dry-run` sur les deux commandes (aucune écriture, aucun scrape) | 5, 6 (tests dédiés) |
| Un échec unitaire n'interrompt pas le batch ; bilan correct | 5, 6 (tests dédiés) |
| Tests unitaires sans réseau (parsing CSV, dédup, orchestration) | 4, 5, 6 |
| `typer` déclaré dans `requirements.txt` | 4 |
| `ruff check .` propre | 7 (+ étape lint par tâche) |
| Changement chirurgical : `session_scope()` | 2 |

Options spec couvertes : `--dry-run`, `--limit`, `--only-provider`/`--provider`, `--sheet-url`, `--delay`, `--json`, `--older-than` — toutes présentes dans les commandes Task 5/6.

**2. Placeholders :** aucun TODO/TBD ; chaque étape de code contient le code complet.

**3. Cohérence des types :** `import_event(..., force=False)` (Task 1) consommé identiquement en Task 5 (`force=False`) et Task 6 (`force=True`). `iter_all(db, *, provider=None, older_than_days=None)` (Task 3) — Task 6 mappe l'option `--older-than` sur le paramètre `older_than_days` via `older_than`. `SheetOutcome`/`RescrapeOutcome` sont des dataclasses sérialisables par `asdict()` pour `--json`. `registry.detect_provider` et `import_service.import_event` sont référencés via leur module (attribut) → monkeypatch effectif dans les tests.

**Note d'exécution** : le repo a un venv en `backend/.venv`. Les commandes du plan utilisent `.venv/bin/python` / `.venv/bin/ruff` depuis `backend/`. Adapter si le venv est activé autrement.
