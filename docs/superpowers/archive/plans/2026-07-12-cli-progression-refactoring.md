# CLI : progression en direct & découpage en services — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Afficher la progression en direct des commandes `import-sheet` / `rescrape-db`, et éclater `app/cli.py` (323 lignes, 4 responsabilités) en services testables + une couche CLI mince.

**Architecture:** Les orchestrations batch descendent dans `app/services/` et consomment `import_service.iter_import_event()` (le générateur de phases déjà utilisé par le SSE du front) au lieu de la variante muette `import_event()`. Elles notifient un `ProgressReporter` (Protocol, `services/progress.py`) dont le défaut `NullReporter` est muet. La couche `app/cli/` ne garde que Typer, les implémentations Rich/Plain du reporter, et le rendu des rapports.

**Tech Stack:** Python 3.11+, Typer 0.26.7, Rich 15 (déjà installé, dépendance dure de Typer), pytest, SQLAlchemy 2.0.

## Global Constraints

- **Langue** : code, commentaires, docstrings et sorties utilisateur en **français avec accents**.
- **Commits** : Conventional Commits (`feat:`, `refactor:`, `test:`…).
- **Aucune nouvelle dépendance** : `rich>=13.8.0` est déjà tiré par `typer==0.26.7`. On l'ajoute seulement en explicite dans `requirements.txt` (Task 6) puisqu'on l'importe directement.
- **Tests sans réseau** : tout scrape est monkeypatché. `pytest -m "not integration"` doit rester vert à chaque commit.
- **La progression sort sur `stderr`**, jamais `stdout` — sinon elle corrompt la sortie `--json`. Le choix TTY se fait donc sur `sys.stderr.isatty()`.
- **`app/cli.py` reste fonctionnel jusqu'à la Task 7** : chaque task qui extrait du code le remplace par un ré-export dans `cli.py`, pour que `tests/test_cli.py` reste vert entre-temps.
- Lancer les commandes depuis `backend/`, venv activé.

---

### Task 1 : Le contrat de progression

**Files:**
- Create: `backend/app/services/progress.py`
- Test: `backend/tests/test_services/test_progress.py`

**Interfaces:**
- Consumes: rien.
- Produces: `ProgressReporter` (Protocol, `@runtime_checkable`) avec les 5 méthodes `batch_start(total: int)`, `item_start(index: int, label: str)`, `item_progress(done: int, total: int)`, `item_done(imported: int, skipped: int, error: str | None)`, `batch_end()`. Et `NullReporter` (implémentation muette, défaut de tous les services).

- [ ] **Step 1 : Écrire le test qui échoue**

Créer `backend/tests/test_services/test_progress.py` :

```python
from app.services.progress import NullReporter, ProgressReporter


def test_null_reporter_respecte_le_protocol():
    assert isinstance(NullReporter(), ProgressReporter)


def test_null_reporter_est_muet_et_ne_leve_rien(capsys):
    reporter = NullReporter()
    reporter.batch_start(2)
    reporter.item_start(0, "klikego · https://k/1")
    reporter.item_progress(10, 100)
    reporter.item_done(10, 0, None)
    reporter.batch_end()

    capture = capsys.readouterr()
    assert capture.out == ""
    assert capture.err == ""
```

- [ ] **Step 2 : Lancer le test pour le voir échouer**

Run: `pytest tests/test_services/test_progress.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.progress'`

- [ ] **Step 3 : Écrire l'implémentation minimale**

Créer `backend/app/services/progress.py` :

```python
"""Contrat de progression des batches d'import.

Les services d'orchestration notifient un reporter au fil de l'eau sans rien
connaître de Typer ni de Rich (inversion de dépendance, comme le registre
Protocol des scrapers). Le défaut `NullReporter` les garde muets et testables
sans terminal ; la couche CLI branche ses propres implémentations.
"""
from typing import Protocol, runtime_checkable


@runtime_checkable
class ProgressReporter(Protocol):
    """Reçoit la progression d'un batch : le batch, puis chaque épreuve."""

    def batch_start(self, total: int) -> None:
        """Le batch démarre avec `total` épreuves à traiter."""
        ...

    def item_start(self, index: int, label: str) -> None:
        """L'épreuve n° `index` (0-based) démarre, identifiée par `label`."""
        ...

    def item_progress(self, done: int, total: int) -> None:
        """Progression *dans* l'épreuve courante : `done`/`total` participants."""
        ...

    def item_done(self, imported: int, skipped: int, error: str | None) -> None:
        """L'épreuve courante est terminée — ou en échec si `error` est renseigné."""
        ...

    def batch_end(self) -> None:
        """Le batch est terminé (y compris s'il a été interrompu)."""
        ...


class NullReporter:
    """Ne rapporte rien. Défaut de tous les services."""

    def batch_start(self, total: int) -> None:
        pass

    def item_start(self, index: int, label: str) -> None:
        pass

    def item_progress(self, done: int, total: int) -> None:
        pass

    def item_done(self, imported: int, skipped: int, error: str | None) -> None:
        pass

    def batch_end(self) -> None:
        pass
```

- [ ] **Step 4 : Lancer le test pour le voir passer**

Run: `pytest tests/test_services/test_progress.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5 : Commit**

```bash
git add backend/app/services/progress.py backend/tests/test_services/test_progress.py
git commit -m "feat(services): Protocol ProgressReporter + NullReporter"
```

---

### Task 2 : Extraire la source Google Sheet

Déplace le parsing/normalisation hors de `cli.py`. `cli.py` ré-exporte pour rester vert.

**Files:**
- Create: `backend/app/services/sheet_source.py`
- Modify: `backend/app/cli.py` (supprimer les helpers, ré-exporter depuis le service)
- Create: `backend/tests/test_services/test_sheet_source.py`
- Modify: `backend/tests/test_cli.py` (retirer les 6 tests migrés)

**Interfaces:**
- Consumes: `app.scrapers.registry.detect_provider`.
- Produces: `normalize_url(url: str) -> str`, `dedupe_links(links: list[str]) -> list[str]`, `parse_sheet_csv(csv_text: str) -> tuple[list[str], int]`, `is_supported(url: str) -> bool`, `host_of(url: str) -> str`, `download_csv(url: str) -> str`, et les constantes `DEFAULT_SHEET_URL`, `LINK_HEADER`, `LINK_COLUMN_FALLBACK_INDEX`.

- [ ] **Step 1 : Écrire le test qui échoue**

Créer `backend/tests/test_services/test_sheet_source.py` — ce sont les 6 tests existants de `tests/test_cli.py`, inchangés hormis le module ciblé :

```python
from app.services import sheet_source


def test_normalize_url_trim_casse_slash_fragment():
    variantes = [
        "  https://WWW.Klikego.COM/resultats/event/1/#top  ",
        "https://www.klikego.com/resultats/event/1",
    ]
    assert sheet_source.normalize_url(variantes[0]) == sheet_source.normalize_url(variantes[1])


def test_normalize_url_conserve_la_query():
    a = sheet_source.normalize_url("https://www.klikego.com/e?heat=42")
    b = sheet_source.normalize_url("https://www.klikego.com/e?heat=7")
    assert a != b  # la query distingue deux heats


def test_dedupe_collapse_les_variantes_normalisees():
    links = [
        "https://www.klikego.com/resultats/event/1",
        "https://www.klikego.com/resultats/event/1/",    # slash final
        "https://WWW.KLIKEGO.COM/resultats/event/1",      # casse host
        "https://www.klikego.com/resultats/event/1#top",  # fragment
        "https://www.klikego.com/resultats/event/2",
    ]
    assert sheet_source.dedupe_links(links) == [
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
    links, sans_lien = sheet_source.parse_sheet_csv(csv_text)
    assert links == ["https://www.klikego.com/resultats/event/1"]
    assert sans_lien == 1


def test_parse_sheet_csv_repli_sur_index_9_si_en_tete_absent():
    header = ",".join(f"c{i}" for i in range(10))
    row = ",".join(["x"] * 9 + ["https://www.timepulse.fr/e/1"])
    links, _ = sheet_source.parse_sheet_csv(f"{header}\n{row}\n")
    assert links == ["https://www.timepulse.fr/e/1"]


def test_is_supported_playwright_est_faux(monkeypatch):
    from app.scrapers import registry

    monkeypatch.setattr(registry, "detect_provider", lambda url: "playwright")
    assert sheet_source.is_supported("http://x") is False

    monkeypatch.setattr(registry, "detect_provider", lambda url: "klikego")
    assert sheet_source.is_supported("http://x") is True


def test_host_of_minuscule_et_repli():
    assert sheet_source.host_of("https://WWW.Example.COM/a") == "www.example.com"
    assert sheet_source.host_of("pas-une-url") == "(inconnu)"
```

- [ ] **Step 2 : Lancer le test pour le voir échouer**

Run: `pytest tests/test_services/test_sheet_source.py -v`
Expected: FAIL — `ImportError: cannot import name 'sheet_source' from 'app.services'`

- [ ] **Step 3 : Écrire l'implémentation**

Créer `backend/app/services/sheet_source.py` :

```python
"""Source Google Sheet : téléchargement du CSV, extraction et normalisation des liens.

Aucun accès DB, aucun scraping — juste la lecture de la source d'entrée de
l'import de masse.
"""
import csv
import io
from urllib.parse import urlparse, urlunparse

import httpx

from app.scrapers import registry

DEFAULT_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1rtiVRFOQUGcaWCTDPTR4xA9UL22UsWosKjsYMcRMsew/export?format=csv&gid=1961918487"
)
LINK_HEADER = "Donne-nous un lien pour accéder aux résultats."
LINK_COLUMN_FALLBACK_INDEX = 9  # 10e colonne, repli si l'en-tête n'est pas trouvé


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


def host_of(url: str) -> str:
    """Host en minuscule, pour grouper les liens ignorés dans le rapport."""
    return (urlparse(url).netloc or "").lower() or "(inconnu)"


def download_csv(url: str) -> str:
    """Télécharge le CSV public du Sheet (httpx, sans auth)."""
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text
```

- [ ] **Step 4 : Faire de `cli.py` un ré-export (il reste vert)**

Dans `backend/app/cli.py`, supprimer les définitions de `normalize_url`, `dedupe_links`, `parse_sheet_csv`, `is_supported`, `_host`, `_download_csv` et les constantes `DEFAULT_SHEET_URL` / `LINK_HEADER` / `LINK_COLUMN_FALLBACK_INDEX`, ainsi que les imports devenus inutiles (`csv`, `io`, `httpx`, `urlparse`, `urlunparse`, `registry`). Les remplacer par :

```python
from app.services.sheet_source import (  # noqa: F401 — ré-export transitoire (Task 7)
    DEFAULT_SHEET_URL,
    dedupe_links,
    download_csv,
    host_of,
    is_supported,
    normalize_url,
    parse_sheet_csv,
)
```

Puis, dans le corps de `cli.py`, remplacer les deux usages restants :
- dans `run_import_sheet` : `host = _host(url)` → `host = host_of(url)`
- dans `import_sheet` : `csv_text = _download_csv(sheet_url)` → `csv_text = download_csv(sheet_url)`

- [ ] **Step 5 : Retirer de `tests/test_cli.py` les 6 tests migrés**

Supprimer de `backend/tests/test_cli.py` : `test_normalize_url_trim_casse_slash_fragment`, `test_normalize_url_conserve_la_query`, `test_dedupe_collapse_les_variantes_normalisees`, `test_parse_sheet_csv_extrait_la_colonne_par_en_tete`, `test_parse_sheet_csv_repli_sur_index_9_si_en_tete_absent`, `test_is_supported_playwright_est_faux`. Garder les 8 tests d'orchestration (ils partiront en Tasks 4 et 5).

- [ ] **Step 6 : Lancer toute la suite**

Run: `pytest -m "not integration" -q && ruff check .`
Expected: PASS — les 6 tests migrés passent depuis leur nouvelle adresse, les 8 tests d'orchestration de `test_cli.py` restent verts grâce au ré-export.

- [ ] **Step 7 : Commit**

```bash
git add backend/app/services/sheet_source.py backend/app/cli.py \
        backend/tests/test_services/test_sheet_source.py backend/tests/test_cli.py
git commit -m "refactor(services): extraire sheet_source de cli.py"
```

---

### Task 3 : La boucle de batch (cœur du changement)

C'est ici que la progression apparaît réellement : la boucle consomme `iter_import_event()` et relaie chaque phase au reporter. Les deux commandes partageaient une boucle identique à l'item près — on la factorise une fois.

**Files:**
- Create: `backend/app/services/batch.py`
- Test: `backend/tests/test_services/test_batch.py`

**Interfaces:**
- Consumes: `import_service.iter_import_event(db, url, settings, force) -> Iterator[dict]` (phases `scraping` / `saving` avec `progress`+`total` / `done` avec `imported`+`skipped` / `error` avec `message`) ; `services.progress.NullReporter`, `ProgressReporter`.
- Produces:
  - `BatchItem(url: str, label: str)` — dataclass frozen.
  - `BatchTotals(imported: int = 0, skipped: int = 0, errors: int = 0, interrupted: bool = False)` — dataclass mutable.
  - `run_batch(db, items: list[BatchItem], settings, *, force: bool, delay: float = 1.0, reporter: ProgressReporter | None = None) -> BatchTotals`.

- [ ] **Step 1 : Écrire la sonde partagée**

Créer `backend/tests/test_services/conftest.py` — `FakeReporter` sert aux Tasks 3, 4 et 5 ; il vit donc dans un conftest plutôt que d'être importé d'un module de test à l'autre :

```python
import pytest


class FakeReporter:
    """Sonde de progression : enregistre les appels reçus, dans l'ordre."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def batch_start(self, total: int) -> None:
        self.calls.append(("batch_start", total))

    def item_start(self, index: int, label: str) -> None:
        self.calls.append(("item_start", index, label))

    def item_progress(self, done: int, total: int) -> None:
        self.calls.append(("item_progress", done, total))

    def item_done(self, imported: int, skipped: int, error: str | None) -> None:
        self.calls.append(("item_done", imported, skipped, error))

    def batch_end(self) -> None:
        self.calls.append(("batch_end",))


@pytest.fixture
def fake_reporter() -> FakeReporter:
    return FakeReporter()
```

- [ ] **Step 2 : Écrire les tests qui échouent**

Créer `backend/tests/test_services/test_batch.py` :

```python
from app.core.config import Settings
from app.services import batch, import_service
from app.services.batch import BatchItem


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def _phases_ok(db, url, settings, force=False):
    """Simule iter_import_event pour une épreuve de 30 participants."""
    yield {"phase": "scraping", "message": "Récupération des participants…"}
    yield {"phase": "saving", "total": 30, "imported": 0, "skipped": 0, "progress": 0}
    yield {"phase": "saving", "total": 30, "imported": 20, "skipped": 0, "progress": 20}
    yield {"phase": "saving", "total": 30, "imported": 28, "skipped": 2, "progress": 30}
    yield {"phase": "done", "imported": 28, "skipped": 2, "total": 30}


def test_run_batch_relaie_la_progression_intra_epreuve(db_session, monkeypatch, fake_reporter):
    monkeypatch.setattr(import_service, "iter_import_event", _phases_ok)

    totals = batch.run_batch(
        db_session, [BatchItem(url="https://k/1", label="klikego · A")], _settings(),
        force=False, delay=0.0, reporter=fake_reporter,
    )

    assert totals.imported == 28
    assert totals.skipped == 2
    assert totals.errors == 0
    assert fake_reporter.calls == [
        ("batch_start", 1),
        ("item_start", 0, "klikego · A"),
        ("item_progress", 0, 30),
        ("item_progress", 20, 30),
        ("item_progress", 30, 30),
        ("item_done", 28, 2, None),
        ("batch_end",),
    ]


def test_run_batch_phase_error_compte_une_erreur_sans_interrompre(
    db_session, monkeypatch, fake_reporter
):
    def _phases(db, url, settings, force=False):
        if "boom" in url:
            yield {"phase": "error", "message": "timeout scrape"}
            return
        yield from _phases_ok(db, url, settings, force)

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    totals = batch.run_batch(
        db_session,
        [BatchItem(url="https://k/boom", label="A"), BatchItem(url="https://k/ok", label="B")],
        _settings(), force=False, delay=0.0, reporter=fake_reporter,
    )

    assert totals.errors == 1
    assert totals.imported == 28  # la 2e épreuve a bien été traitée
    assert ("item_done", 0, 0, "timeout scrape") in fake_reporter.calls


def test_run_batch_une_exception_reelle_compte_aussi_une_erreur(db_session, monkeypatch):
    def _phases(db, url, settings, force=False):
        raise RuntimeError("bug inattendu")
        yield  # pragma: no cover — fait de _phases un générateur

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    totals = batch.run_batch(
        db_session, [BatchItem(url="https://k/1", label="A")], _settings(),
        force=False, delay=0.0,
    )

    assert totals.errors == 1
    assert totals.imported == 0


def test_run_batch_ctrl_c_conserve_le_travail_deja_fait(db_session, monkeypatch, fake_reporter):
    def _phases(db, url, settings, force=False):
        if "stop" in url:
            raise KeyboardInterrupt
        yield from _phases_ok(db, url, settings, force)

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    totals = batch.run_batch(
        db_session,
        [BatchItem(url="https://k/ok", label="A"), BatchItem(url="https://k/stop", label="B"),
         BatchItem(url="https://k/jamais", label="C")],
        _settings(), force=False, delay=0.0, reporter=fake_reporter,
    )

    assert totals.interrupted is True
    assert totals.imported == 28   # la 1re épreuve est conservée
    assert totals.errors == 0      # une interruption n'est pas une erreur
    assert ("item_start", 2, "C") not in fake_reporter.calls  # la 3e n'a pas démarré
    assert fake_reporter.calls[-1] == ("batch_end",)          # les barres sont bien fermées


def test_run_batch_transmet_force_au_generateur(db_session, monkeypatch):
    vus: list[bool] = []

    def _phases(db, url, settings, force=False):
        vus.append(force)
        yield {"phase": "done", "imported": 1, "skipped": 0, "total": 1}

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    batch.run_batch(
        db_session, [BatchItem(url="https://k/1", label="A")], _settings(),
        force=True, delay=0.0,
    )

    assert vus == [True]


def test_run_batch_sans_reporter_ne_leve_pas(db_session, monkeypatch):
    monkeypatch.setattr(import_service, "iter_import_event", _phases_ok)

    totals = batch.run_batch(
        db_session, [BatchItem(url="https://k/1", label="A")], _settings(),
        force=False, delay=0.0,
    )

    assert totals.imported == 28  # NullReporter par défaut
```

- [ ] **Step 3 : Lancer les tests pour les voir échouer**

Run: `pytest tests/test_services/test_batch.py -v`
Expected: FAIL — `ImportError: cannot import name 'batch' from 'app.services'`

- [ ] **Step 4 : Écrire l'implémentation**

Créer `backend/app/services/batch.py` :

```python
"""Boucle de batch commune à l'import de masse et au rescrape.

Consomme `import_service.iter_import_event()` — le même générateur de phases que
le SSE du frontend — et relaie la progression à un `ProgressReporter`. Une
épreuve en échec n'interrompt pas le batch ; un Ctrl-C l'arrête proprement en
conservant le travail déjà persisté (chaque épreuve est commitée séparément).
"""
import logging
import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services import import_service
from app.services.progress import NullReporter, ProgressReporter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BatchItem:
    """Une épreuve à traiter : l'URL à scraper, et son libellé d'affichage."""
    url: str
    label: str


@dataclass
class BatchTotals:
    """Compteurs cumulés d'un batch. `interrupted` = arrêté par Ctrl-C."""
    imported: int = 0
    skipped: int = 0
    errors: int = 0
    interrupted: bool = False


def _import_one(
    db: Session,
    url: str,
    settings: Settings,
    *,
    force: bool,
    reporter: ProgressReporter,
) -> tuple[int, int, str | None]:
    """Consomme les phases d'une épreuve. Renvoie (imported, skipped, error).

    `iter_import_event` *yield* une phase `error` au lieu de lever : c'est cette
    phase qui porte l'échec, pas une exception.
    """
    imported = skipped = 0
    error: str | None = None

    for phase in import_service.iter_import_event(db, url, settings, force=force):
        nom = phase.get("phase")
        if nom == "saving":
            reporter.item_progress(phase.get("progress", 0), phase.get("total", 0))
        elif nom == "done":
            imported = phase.get("imported", 0)
            skipped = phase.get("skipped", 0)
        elif nom == "error":
            error = phase.get("message", "erreur inconnue")

    return imported, skipped, error


def run_batch(
    db: Session,
    items: list[BatchItem],
    settings: Settings,
    *,
    force: bool,
    delay: float = 1.0,
    reporter: ProgressReporter | None = None,
) -> BatchTotals:
    """Importe chaque épreuve en séquence, en rapportant la progression.

    `delay` est une pause de politesse entre deux scrapes (pas après le dernier).
    """
    reporter = reporter or NullReporter()
    totals = BatchTotals()

    reporter.batch_start(len(items))
    try:
        for i, item in enumerate(items):
            reporter.item_start(i, item.label)
            try:
                imported, skipped, error = _import_one(
                    db, item.url, settings, force=force, reporter=reporter
                )
            except Exception as exc:  # filet : un bug ne doit pas tuer le batch
                logger.warning("Échec import %s : %s", item.url, exc)
                imported = skipped = 0
                error = str(exc)

            if error:
                totals.errors += 1
            else:
                totals.imported += imported
                totals.skipped += skipped
            reporter.item_done(imported, skipped, error)

            if delay and i < len(items) - 1:
                time.sleep(delay)
    except KeyboardInterrupt:
        # Ctrl-C : on ne perd pas le bilan de ce qui est déjà en base.
        totals.interrupted = True
        logger.warning("Interruption clavier — arrêt du batch")
    finally:
        reporter.batch_end()

    return totals
```

Note : `KeyboardInterrupt` hérite de `BaseException`, donc le `except Exception` interne ne l'attrape pas — il remonte bien au `except KeyboardInterrupt` de la boucle.

- [ ] **Step 5 : Lancer les tests pour les voir passer**

Run: `pytest tests/test_services/test_batch.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6 : Commit**

```bash
git add backend/app/services/batch.py backend/tests/test_services/conftest.py \
        backend/tests/test_services/test_batch.py
git commit -m "feat(services): run_batch consomme iter_import_event et relaie la progression"
```

---

### Task 4 : Le service d'import de masse

**Files:**
- Create: `backend/app/services/bulk_import_service.py`
- Modify: `backend/app/cli.py` (déléguer au service)
- Create: `backend/tests/test_services/test_bulk_import_service.py`
- Modify: `backend/tests/test_cli.py` (retirer les 4 tests migrés)

**Interfaces:**
- Consumes: `sheet_source.{parse_sheet_csv, dedupe_links, is_supported, host_of}`, `registry.detect_provider`, `batch.{BatchItem, run_batch}`, `progress.ProgressReporter`.
- Produces:
  - `SheetOutcome(imported=0, skipped=0, errors=0, rows_without_link=0, unique_supported=0, ignored_by_host: dict[str, int], interrupted=False)`.
  - `run_import_sheet(db, csv_text: str, settings, *, dry_run=False, limit: int | None = None, only_provider: str | None = None, delay: float = 1.0, reporter: ProgressReporter | None = None) -> SheetOutcome`.

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer `backend/tests/test_services/test_bulk_import_service.py`. Les 4 tests d'orchestration existants sont **réécrits** : ils monkeypatchaient `import_event`, ils simulent désormais le générateur `iter_import_event`. Deux tests nouveaux couvrent le reporter et le Ctrl-C.

```python
from app.core.config import Settings
from app.services import bulk_import_service, import_service


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def _phases(imported: int = 2, skipped: int = 1):
    """Fabrique un faux iter_import_event qui journalise les URLs vues."""
    vus: list[tuple[str, bool]] = []

    def _iter(db, url, settings, force=False):
        vus.append((url, force))
        yield {"phase": "saving", "total": 3, "imported": 0, "skipped": 0, "progress": 0}
        yield {"phase": "done", "imported": imported, "skipped": skipped, "total": 3}

    return _iter, vus


def test_run_import_sheet_compteurs_et_rapport(db_session, monkeypatch):
    from app.scrapers import registry

    monkeypatch.setattr(
        registry, "detect_provider",
        lambda url: "klikego" if "klikego" in url else "playwright",
    )
    _iter, vus = _phases(imported=2, skipped=1)
    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    csv_text = (
        "a,Donne-nous un lien pour accéder aux résultats.\n"
        "x,https://www.klikego.com/e/1\n"
        "x,https://www.klikego.com/e/1/\n"        # doublon du précédent
        "x,https://inconnu.example/e/2\n"          # non supporté
        "x,\n"                                      # sans lien
    )
    out = bulk_import_service.run_import_sheet(db_session, csv_text, _settings(), delay=0.0)

    assert out.imported == 2
    assert out.skipped == 1
    assert out.errors == 0
    assert out.rows_without_link == 1
    assert out.ignored_by_host == {"inconnu.example": 1}
    assert out.unique_supported == 1
    # 1 seul lien supporté unique, importé avec force=False
    assert vus == [("https://www.klikego.com/e/1", False)]


def test_run_import_sheet_un_echec_n_interrompt_pas_le_batch(db_session, monkeypatch):
    from app.scrapers import registry

    monkeypatch.setattr(registry, "detect_provider", lambda url: "klikego")

    def _iter(db, url, settings, force=False):
        if "boom" in url:
            yield {"phase": "error", "message": "échec scrape"}
            return
        yield {"phase": "done", "imported": 1, "skipped": 0, "total": 1}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    csv_text = (
        "a,Donne-nous un lien pour accéder aux résultats.\n"
        "x,https://www.klikego.com/boom\n"
        "x,https://www.klikego.com/ok\n"
    )
    out = bulk_import_service.run_import_sheet(db_session, csv_text, _settings(), delay=0.0)
    assert out.errors == 1
    assert out.imported == 1


def test_run_import_sheet_dry_run_ne_scrape_pas(db_session, monkeypatch):
    from app.scrapers import registry

    monkeypatch.setattr(registry, "detect_provider", lambda url: "klikego")
    _iter, vus = _phases()
    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    csv_text = (
        "a,Donne-nous un lien pour accéder aux résultats.\n"
        "x,https://www.klikego.com/e/1\n"
    )
    out = bulk_import_service.run_import_sheet(
        db_session, csv_text, _settings(), dry_run=True, delay=0.0
    )
    assert vus == []
    assert out.unique_supported == 1


def test_run_import_sheet_only_provider_restreint(db_session, monkeypatch):
    from app.scrapers import registry

    monkeypatch.setattr(
        registry, "detect_provider",
        lambda url: "klikego" if "klikego" in url else "timepulse",
    )
    _iter, vus = _phases(imported=1, skipped=0)
    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    csv_text = (
        "a,Donne-nous un lien pour accéder aux résultats.\n"
        "x,https://www.klikego.com/e/1\n"
        "x,https://www.timepulse.fr/e/2\n"
    )
    out = bulk_import_service.run_import_sheet(
        db_session, csv_text, _settings(), only_provider="klikego", delay=0.0
    )
    assert [url for url, _ in vus] == ["https://www.klikego.com/e/1"]
    assert out.imported == 1


def test_run_import_sheet_libelle_provider_et_url(db_session, monkeypatch, fake_reporter):
    """Le label part du provider + l'URL : le nom de course n'est pas connu avant le scrape."""
    from app.scrapers import registry

    monkeypatch.setattr(registry, "detect_provider", lambda url: "klikego")
    _iter, _ = _phases()
    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    csv_text = (
        "a,Donne-nous un lien pour accéder aux résultats.\n"
        "x,https://www.klikego.com/e/1\n"
    )
    bulk_import_service.run_import_sheet(
        db_session, csv_text, _settings(), delay=0.0, reporter=fake_reporter
    )

    assert ("item_start", 0, "klikego · https://www.klikego.com/e/1") in fake_reporter.calls


def test_run_import_sheet_dry_run_ne_rapporte_aucune_progression(
    db_session, monkeypatch, fake_reporter
):
    from app.scrapers import registry

    monkeypatch.setattr(registry, "detect_provider", lambda url: "klikego")

    csv_text = (
        "a,Donne-nous un lien pour accéder aux résultats.\n"
        "x,https://www.klikego.com/e/1\n"
    )
    bulk_import_service.run_import_sheet(
        db_session, csv_text, _settings(), dry_run=True, delay=0.0, reporter=fake_reporter
    )

    assert fake_reporter.calls == []


def test_run_import_sheet_ctrl_c_remonte_le_drapeau(db_session, monkeypatch):
    from app.scrapers import registry

    monkeypatch.setattr(registry, "detect_provider", lambda url: "klikego")

    def _iter(db, url, settings, force=False):
        raise KeyboardInterrupt
        yield  # pragma: no cover — fait de _iter un générateur

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    csv_text = (
        "a,Donne-nous un lien pour accéder aux résultats.\n"
        "x,https://www.klikego.com/e/1\n"
    )
    out = bulk_import_service.run_import_sheet(db_session, csv_text, _settings(), delay=0.0)

    assert out.interrupted is True
```

- [ ] **Step 2 : Lancer les tests pour les voir échouer**

Run: `pytest tests/test_services/test_bulk_import_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'bulk_import_service' from 'app.services'`

- [ ] **Step 3 : Écrire l'implémentation**

Créer `backend/app/services/bulk_import_service.py` :

```python
"""Import de masse depuis le Google Sheet des adhérents.

Sélectionne les liens supportés de la source, puis délègue la boucle à
`batch.run_batch`. Les liens non supportés vont au rapport, jamais aux erreurs.
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.scrapers import registry
from app.services import sheet_source
from app.services.batch import BatchItem, run_batch
from app.services.progress import ProgressReporter


@dataclass
class SheetOutcome:
    """Bilan d'un import-sheet."""
    imported: int = 0
    skipped: int = 0
    errors: int = 0
    rows_without_link: int = 0
    unique_supported: int = 0
    ignored_by_host: dict[str, int] = field(default_factory=dict)
    interrupted: bool = False


def run_import_sheet(
    db: Session,
    csv_text: str,
    settings: Settings,
    *,
    dry_run: bool = False,
    limit: int | None = None,
    only_provider: str | None = None,
    delay: float = 1.0,
    reporter: ProgressReporter | None = None,
) -> SheetOutcome:
    """Détecte, dédoublonne et importe les liens supportés du CSV du Sheet.

    En dry-run : ne scrape rien, ne persiste rien, ne temporise pas, ne rapporte
    aucune progression.
    """
    links, rows_without_link = sheet_source.parse_sheet_csv(csv_text)
    unique = sheet_source.dedupe_links(links)

    supported: list[str] = []
    ignored_by_host: dict[str, int] = {}
    for url in unique:
        if sheet_source.is_supported(url):
            if only_provider and registry.detect_provider(url) != only_provider:
                continue
            supported.append(url)
        else:
            host = sheet_source.host_of(url)
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

    # Le nom de la course n'est connu qu'après le scrape : on libelle par l'URL.
    items = [
        BatchItem(url=url, label=f"{registry.detect_provider(url)} · {url}")
        for url in supported
    ]
    totals = run_batch(
        db, items, settings, force=False, delay=delay, reporter=reporter
    )

    outcome.imported = totals.imported
    outcome.skipped = totals.skipped
    outcome.errors = totals.errors
    outcome.interrupted = totals.interrupted
    return outcome
```

- [ ] **Step 4 : Faire déléguer `cli.py` (il reste vert)**

Dans `backend/app/cli.py` : supprimer la dataclass `SheetOutcome` et la fonction `run_import_sheet`, ainsi que les imports devenus inutiles (`time`, `logging`, `import_service`, `logger`). Ajouter au ré-export :

```python
from app.services.bulk_import_service import (  # noqa: F401 — ré-export transitoire (Task 7)
    SheetOutcome,
    run_import_sheet,
)
```

`render_sheet_report` et la commande Typer `import_sheet` restent en place pour l'instant.

- [ ] **Step 5 : Retirer de `tests/test_cli.py` les 4 tests migrés**

Supprimer `test_run_import_sheet_compteurs_et_rapport`, `test_run_import_sheet_un_echec_n_interrompt_pas_le_batch`, `test_run_import_sheet_dry_run_ne_scrape_pas`, `test_run_import_sheet_only_provider_restreint`. Il reste les 4 tests de rescrape.

- [ ] **Step 6 : Lancer toute la suite**

Run: `pytest -m "not integration" -q && ruff check .`
Expected: PASS

- [ ] **Step 7 : Commit**

```bash
git add backend/app/services/bulk_import_service.py backend/app/cli.py \
        backend/tests/test_services/test_bulk_import_service.py backend/tests/test_cli.py
git commit -m "refactor(services): bulk_import_service avec progression"
```

---

### Task 5 : Le service de rescrape

**Files:**
- Create: `backend/app/services/rescrape_service.py`
- Modify: `backend/app/cli.py` (déléguer au service)
- Create: `backend/tests/test_services/test_rescrape_service.py`
- Delete: `backend/tests/test_cli.py` (les 4 derniers tests migrent ici)

**Interfaces:**
- Consumes: `course_repository.iter_all(db, *, provider=None, older_than_days=None) -> list[Course]` (les `Course` portent `source_url`, `name`, `provider`), `batch.{BatchItem, run_batch}`.
- Produces:
  - `RescrapeOutcome(total=0, imported=0, skipped=0, errors=0, dry_run_urls: list[str], interrupted=False)`.
  - `run_rescrape_db(db, settings, *, dry_run=False, older_than: int | None = None, provider: str | None = None, limit: int | None = None, delay: float = 1.0, reporter: ProgressReporter | None = None) -> RescrapeOutcome`.

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer `backend/tests/test_services/test_rescrape_service.py` — les 4 tests existants réécrits pour le générateur, plus un test de libellé (ici le nom vient de la DB) :

```python
from datetime import date

from app.core.config import Settings
from app.repositories import course_repository
from app.services import import_service, rescrape_service


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def _course(db, nom: str, url: str, jour: int = 1) -> None:
    course_repository.get_or_create(
        db, name=nom, event_date=date(2026, 1, jour),
        event_type="triathlon-m", source_url=url, provider="klikego",
    )
    db.flush()


def test_run_rescrape_force_et_compte(db_session, monkeypatch):
    _course(db_session, "A", "https://k/1")
    vus: list[tuple[str, bool]] = []

    def _iter(db, url, settings, force=False):
        vus.append((url, force))
        yield {"phase": "done", "imported": 3, "skipped": 0, "total": 3}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    out = rescrape_service.run_rescrape_db(db_session, _settings(), delay=0.0)
    assert out.total == 1
    assert out.imported == 3
    assert out.errors == 0
    # force=True : c'est le cœur de la commande
    assert vus == [("https://k/1", True)]


def test_run_rescrape_dry_run_liste_sans_scraper(db_session, monkeypatch):
    _course(db_session, "A", "https://k/1")
    vus: list[str] = []

    def _iter(db, url, settings, force=False):
        vus.append(url)
        yield {"phase": "done", "imported": 0, "skipped": 0, "total": 0}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    out = rescrape_service.run_rescrape_db(db_session, _settings(), dry_run=True, delay=0.0)
    assert vus == []
    assert out.dry_run_urls == ["https://k/1"]
    assert out.total == 1


def test_run_rescrape_ignore_les_courses_sans_url(db_session, monkeypatch):
    _course(db_session, "SansUrl", "")
    vus: list[str] = []

    def _iter(db, url, settings, force=False):
        vus.append(url)
        yield {"phase": "done", "imported": 0, "skipped": 0, "total": 0}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    out = rescrape_service.run_rescrape_db(db_session, _settings(), delay=0.0)
    assert out.total == 0
    assert vus == []


def test_run_rescrape_un_echec_n_interrompt_pas_le_batch(db_session, monkeypatch):
    _course(db_session, "Boom", "https://k/boom", jour=1)
    _course(db_session, "Ok", "https://k/ok", jour=2)

    def _iter(db, url, settings, force=False):
        if "boom" in url:
            yield {"phase": "error", "message": "échec"}
            return
        yield {"phase": "done", "imported": 1, "skipped": 0, "total": 1}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    out = rescrape_service.run_rescrape_db(db_session, _settings(), delay=0.0)
    assert out.total == 2
    assert out.errors == 1
    assert out.imported == 1


def test_run_rescrape_libelle_avec_le_nom_de_course(db_session, monkeypatch, fake_reporter):
    """Ici le nom vient de la DB : contrairement à import-sheet, on l'a avant le scrape."""
    _course(db_session, "Triathlon de Nantes", "https://k/1")

    def _iter(db, url, settings, force=False):
        yield {"phase": "done", "imported": 1, "skipped": 0, "total": 1}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    rescrape_service.run_rescrape_db(db_session, _settings(), delay=0.0, reporter=fake_reporter)

    assert ("item_start", 0, "klikego · Triathlon de Nantes") in fake_reporter.calls
```

- [ ] **Step 2 : Lancer les tests pour les voir échouer**

Run: `pytest tests/test_services/test_rescrape_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'rescrape_service' from 'app.services'`

- [ ] **Step 3 : Écrire l'implémentation**

Créer `backend/app/services/rescrape_service.py` :

```python
"""Re-scrape en masse des courses déjà en base (force=True, bypass du cache TTL)."""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.repositories import course_repository
from app.services.batch import BatchItem, run_batch
from app.services.progress import ProgressReporter


@dataclass
class RescrapeOutcome:
    """Bilan d'un rescrape-db."""
    total: int = 0
    imported: int = 0
    skipped: int = 0
    errors: int = 0
    dry_run_urls: list[str] = field(default_factory=list)
    interrupted: bool = False


def run_rescrape_db(
    db: Session,
    settings: Settings,
    *,
    dry_run: bool = False,
    older_than: int | None = None,
    provider: str | None = None,
    limit: int | None = None,
    delay: float = 1.0,
    reporter: ProgressReporter | None = None,
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

    # Le nom de la course vient de la DB : on peut libeller proprement.
    items = [
        BatchItem(url=c.source_url, label=f"{c.provider} · {c.name}") for c in courses
    ]
    totals = run_batch(db, items, settings, force=True, delay=delay, reporter=reporter)

    outcome.imported = totals.imported
    outcome.skipped = totals.skipped
    outcome.errors = totals.errors
    outcome.interrupted = totals.interrupted
    return outcome
```

- [ ] **Step 4 : Faire déléguer `cli.py` (il reste vert)**

Dans `backend/app/cli.py` : supprimer la dataclass `RescrapeOutcome` et la fonction `run_rescrape_db`, ainsi que l'import `course_repository` devenu inutile. Ajouter au ré-export :

```python
from app.services.rescrape_service import (  # noqa: F401 — ré-export transitoire (Task 7)
    RescrapeOutcome,
    run_rescrape_db,
)
```

À ce stade `cli.py` ne contient plus que : les ré-exports, les deux `render_*_report`, les deux commandes Typer, et `app = typer.Typer(...)`.

- [ ] **Step 5 : Supprimer `tests/test_cli.py`**

Les 4 derniers tests viennent d'être migrés. Le fichier est vide de tests utiles :

```bash
git rm backend/tests/test_cli.py
```

- [ ] **Step 6 : Lancer toute la suite**

Run: `pytest -m "not integration" -q && ruff check .`
Expected: PASS — les 14 tests d'origine existent tous, sous leurs nouvelles adresses.

- [ ] **Step 7 : Commit**

```bash
git add backend/app/services/rescrape_service.py backend/app/cli.py \
        backend/tests/test_services/test_rescrape_service.py
git commit -m "refactor(services): rescrape_service avec progression"
```

---

### Task 6 : Les reporters d'affichage

Python ne tolère pas `app/cli.py` et le package `app/cli/` simultanément, et `cli.py` doit rester importable jusqu'à la Task 7. On crée donc les reporters dans un module plat `app/cli_reporters.py`, que la Task 7 déplacera en `app/cli/progress.py` (contenu identique, `git mv`).

**Files:**
- Create: `backend/app/cli_reporters.py`
- Modify: `backend/requirements.txt`
- Create: `backend/tests/test_cli_reporters.py`

**Interfaces:**
- Consumes: `services.progress.{NullReporter, ProgressReporter}`.
- Produces: `truncate(label: str, limit: int = 60) -> str`, `_stderr_is_tty() -> bool` (point d'injection des tests), `PlainReporter(write: Callable[[str], None] | None = None)`, `RichReporter(console: rich.console.Console | None = None)`, `select_reporter(*, no_progress: bool = False, plain: bool = False) -> ProgressReporter`.

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer `backend/tests/test_cli_reporters.py` :

```python
from app import cli_reporters
from app.cli_reporters import PlainReporter, RichReporter, select_reporter, truncate
from app.services.progress import NullReporter, ProgressReporter


def test_les_reporters_respectent_le_protocol():
    assert isinstance(PlainReporter(), ProgressReporter)
    assert isinstance(RichReporter(), ProgressReporter)


def test_truncate_borne_le_libelle():
    assert truncate("court") == "court"
    long = "k · https://www.klikego.com/" + "a" * 100
    assert len(truncate(long)) == 60
    assert truncate(long).endswith("…")


def test_plain_reporter_une_ligne_par_epreuve_sans_ansi():
    lignes: list[str] = []
    reporter = PlainReporter(write=lignes.append)

    reporter.batch_start(2)
    reporter.item_start(0, "klikego · Triathlon de Nantes")
    reporter.item_progress(20, 30)
    reporter.item_done(28, 2, None)
    reporter.item_start(1, "timepulse · Duathlon de Rezé")
    reporter.item_done(0, 0, "timeout scrape")
    reporter.batch_end()

    texte = "\n".join(lignes)
    assert "\x1b" not in texte  # aucun code ANSI : lisible dans un log
    assert "[1/2]" in texte
    assert "scraping en cours" in texte  # le log ne reste pas muet pendant le scrape
    assert "28 importés, 2 ignorés" in texte
    assert "[2/2]" in texte
    assert "ERREUR : timeout scrape" in texte


def test_plain_reporter_ecrit_sur_stderr_pas_stdout(capsys):
    reporter = PlainReporter()
    reporter.batch_start(1)

    capture = capsys.readouterr()
    assert capture.out == ""      # stdout reste propre pour --json
    assert "1 épreuve" in capture.err


def test_select_reporter_null_si_no_progress():
    assert isinstance(select_reporter(no_progress=True), NullReporter)


def test_select_reporter_plain_hors_tty(monkeypatch):
    monkeypatch.setattr(cli_reporters, "_stderr_is_tty", lambda: False)
    assert isinstance(select_reporter(), PlainReporter)


def test_select_reporter_rich_en_tty(monkeypatch):
    monkeypatch.setattr(cli_reporters, "_stderr_is_tty", lambda: True)
    assert isinstance(select_reporter(), RichReporter)


def test_select_reporter_plain_force_meme_en_tty(monkeypatch):
    monkeypatch.setattr(cli_reporters, "_stderr_is_tty", lambda: True)
    assert isinstance(select_reporter(plain=True), PlainReporter)
```

- [ ] **Step 2 : Lancer les tests pour les voir échouer**

Run: `pytest tests/test_cli_reporters.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.cli_reporters'`

- [ ] **Step 3 : Écrire l'implémentation**

Créer `backend/app/cli_reporters.py` :

```python
"""Implémentations d'affichage du ProgressReporter (couche CLI).

Tout sort sur **stderr** : stdout reste réservé au rapport final et à `--json`,
qui doivent rester parsables quand on redirige la sortie.
"""
import sys
import time
from collections.abc import Callable

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from app.services.progress import NullReporter, ProgressReporter

MAX_LABEL = 60


def truncate(label: str, limit: int = MAX_LABEL) -> str:
    """Borne un libellé pour l'affichage (les URLs de Sheet sont longues)."""
    if len(label) <= limit:
        return label
    return label[: limit - 1] + "…"


def _stderr(ligne: str) -> None:
    print(ligne, file=sys.stderr, flush=True)


def _stderr_is_tty() -> bool:
    """Isolé dans une fonction : c'est le point d'injection des tests."""
    return sys.stderr.isatty()


class PlainReporter:
    """Une ligne par épreuve, sans code ANSI : lisible dans un log (cron, CI, CI/CD)."""

    def __init__(self, write: Callable[[str], None] | None = None) -> None:
        self._write = write or _stderr
        self._total = 0
        self._index = 0
        self._label = ""
        self._debut = 0.0

    def batch_start(self, total: int) -> None:
        self._total = total
        self._write(f"=== {total} épreuve(s) à traiter ===")

    def item_start(self, index: int, label: str) -> None:
        self._index = index
        self._label = truncate(label)
        self._debut = time.monotonic()
        # Le scrape peut durer une minute : le log ne doit pas rester muet.
        self._write(f"[{index + 1}/{self._total}] {self._label} · scraping en cours…")

    def item_progress(self, done: int, total: int) -> None:
        pass  # le détail intra-épreuve est réservé au mode TTY : ici il inonderait le log

    def item_done(self, imported: int, skipped: int, error: str | None) -> None:
        duree = time.monotonic() - self._debut
        issue = f"ERREUR : {error}" if error else f"{imported} importés, {skipped} ignorés"
        self._write(f"[{self._index + 1}/{self._total}] {self._label} → {issue} ({duree:.1f}s)")

    def batch_end(self) -> None:
        pass


class RichReporter:
    """Deux barres imbriquées dans un terminal : le batch, puis l'épreuve courante."""

    def __init__(self, console: Console | None = None) -> None:
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console or Console(stderr=True),
            transient=True,  # les barres s'effacent : le rapport final reste seul
        )
        self._batch_task: int | None = None
        self._item_task: int | None = None
        self._label = ""

    def batch_start(self, total: int) -> None:
        self._progress.start()
        self._batch_task = self._progress.add_task("Épreuves", total=total)
        self._item_task = self._progress.add_task("En attente…", total=None)

    def item_start(self, index: int, label: str) -> None:
        self._label = truncate(label)
        self._progress.reset(
            self._item_task, total=None, description=f"  {self._label} · scraping…"
        )

    def item_progress(self, done: int, total: int) -> None:
        self._progress.update(
            self._item_task,
            completed=done,
            total=total,
            description=f"  {self._label} · enregistrement",
        )

    def item_done(self, imported: int, skipped: int, error: str | None) -> None:
        self._progress.advance(self._batch_task)
        if error:
            # Les erreurs survivent à l'effacement des barres : on veut les revoir.
            self._progress.console.print(f"  [red]✗[/red] {self._label} → {error}")

    def batch_end(self) -> None:
        self._progress.stop()


def select_reporter(
    *, no_progress: bool = False, plain: bool = False
) -> ProgressReporter:
    """Rich en terminal, lignes simples ailleurs (cron, redirection), rien si --no-progress."""
    if no_progress:
        return NullReporter()
    if plain or not _stderr_is_tty():
        return PlainReporter()
    return RichReporter()
```

- [ ] **Step 4 : Déclarer `rich` en dépendance explicite**

Dans `backend/requirements.txt`, sous la ligne `typer==0.26.7`, ajouter :

```
rich==15.0.0
```

(Déjà installé — Typer le tire via `Requires-Dist: rich>=13.8.0`. On l'épingle car on l'importe désormais directement.)

- [ ] **Step 5 : Lancer les tests pour les voir passer**

Run: `pytest tests/test_cli_reporters.py -v`
Expected: PASS (8 tests)

- [ ] **Step 6 : Vérifier que rien n'a régressé**

Run: `pytest -m "not integration" -q && ruff check .`
Expected: PASS

- [ ] **Step 7 : Commit**

```bash
git add backend/app/cli_reporters.py backend/tests/test_cli_reporters.py backend/requirements.txt
git commit -m "feat(cli): reporters Rich (TTY) et Plain (log), sortie sur stderr"
```

---

### Task 7 : Le package CLI

Bascule finale : `app/cli.py` (module) devient `app/cli/` (package). Les deux ne peuvent pas coexister — c'est pourquoi tout le reste a été préparé d'abord.

**Files:**
- Delete: `backend/app/cli.py`
- Delete: `backend/app/cli_reporters.py` (déplacé)
- Create: `backend/app/cli/__init__.py`, `backend/app/cli/__main__.py`, `backend/app/cli/progress.py` (ex-`cli_reporters.py`, contenu identique), `backend/app/cli/reports.py`, `backend/app/cli/commands/__init__.py`, `backend/app/cli/commands/import_sheet.py`, `backend/app/cli/commands/rescrape_db.py`
- Move: `backend/tests/test_cli_reporters.py` → `backend/tests/test_cli/test_progress.py`
- Create: `backend/tests/test_cli/__init__.py`, `backend/tests/test_cli/test_reports.py`, `backend/tests/test_cli/test_commands.py`

**Interfaces:**
- Consumes: `bulk_import_service.{SheetOutcome, run_import_sheet}`, `rescrape_service.{RescrapeOutcome, run_rescrape_db}`, `sheet_source.{DEFAULT_SHEET_URL, download_csv}`, `cli.progress.select_reporter`.
- Produces: `app.cli.app` (le `typer.Typer`), invocable par `python -m app.cli`.

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer `backend/tests/test_cli/__init__.py` (vide).

Créer `backend/tests/test_cli/test_reports.py` :

```python
from app.cli.reports import render_rescrape_report, render_sheet_report
from app.services.bulk_import_service import SheetOutcome
from app.services.rescrape_service import RescrapeOutcome


def test_rapport_sheet_dry_run_masque_les_compteurs_d_import():
    out = SheetOutcome(unique_supported=3, rows_without_link=2)
    texte = render_sheet_report(out, dry_run=True)

    assert "IMPORT SHEET (dry-run)" in texte
    assert "Liens supportés uniques : 3" in texte
    assert "Lignes sans lien        : 2" in texte
    assert "Importées" not in texte


def test_rapport_sheet_liste_les_ignores_par_host():
    out = SheetOutcome(
        imported=5, skipped=1, errors=1, unique_supported=2,
        ignored_by_host={"inconnu.example": 3},
    )
    texte = render_sheet_report(out, dry_run=False)

    assert "Importées : 5" in texte
    assert "En erreur : 1" in texte
    assert "inconnu.example : 3" in texte


def test_rapport_sheet_signale_l_interruption():
    out = SheetOutcome(imported=5, unique_supported=10, interrupted=True)
    texte = render_sheet_report(out, dry_run=False)

    assert "interrompu" in texte.lower()


def test_rapport_rescrape_dry_run_liste_les_urls():
    out = RescrapeOutcome(total=2, dry_run_urls=["https://k/1", "https://k/2"])
    texte = render_rescrape_report(out, dry_run=True)

    assert "RESCRAPE DB (dry-run)" in texte
    assert "Courses ciblées : 2" in texte
    assert "https://k/1" in texte


def test_rapport_rescrape_signale_l_interruption():
    out = RescrapeOutcome(total=10, imported=3, interrupted=True)
    texte = render_rescrape_report(out, dry_run=False)

    assert "interrompu" in texte.lower()
    assert "Importées : 3" in texte
```

Créer `backend/tests/test_cli/test_commands.py` — smoke tests du câblage (options → service → rendu → code de sortie). La DB et le réseau sont écartés :

```python
from contextlib import contextmanager

from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import import_sheet as cmd_import
from app.cli.commands import rescrape_db as cmd_rescrape
from app.services.bulk_import_service import SheetOutcome
from app.services.rescrape_service import RescrapeOutcome

runner = CliRunner()


@contextmanager
def _fausse_session():
    yield None


def test_import_sheet_dry_run_affiche_le_rapport(monkeypatch):
    monkeypatch.setattr(cmd_import, "session_scope", _fausse_session)
    monkeypatch.setattr(cmd_import.sheet_source, "download_csv", lambda url: "a,b\n")
    monkeypatch.setattr(
        cmd_import.bulk_import_service, "run_import_sheet",
        lambda *a, **k: SheetOutcome(unique_supported=4, rows_without_link=1),
    )

    result = runner.invoke(app, ["import-sheet", "--dry-run"])

    assert result.exit_code == 0
    assert "IMPORT SHEET (dry-run)" in result.stdout
    assert "Liens supportés uniques : 4" in result.stdout


def test_import_sheet_json_emet_du_json_sur_stdout(monkeypatch):
    import json

    monkeypatch.setattr(cmd_import, "session_scope", _fausse_session)
    monkeypatch.setattr(cmd_import.sheet_source, "download_csv", lambda url: "a,b\n")
    monkeypatch.setattr(
        cmd_import.bulk_import_service, "run_import_sheet",
        lambda *a, **k: SheetOutcome(imported=7, skipped=2, unique_supported=1),
    )

    result = runner.invoke(app, ["import-sheet", "--json"])

    assert result.exit_code == 0
    derniere = result.stdout.strip().splitlines()[-1]
    assert json.loads(derniere)["imported"] == 7


def test_import_sheet_interrompu_sort_en_130(monkeypatch):
    monkeypatch.setattr(cmd_import, "session_scope", _fausse_session)
    monkeypatch.setattr(cmd_import.sheet_source, "download_csv", lambda url: "a,b\n")
    monkeypatch.setattr(
        cmd_import.bulk_import_service, "run_import_sheet",
        lambda *a, **k: SheetOutcome(imported=3, unique_supported=9, interrupted=True),
    )

    result = runner.invoke(app, ["import-sheet"])

    assert result.exit_code == 130
    assert "Importées : 3" in result.stdout  # le bilan partiel est bien affiché


def test_rescrape_db_dry_run_affiche_les_urls(monkeypatch):
    monkeypatch.setattr(cmd_rescrape, "session_scope", _fausse_session)
    monkeypatch.setattr(
        cmd_rescrape.rescrape_service, "run_rescrape_db",
        lambda *a, **k: RescrapeOutcome(total=1, dry_run_urls=["https://k/1"]),
    )

    result = runner.invoke(app, ["rescrape-db", "--dry-run"])

    assert result.exit_code == 0
    assert "Courses ciblées : 1" in result.stdout
    assert "https://k/1" in result.stdout


def test_rescrape_db_interrompu_sort_en_130(monkeypatch):
    monkeypatch.setattr(cmd_rescrape, "session_scope", _fausse_session)
    monkeypatch.setattr(
        cmd_rescrape.rescrape_service, "run_rescrape_db",
        lambda *a, **k: RescrapeOutcome(total=9, imported=2, interrupted=True),
    )

    result = runner.invoke(app, ["rescrape-db"])

    assert result.exit_code == 130
```

- [ ] **Step 2 : Lancer les tests pour les voir échouer**

Run: `pytest tests/test_cli/ -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.cli.reports'`

- [ ] **Step 3 : Basculer le module en package**

```bash
cd backend
git rm app/cli.py
mkdir -p app/cli/commands
git mv app/cli_reporters.py app/cli/progress.py
mkdir -p tests/test_cli
git mv tests/test_cli_reporters.py tests/test_cli/test_progress.py
```

Dans `tests/test_cli/test_progress.py`, corriger les imports : `from app import cli_reporters` → `from app.cli import progress as cli_reporters`, et `from app.cli_reporters import ...` → `from app.cli.progress import ...`. Le reste du fichier est inchangé.

Créer `backend/app/cli/commands/__init__.py` (vide).

- [ ] **Step 4 : Écrire le rendu des rapports**

Créer `backend/app/cli/reports.py` :

```python
"""Rendu texte des bilans de batch. Aucune logique métier : de la mise en forme."""
from app.services.bulk_import_service import SheetOutcome
from app.services.rescrape_service import RescrapeOutcome


def _titre(base: str, *, dry_run: bool, interrupted: bool) -> str:
    if dry_run:
        return f"=== {base} (dry-run) ==="
    if interrupted:
        return f"=== {base} (interrompu — bilan partiel) ==="
    return f"=== {base} ==="


def render_sheet_report(outcome: SheetOutcome, *, dry_run: bool) -> str:
    """Rapport texte lisible : compteurs + table des ignorés groupés par host."""
    lignes = [_titre("IMPORT SHEET", dry_run=dry_run, interrupted=outcome.interrupted)]
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


def render_rescrape_report(outcome: RescrapeOutcome, *, dry_run: bool) -> str:
    """Rapport texte lisible pour rescrape-db."""
    lignes = [_titre("RESCRAPE DB", dry_run=dry_run, interrupted=outcome.interrupted)]
    lignes.append(f"Courses ciblées : {outcome.total}")
    if dry_run:
        for url in outcome.dry_run_urls:
            lignes.append(f"  - {url}")
    else:
        lignes.append(f"Importées : {outcome.imported}")
        lignes.append(f"Ignorées  : {outcome.skipped}")
        lignes.append(f"En erreur : {outcome.errors}")
    return "\n".join(lignes)
```

- [ ] **Step 5 : Écrire les deux commandes**

Créer `backend/app/cli/commands/import_sheet.py` :

```python
"""Commande `import-sheet` : options Typer, câblage, affichage. Zéro logique métier."""
import json
from dataclasses import asdict

import typer

from app.cli.progress import select_reporter
from app.cli.reports import render_sheet_report
from app.core.config import get_settings
from app.core.database import session_scope
from app.services import bulk_import_service, sheet_source


def import_sheet(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Détecte et dédoublonne sans scraper ni persister."
    ),
    limit: int | None = typer.Option(None, "--limit", help="Borne le nombre d'épreuves."),
    only_provider: str | None = typer.Option(
        None, "--only-provider", help="Restreint à un provider (ex. klikego)."
    ),
    sheet_url: str = typer.Option(
        sheet_source.DEFAULT_SHEET_URL, "--sheet-url", envvar="IMPORT_SHEET_URL",
        help="Override la source CSV.",
    ),
    delay: float = typer.Option(
        1.0, "--delay", help="Pause de politesse entre scrapes réels (s)."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Rapport machine-lisible en plus du texte."
    ),
    no_progress: bool = typer.Option(
        False, "--no-progress", help="Aucun affichage de progression."
    ),
    plain: bool = typer.Option(
        False, "--plain", help="Progression ligne à ligne même dans un terminal."
    ),
) -> None:
    """Amorce la base depuis le Google Sheet des adhérents."""
    settings = get_settings()
    csv_text = sheet_source.download_csv(sheet_url)
    reporter = select_reporter(no_progress=no_progress or dry_run, plain=plain)

    with session_scope() as db:
        outcome = bulk_import_service.run_import_sheet(
            db, csv_text, settings,
            dry_run=dry_run, limit=limit, only_provider=only_provider,
            delay=delay, reporter=reporter,
        )

    typer.echo(render_sheet_report(outcome, dry_run=dry_run))
    if json_output:
        typer.echo(json.dumps(asdict(outcome), ensure_ascii=False))
    if outcome.interrupted:
        raise typer.Exit(code=130)
```

Créer `backend/app/cli/commands/rescrape_db.py` :

```python
"""Commande `rescrape-db` : options Typer, câblage, affichage. Zéro logique métier."""
import json
from dataclasses import asdict

import typer

from app.cli.progress import select_reporter
from app.cli.reports import render_rescrape_report
from app.core.config import get_settings
from app.core.database import session_scope
from app.services import rescrape_service


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
    no_progress: bool = typer.Option(
        False, "--no-progress", help="Aucun affichage de progression."
    ),
    plain: bool = typer.Option(
        False, "--plain", help="Progression ligne à ligne même dans un terminal."
    ),
) -> None:
    """Re-scrape tous les events en DB (force=True, bypass du cache TTL)."""
    settings = get_settings()
    reporter = select_reporter(no_progress=no_progress or dry_run, plain=plain)

    with session_scope() as db:
        outcome = rescrape_service.run_rescrape_db(
            db, settings,
            dry_run=dry_run, older_than=older_than, provider=provider,
            limit=limit, delay=delay, reporter=reporter,
        )

    typer.echo(render_rescrape_report(outcome, dry_run=dry_run))
    if json_output:
        typer.echo(json.dumps(asdict(outcome), ensure_ascii=False))
    if outcome.interrupted:
        raise typer.Exit(code=130)
```

- [ ] **Step 6 : Monter le Typer**

Créer `backend/app/cli/__init__.py` :

```python
"""Outillage CLI (Typer) : import de masse depuis le Google Sheet & rescrape DB.

CLI mince par-dessus les services : aucune logique de scraping ni d'accès DB
direct. Invocable depuis backend/ :
    python -m app.cli import-sheet --dry-run
    python -m app.cli rescrape-db --dry-run
"""
import typer

from app.cli.commands.import_sheet import import_sheet
from app.cli.commands.rescrape_db import rescrape_db

app = typer.Typer(help="Outillage d'import de masse et de rescrape.")
app.command("import-sheet")(import_sheet)
app.command("rescrape-db")(rescrape_db)

__all__ = ["app"]
```

Créer `backend/app/cli/__main__.py` :

```python
"""Point d'entrée `python -m app.cli`."""
from app.cli import app

if __name__ == "__main__":
    app()
```

- [ ] **Step 7 : Lancer les tests pour les voir passer**

Run: `pytest tests/test_cli/ -v`
Expected: PASS (5 tests de rapports + 5 de commandes + 8 de reporters)

- [ ] **Step 8 : Vérifier toute la suite et le lint**

Run: `pytest -m "not integration" -q && ruff check .`
Expected: PASS

- [ ] **Step 9 : Vérifier le comportement réel de la CLI**

L'aide doit lister les deux commandes et les nouvelles options :

```bash
python -m app.cli --help
python -m app.cli import-sheet --help
```
Expected: `--no-progress` et `--plain` apparaissent ; `python -m app.cli` fonctionne toujours.

Le dry-run doit tourner de bout en bout (il télécharge le CSV, ne scrape rien) :

```bash
python -m app.cli import-sheet --dry-run
```
Expected: le rapport `=== IMPORT SHEET (dry-run) ===` avec les compteurs.

La progression doit réellement s'afficher, et `--json` rester parsable malgré elle :

```bash
python -m app.cli rescrape-db --limit 2 --delay 0 --json | python -m json.tool
```
Expected: la progression apparaît à l'écran (stderr) mais **pas** dans le pipe ; `json.tool` parse la dernière ligne sans erreur.

- [ ] **Step 10 : Commit**

```bash
git add -A backend/app/cli backend/tests/test_cli
git commit -m "refactor(cli): package cli/ (commandes, rapports, progression)"
```

---

### Task 8 : Documentation

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1 : Documenter la CLI dans AGENTS.md**

Dans la section « Commandes », sous le bloc Backend, ajouter :

```markdown
python -m app.cli import-sheet --dry-run     # import de masse (Sheet) — progression en direct
python -m app.cli rescrape-db --limit 10     # re-scrape la DB (force=True) ; --plain, --no-progress
```

Dans « Architecture backend », compléter la ligne `app/services/` :

```markdown
- `app/services/` — logique métier : `mapping`, `cache` (TTL), `scrape_service`,
  `import_service`, `stats_service`, `geocode_service`, plus les batches CLI :
  `sheet_source` (source Google Sheet), `batch` (boucle + progression),
  `bulk_import_service`, `rescrape_service`, `progress` (Protocol `ProgressReporter`).
- `app/cli/` — Typer : `commands/` (une commande par fichier), `progress.py`
  (reporters Rich/Plain, sortie sur **stderr**), `reports.py` (rendu des bilans).
  La progression réutilise `import_service.iter_import_event()`, le générateur de
  phases du SSE.
```

- [ ] **Step 2 : Commit**

```bash
git add AGENTS.md
git commit -m "docs: CLI en package + services de batch"
```

---

## Récapitulatif de la structure cible

| Fichier | Responsabilité |
| --- | --- |
| `services/progress.py` | Le contrat `ProgressReporter` + `NullReporter` |
| `services/sheet_source.py` | Télécharger / parser / normaliser la source Sheet |
| `services/batch.py` | La boucle : consomme `iter_import_event`, relaie la progression, encaisse les erreurs et le Ctrl-C |
| `services/bulk_import_service.py` | Sélection des liens à importer + bilan |
| `services/rescrape_service.py` | Sélection des courses à re-scraper + bilan |
| `cli/progress.py` | `RichReporter`, `PlainReporter`, `select_reporter` |
| `cli/reports.py` | Rendu texte des bilans |
| `cli/commands/*.py` | Une commande Typer par fichier |
| `cli/__init__.py` | Montage du Typer |
