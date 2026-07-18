# Ciblage d'épreuves en CLI (`--url` / `--urls-from`) — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permettre à `rescrape-db` de cibler des épreuves précises par URL (`--url`, `--urls-from`), y compris des épreuves absentes de la base, et fermer la boucle de rejeu en exposant le détail des échecs dans le bilan de `rescrape-db`.

**Architecture:** Un nouveau module CLI `app/cli/url_sources.py` collecte et valide les URLs (fichier, stdin, options répétées) et rejette la combinaison avec les filtres base. `rescrape_service.run_rescrape_db` gagne un paramètre `urls` : quand il est fourni, la base n'est plus interrogée pour *sélectionner* (seulement pour libeller), et les deux modes convergent sur le `run_batch` existant. `RescrapeOutcome` gagne `failures`, et le rendu du détail des échecs est factorisé entre les deux rapports.

**Tech Stack:** Python 3.13, uv, Typer/Click, pytest, ruff. Toutes les commandes s'exécutent depuis `backend/`.

## Global Constraints

- Langue : code, commentaires, messages et docstrings en **français avec accents**.
- **stdout reste parsable** : progression et messages d'erreur sur stderr ; avec `--json`, stdout ne porte que la ligne JSON.
- Codes de sortie inchangés : `0` succès (y compris partiel et zéro épreuve ciblée), `1` échec total, `2` saisie invalide, `130` Ctrl-C (prioritaire sur `1`).
- La CLI compte des **épreuves** (une `source_url` unique), jamais des courses.
- `app/cli/` est une **couche mince** : zéro logique métier. La validation d'entrée utilisateur y a en revanche toute sa place (précédent : `validators.valider_provider`).
- Aucun test réseau : `run_batch` / `import_service.iter_import_event` sont mockés. Le marker `integration` n'est pas concerné.
- Clé de déduplication d'URL : `sheet_source.normalize_url`, partout, sans exception.
- Erreur de saisie → `typer.BadParameter` (message + usage sur stderr, code 2), levée **avant** l'ouverture de la Session.
- Commits : Conventional Commits.
- Hors périmètre : pas de `--url` sur `import-sheet` ; pas de mémorisation des échecs entre deux runs.

---

## Structure des fichiers

| Fichier | Responsabilité |
| --- | --- |
| `backend/app/cli/url_sources.py` *(créé)* | Collecte des URLs (options répétées, fichier, stdin), validation de forme, exclusivité des modes de ciblage. |
| `backend/app/services/rescrape_service.py` *(modifié)* | Second mode de sélection (`urls`) + champ `failures` sur `RescrapeOutcome`. |
| `backend/app/cli/reports.py` *(modifié)* | Helper `_lignes_echecs` partagé par les deux rendus. |
| `backend/app/cli/commands/rescrape_db.py` *(modifié)* | Options `--url` / `--urls-from`, câblage. |
| `backend/tests/test_cli/test_url_sources.py` *(créé)* | Tests unitaires du nouveau module. |
| `backend/tests/test_cli/test_commands.py` *(modifié)* | Tests d'intégration CLI (codes de sortie, transmission au service). |
| `backend/tests/test_cli/test_reports.py` *(modifié)* | Détail des échecs dans le rapport `rescrape-db`. |
| `backend/tests/test_services/test_rescrape_service.py` *(modifié)* | Mode `urls` du service. |
| `AGENTS.md` *(modifié)* | Doc CLI : options, boucle de rejeu, correction de la phrase qui réserve le détail des échecs à `import-sheet`. |

**Écart assumé vs la spec de conception :** la spec donne `charger_urls(urls, urls_from) -> list[str]`. Le plan retient `-> list[str] | None` : `None` = « aucun ciblage par URL demandé » (mode base), `[]` = « ciblage demandé, liste vide » (zéro épreuve, code 0). Sans cette distinction, un `--urls-from vide.txt` retomberait silencieusement sur le mode base et re-scraperait toute la table — exactement le silence trompeur que la spec cherche à éviter.

---

### Task 1 : Module `cli/url_sources.py`

**Files:**
- Create: `backend/app/cli/url_sources.py`
- Test: `backend/tests/test_cli/test_url_sources.py`

**Interfaces:**
- Consumes: `app.services.sheet_source.dedupe_links(links: list[str]) -> list[str]` (existant).
- Produces:
  - `charger_urls(urls: list[str] | None, urls_from: str | None) -> list[str] | None`
  - `valider_ciblage_exclusif(*, urls: list[str] | None, provider: str | None, older_than: int | None) -> None`

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `backend/tests/test_cli/test_url_sources.py` :

```python
import pytest
import typer

from app.cli import url_sources


def test_aucun_ciblage_renvoie_none():
    """None (et non []) : « pas de ciblage demandé » ≠ « liste vide »."""
    assert url_sources.charger_urls([], None) is None


def test_url_repetee_conserve_l_ordre():
    assert url_sources.charger_urls(["https://k/1", "https://k/2"], None) == [
        "https://k/1",
        "https://k/2",
    ]


def test_urls_from_fichier(tmp_path):
    fichier = tmp_path / "echecs.txt"
    fichier.write_text("https://k/1\nhttps://k/2\n", encoding="utf-8")

    assert url_sources.charger_urls([], str(fichier)) == ["https://k/1", "https://k/2"]


def test_url_et_urls_from_se_cumulent(tmp_path):
    """Ajouter une URL à une liste est un besoin légitime : les deux se cumulent."""
    fichier = tmp_path / "echecs.txt"
    fichier.write_text("https://k/2\n", encoding="utf-8")

    assert url_sources.charger_urls(["https://k/1"], str(fichier)) == [
        "https://k/1",
        "https://k/2",
    ]


def test_urls_from_tiret_lit_stdin(monkeypatch):
    import io
    import sys

    monkeypatch.setattr(sys, "stdin", io.StringIO("https://k/1\nhttps://k/2\n"))

    assert url_sources.charger_urls([], "-") == ["https://k/1", "https://k/2"]


def test_lignes_vides_et_commentaires_ignorees(tmp_path):
    """Un opérateur commente une URL plutôt que de la supprimer."""
    fichier = tmp_path / "echecs.txt"
    fichier.write_text(
        "# épreuves du 12/07\nhttps://k/1\n\n  \n#https://k/2\n", encoding="utf-8"
    )

    assert url_sources.charger_urls([], str(fichier)) == ["https://k/1"]


def test_fichier_vide_renvoie_liste_vide(tmp_path):
    """[] et non None : le ciblage a bien été demandé → zéro épreuve, code 0."""
    fichier = tmp_path / "vide.txt"
    fichier.write_text("", encoding="utf-8")

    assert url_sources.charger_urls([], str(fichier)) == []


def test_ligne_non_http_cite_le_numero_de_ligne(tmp_path):
    fichier = tmp_path / "echecs.txt"
    fichier.write_text("https://k/1\nsalut\n", encoding="utf-8")

    with pytest.raises(typer.BadParameter) as exc:
        url_sources.charger_urls([], str(fichier))

    assert "ligne 2" in str(exc.value)
    assert "salut" in str(exc.value)


def test_url_option_non_http_rejetee():
    with pytest.raises(typer.BadParameter) as exc:
        url_sources.charger_urls(["ftp://k/1"], None)

    assert "ftp://k/1" in str(exc.value)


def test_fichier_introuvable_rejete(tmp_path):
    with pytest.raises(typer.BadParameter) as exc:
        url_sources.charger_urls([], str(tmp_path / "absent.txt"))

    assert "absent.txt" in str(exc.value)


def test_dedoublonne_en_conservant_la_forme_d_origine():
    """Casse d'hôte et slash final : une seule épreuve, forme d'origine gardée."""
    urls = url_sources.charger_urls(
        ["https://Klikego.com/e/1", "https://klikego.com/e/1/"], None
    )

    assert urls == ["https://Klikego.com/e/1"]


def test_ciblage_exclusif_accepte_le_mode_base():
    url_sources.valider_ciblage_exclusif(urls=None, provider="klikego", older_than=30)


def test_ciblage_exclusif_accepte_les_urls_seules():
    url_sources.valider_ciblage_exclusif(urls=["https://k/1"], provider=None, older_than=None)


def test_ciblage_exclusif_refuse_url_avec_provider():
    with pytest.raises(typer.BadParameter) as exc:
        url_sources.valider_ciblage_exclusif(
            urls=["https://k/1"], provider="klikego", older_than=None
        )

    assert "--provider" in str(exc.value)


def test_ciblage_exclusif_refuse_url_avec_older_than():
    with pytest.raises(typer.BadParameter) as exc:
        url_sources.valider_ciblage_exclusif(urls=[], provider=None, older_than=30)

    assert "--older-than" in str(exc.value)
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `uv run pytest tests/test_cli/test_url_sources.py -q`
Expected: FAIL — collecte impossible, `ModuleNotFoundError: No module named 'app.cli.url_sources'`.

- [ ] **Step 3: Écrire l'implémentation minimale**

Créer `backend/app/cli/url_sources.py` :

```python
"""Collecte des URLs ciblées par la CLI (`--url`, `--urls-from`).

Distinct de `validators.py`, qui ne valide que des saisies déjà en mémoire :
collecter des URLs suppose en plus de **lire** — un fichier, ou stdin. Assez
pour justifier un module à part, minuscule et testable isolément.

Toute saisie invalide est rejetée par `typer.BadParameter` : message + usage sur
stderr, code de sortie 2 (convention Click), arrêt **avant** l'ouverture de la
Session. Même raisonnement que `valider_provider`.
"""
import sys
from pathlib import Path

import typer

from app.services import sheet_source


def _lignes_du_fichier(chemin: str) -> list[str]:
    """Lit `chemin`, ou **stdin** si `chemin` vaut `-` (pas de fichier temporaire)."""
    if chemin == "-":
        return sys.stdin.read().splitlines()
    try:
        return Path(chemin).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise typer.BadParameter(
            f"fichier d'URLs illisible : « {chemin} » ({exc.strerror})."
        ) from exc


def _valider_ligne(ligne: str, origine: str) -> None:
    if not ligne.startswith(("http://", "https://")):
        raise typer.BadParameter(f"{origine} n'est pas une URL http(s) : « {ligne} ».")


def charger_urls(urls: list[str] | None, urls_from: str | None) -> list[str] | None:
    """Concatène les `--url` répétés puis le contenu de `--urls-from`.

    Renvoie `None` quand **aucun** ciblage n'a été demandé — à distinguer d'une
    liste **vide** (fichier vide, ou liste d'échecs vide en fin de boucle de
    rejeu), qui signifie « zéro épreuve à traiter » et doit sortir en 0. Les
    confondre ferait retomber `--urls-from vide.txt` sur le mode base, qui
    re-scraperait toute la table en silence.

    Les deux options se cumulent : ajouter une URL à une liste est un besoin
    légitime. `--url` est répétable, `--urls-from` ne l'est pas — une seule
    source de liste, `cat a.txt b.txt | … --urls-from -` couvre le reste.

    Lignes vides et lignes commençant par `#` ignorées : un opérateur qui
    construit sa liste à la main commente une URL plutôt que de la supprimer.
    Toute autre ligne non-http(s) est rejetée **en citant son numéro de ligne**,
    corrigeable sans relire le fichier à l'œil.

    Dédup finale via `sheet_source.dedupe_links` : ordre et forme d'origine
    conservés, clé `normalize_url` — la même que partout ailleurs.
    """
    urls = urls or []
    if not urls and urls_from is None:
        return None

    collectees: list[str] = []
    for valeur in urls:
        ligne = valeur.strip()
        _valider_ligne(ligne, "--url")
        collectees.append(ligne)

    if urls_from is not None:
        for numero, brute in enumerate(_lignes_du_fichier(urls_from), start=1):
            ligne = brute.strip()
            if not ligne or ligne.startswith("#"):
                continue
            _valider_ligne(ligne, f"--urls-from, ligne {numero}")
            collectees.append(ligne)

    return sheet_source.dedupe_links(collectees)


def valider_ciblage_exclusif(
    *, urls: list[str] | None, provider: str | None, older_than: int | None
) -> None:
    """Refuse un ciblage par URL combiné à `--provider` ou `--older-than`.

    Ce sont deux **modes de sélection**, pas des filtres à composer : `--url`
    court-circuite la base (c'est tout l'intérêt du rejeu d'un échec d'import,
    dont l'épreuve n'est jamais persistée), tandis que `--provider` et
    `--older-than` filtrent ce que la base contient. Les combiner produirait un
    ET dont personne ne peut prédire le résultat.

    Vérification croisée, donc appelée explicitement en tête de commande : un
    callback Typer ne voit que sa propre option.
    """
    if urls is None:
        return
    incompatibles = []
    if provider is not None:
        incompatibles.append("--provider")
    if older_than is not None:
        incompatibles.append("--older-than")
    if incompatibles:
        raise typer.BadParameter(
            f"--url / --urls-from est exclusif de {' et '.join(incompatibles)} : "
            "ce sont deux modes de sélection, pas des filtres à composer."
        )
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `uv run pytest tests/test_cli/test_url_sources.py -q`
Expected: PASS — 14 passed.

- [ ] **Step 5: Lint**

Run: `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add app/cli/url_sources.py tests/test_cli/test_url_sources.py
git commit -m "feat(cli): collecte et validation des URLs ciblées (--url / --urls-from)"
```

---

### Task 2 : Mode `urls` dans `rescrape_service`

**Files:**
- Modify: `backend/app/services/rescrape_service.py:71-114`
- Test: `backend/tests/test_services/test_rescrape_service.py`

**Interfaces:**
- Consumes: `course_repository.get_latest_by_source_url(db, source_url) -> Course | None`, `sheet_source.dedupe_links`, `batch.BatchItem(url, label)`, `batch.run_batch`.
- Produces: `run_rescrape_db(db, settings, *, dry_run=False, older_than=None, provider=None, limit=None, delay=1.0, reporter=None, urls: list[str] | None = None) -> RescrapeOutcome`.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `backend/tests/test_services/test_rescrape_service.py` :

```python
def test_mode_urls_n_interroge_pas_iter_all(db_session, monkeypatch):
    """`--url` court-circuite la base : une URL inconnue est le cas nominal du
    rejeu d'un échec d'import, dont l'épreuve n'a rien persisté."""
    _course(db_session, "A", "https://k/en-base")
    appels: list[str] = []

    def _iter_all_interdit(*args, **kwargs):
        raise AssertionError("iter_all ne doit pas être appelé en mode urls")

    def _iter(db, url, settings, force=False):
        appels.append(url)
        yield {"phase": "done", "imported": 1, "skipped": 0, "total": 1}

    monkeypatch.setattr(course_repository, "iter_all", _iter_all_interdit)
    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    out = rescrape_service.run_rescrape_db(
        db_session, _settings(), delay=0.0, urls=["https://k/inconnue"]
    )

    assert appels == ["https://k/inconnue"]
    assert out.total == 1
    assert out.imported == 1


def test_mode_urls_libelle_depuis_la_base_sinon_l_url(db_session, monkeypatch):
    """Le libellé est cosmétique (ligne de progression) : repli sur l'URL."""
    _course(db_session, "Triathlon de Nantes", "https://k/en-base")
    libelles: list[str] = []

    class _Reporter:
        """Capture les libellés annoncés. Signatures : cf. `ProgressReporter`."""

        def batch_start(self, total: int) -> None:
            pass

        def item_start(self, index: int, label: str) -> None:
            libelles.append(label)

        def item_progress(self, done: int, total: int) -> None:
            pass

        def item_done(self, imported: int, skipped: int, error: str | None) -> None:
            pass

        def batch_end(self) -> None:
            pass

    def _iter(db, url, settings, force=False):
        yield {"phase": "done", "imported": 0, "skipped": 0, "total": 0}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    rescrape_service.run_rescrape_db(
        db_session, _settings(), delay=0.0,
        urls=["https://k/en-base", "https://k/inconnue"],
        reporter=_Reporter(),
    )

    assert libelles == ["klikego · Triathlon de Nantes", "https://k/inconnue"]


def test_mode_urls_dedoublonne_les_formes_equivalentes(db_session, monkeypatch):
    """Casse d'hôte et slash final : une seule épreuve scrapée."""
    vus: list[str] = []

    def _iter(db, url, settings, force=False):
        vus.append(url)
        yield {"phase": "done", "imported": 0, "skipped": 0, "total": 0}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    out = rescrape_service.run_rescrape_db(
        db_session, _settings(), delay=0.0,
        urls=["https://Klikego.com/e/1", "https://klikego.com/e/1/"],
    )

    assert vus == ["https://Klikego.com/e/1"]
    assert out.total == 1


def test_mode_urls_dry_run_liste_sans_scraper(db_session, monkeypatch):
    def _iter(db, url, settings, force=False):
        raise AssertionError("aucun scrape en dry-run")

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    out = rescrape_service.run_rescrape_db(
        db_session, _settings(), dry_run=True, delay=0.0, urls=["https://k/1"]
    )

    assert out.dry_run_urls == ["https://k/1"]
    assert out.total == 1


def test_mode_urls_vide_cible_zero_epreuve(db_session, monkeypatch):
    """Liste d'échecs vide en fin de boucle de rejeu : rien à faire, pas la base."""
    def _iter_all_interdit(*args, **kwargs):
        raise AssertionError("iter_all ne doit pas être appelé en mode urls")

    monkeypatch.setattr(course_repository, "iter_all", _iter_all_interdit)

    out = rescrape_service.run_rescrape_db(db_session, _settings(), delay=0.0, urls=[])

    assert out.total == 0
    assert out.echec_total is False


def test_mode_urls_respecte_limit(db_session, monkeypatch):
    vus: list[str] = []

    def _iter(db, url, settings, force=False):
        vus.append(url)
        yield {"phase": "done", "imported": 0, "skipped": 0, "total": 0}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    out = rescrape_service.run_rescrape_db(
        db_session, _settings(), delay=0.0, limit=1,
        urls=["https://k/1", "https://k/2"],
    )

    assert vus == ["https://k/1"]
    assert out.total == 1
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `uv run pytest tests/test_services/test_rescrape_service.py -q`
Expected: FAIL — `TypeError: run_rescrape_db() got an unexpected keyword argument 'urls'`.

- [ ] **Step 3: Implémenter le second mode de sélection**

Dans `backend/app/services/rescrape_service.py`, ajouter ce helper juste après `_dedupe_par_url` :

```python
def _items_depuis_urls(db: Session, urls: list[str]) -> list[BatchItem]:
    """Épreuves ciblées **explicitement** : la base ne sert plus qu'à libeller.

    Une URL inconnue en base est le cas **nominal** du rejeu d'un échec
    d'import : l'épreuve fautive n'a rien persisté, elle est absente de la table
    `course`. La sélectionner via `iter_all` porterait sur zéro épreuve et
    sortirait en code 0 — un silence trompeur. On soumet donc les URLs telles
    quelles au batch, connues ou non.

    Le libellé est purement cosmétique (ligne de progression) : quand la course
    est inconnue, il retombe sur l'URL, sans avertissement ni dégradation.
    """
    items: list[BatchItem] = []
    for url in sheet_source.dedupe_links(urls):
        course = course_repository.get_latest_by_source_url(db, url)
        label = f"{course.provider} · {course.name}" if course else url
        items.append(BatchItem(url=url, label=label))
    return items
```

Puis remplacer le corps de `run_rescrape_db` (lignes 89-114) par :

```python
    if urls is not None:
        items = _items_depuis_urls(db, urls)
    else:
        courses = course_repository.iter_all(
            db, provider=provider, older_than_days=older_than
        )
        epreuves = _dedupe_par_url([c for c in courses if c.source_url])
        # Le nom de la course vient de la DB : on peut libeller proprement.
        items = [
            BatchItem(url=c.source_url, label=f"{c.provider} · {c.name}")
            for c in epreuves
        ]
    if limit is not None:
        items = items[:limit]

    outcome = RescrapeOutcome(total=len(items))
    if dry_run:
        # Charge utile réservée au dry-run : hors dry-run, embarquer l'URL de
        # chaque épreuve gonflerait la sortie --json de plusieurs dizaines de Ko.
        outcome.dry_run_urls = [item.url for item in items]
        return outcome

    totals = run_batch(db, items, settings, force=True, delay=delay, reporter=reporter)

    outcome.imported = totals.imported
    outcome.skipped = totals.skipped
    outcome.errors = totals.errors
    outcome.processed = totals.processed
    outcome.interrupted = totals.interrupted
    return outcome
```

Ajouter le paramètre à la signature, après `reporter` :

```python
    reporter: ProgressReporter | None = None,
    urls: list[str] | None = None,
) -> RescrapeOutcome:
```

Et compléter la docstring de `run_rescrape_db` par ce paragraphe :

```
    Deux modes de sélection, un seul batch en aval. `urls=None` : les épreuves
    viennent de la base (`provider`, `older_than`, dédup par URL). `urls`
    fourni : la base **n'est pas interrogée pour sélectionner**, chaque URL
    devient une épreuve — c'est ce qui permet de rejouer un échec d'import, dont
    l'épreuve n'existe pas en base. `limit` borne la liste finale dans les deux
    cas ; `force=True`, `delay`, dry-run et Ctrl-C sont inchangés.
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `uv run pytest tests/test_services/test_rescrape_service.py -q`
Expected: PASS — tous les tests, anciens compris (le mode base est inchangé).

- [ ] **Step 5: Commit**

```bash
git add app/services/rescrape_service.py tests/test_services/test_rescrape_service.py
git commit -m "feat(rescrape): sélection d'épreuves par URL, sans passer par la base"
```

---

### Task 3 : Détail des échecs dans le bilan de `rescrape-db`

**Files:**
- Modify: `backend/app/services/rescrape_service.py:42-68` (dataclass `RescrapeOutcome`) et l'affectation des totaux
- Modify: `backend/app/cli/reports.py:65-101`
- Test: `backend/tests/test_cli/test_reports.py`

**Interfaces:**
- Consumes: `batch.BatchFailure(url: str, label: str, message: str)`, `batch.BatchTotals.failures: list[BatchFailure]`.
- Produces: `RescrapeOutcome.failures: list[BatchFailure]` (sérialisé par `asdict()` dans la charge `--json`), `reports._lignes_echecs(outcome: Outcome) -> list[str]`.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `backend/tests/test_cli/test_reports.py` (aucun import à ajouter : `render_rescrape_report`, `RescrapeOutcome` et `BatchFailure` y sont déjà importés) :

```python
def test_rescrape_report_liste_les_echecs():
    """« Épreuves en erreur : 2 » dit *combien*, pas *lesquelles*. Sans le
    détail, une troisième tentative suppose de relire le terminal à la main."""
    outcome = RescrapeOutcome(
        total=3, errors=2, imported=10,
        failures=[
            BatchFailure(url="https://k/1", label="klikego · A", message="503"),
            BatchFailure(url="https://k/2", label="klikego · B", message="timeout"),
        ],
    )

    rapport = render_rescrape_report(outcome, dry_run=False)

    assert "Épreuves en erreur (détail) :" in rapport
    assert "  - https://k/1 : 503" in rapport
    assert "  - https://k/2 : timeout" in rapport


def test_rescrape_report_sans_echec_n_affiche_pas_le_bloc():
    rapport = render_rescrape_report(RescrapeOutcome(total=3, imported=10), dry_run=False)

    assert "détail" not in rapport
```

Ajouter à `backend/tests/test_cli/test_commands.py`, dans la section `# --- rescrape-db` :

```python
def test_rescrape_db_json_embarque_les_echecs(monkeypatch):
    """La boucle de rejeu (`--json | jq -r '.failures[].url'`) en dépend."""
    from app.services.batch import BatchFailure

    _brancher_rescrape(
        monkeypatch,
        RescrapeOutcome(
            total=2, errors=1, imported=3,
            failures=[BatchFailure(url="https://k/1", label="klikego · A", message="503")],
        ),
    )

    result = runner.invoke(app, ["rescrape-db", "--json"])

    assert result.exit_code == 0
    charge = json.loads(result.stdout)
    assert charge["failures"] == [
        {"url": "https://k/1", "label": "klikego · A", "message": "503"}
    ]
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `uv run pytest tests/test_cli/test_reports.py tests/test_cli/test_commands.py -q`
Expected: FAIL — `TypeError: RescrapeOutcome.__init__() got an unexpected keyword argument 'failures'`.

- [ ] **Step 3: Ajouter le champ puis factoriser le rendu**

Dans `backend/app/services/rescrape_service.py`, importer `BatchFailure` :

```python
from app.services.batch import BatchFailure, BatchItem, est_echec_total, run_batch
```

Ajouter le champ à `RescrapeOutcome`, après `dry_run_urls` :

```python
    #: Épreuves fautives (URL + cause). Borné aux seuls échecs : léger,
    #: contrairement à la liste de toutes les épreuves. `asdict()` l'embarque
    #: dans `--json`, ce qui referme la boucle de rejeu sans fichier d'état.
    failures: list[BatchFailure] = field(default_factory=list)
```

Et le recopier depuis les totaux, à côté des autres compteurs :

```python
    outcome.errors = totals.errors
    outcome.failures = totals.failures
```

Dans `backend/app/cli/reports.py`, ajouter le helper juste avant `render_sheet_report` :

```python
def _lignes_echecs(outcome: Outcome) -> list[str]:
    """Le détail des épreuves fautives, commun aux deux commandes.

    Le compteur « Épreuves en erreur : N » dit *combien* ; ce bloc dit
    *lesquelles* et *pourquoi*, sans avoir à rejouer le batch. Il alimente aussi
    la boucle de rejeu de `rescrape-db --urls-from -`. Deux rendus divergeaient
    sans raison : `run_batch` collecte ces échecs pour les deux commandes.
    """
    if not outcome.failures:
        return []
    lignes = ["Épreuves en erreur (détail) :"]
    lignes.extend(f"  - {f.url} : {f.message}" for f in outcome.failures)
    return lignes
```

Dans `render_sheet_report`, remplacer le bloc `if outcome.failures:` (lignes 72-77) par :

```python
        lignes.extend(_lignes_echecs(outcome))
```

Dans `render_rescrape_report`, remplacer la branche `else` par :

```python
    else:
        lignes.extend(_lignes_compteurs(outcome))
        lignes.extend(_lignes_echecs(outcome))
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `uv run pytest tests/test_cli tests/test_services -q`
Expected: PASS — y compris les tests existants de `render_sheet_report` (rendu identique).

- [ ] **Step 5: Commit**

```bash
git add app/services/rescrape_service.py app/cli/reports.py tests/test_cli/test_reports.py tests/test_cli/test_commands.py
git commit -m "feat(cli): rescrape-db liste les épreuves en erreur (texte et --json)"
```

---

### Task 4 : Options `--url` / `--urls-from` sur `rescrape-db`

**Files:**
- Modify: `backend/app/cli/commands/rescrape_db.py`
- Test: `backend/tests/test_cli/test_commands.py`

**Interfaces:**
- Consumes: `url_sources.charger_urls`, `url_sources.valider_ciblage_exclusif` (Task 1) ; `rescrape_service.run_rescrape_db(..., urls=...)` (Task 2).
- Produces: rien pour les tâches suivantes.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `backend/tests/test_cli/test_commands.py`, section `# --- rescrape-db` :

```python
def test_rescrape_db_url_transmise_au_service(monkeypatch):
    espion = _brancher_rescrape(monkeypatch, RescrapeOutcome(total=2))

    result = runner.invoke(
        app, ["rescrape-db", "--url", "https://k/1", "--url", "https://k/2"]
    )

    assert result.exit_code == 0
    assert espion.kwargs["urls"] == ["https://k/1", "https://k/2"]


def test_rescrape_db_urls_from_fichier(monkeypatch, tmp_path):
    fichier = tmp_path / "echecs.txt"
    fichier.write_text("https://k/1\n# commentaire\n\n", encoding="utf-8")
    espion = _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(app, ["rescrape-db", "--urls-from", str(fichier)])

    assert result.exit_code == 0
    assert espion.kwargs["urls"] == ["https://k/1"]


def test_rescrape_db_urls_from_stdin(monkeypatch):
    """`… --json | jq -r '.failures[].url' | … --urls-from -`, sans fichier."""
    espion = _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(app, ["rescrape-db", "--urls-from", "-"], input="https://k/1\n")

    assert result.exit_code == 0
    assert espion.kwargs["urls"] == ["https://k/1"]


def test_rescrape_db_sans_url_reste_en_mode_base(monkeypatch):
    espion = _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(app, ["rescrape-db"])

    assert result.exit_code == 0
    assert espion.kwargs["urls"] is None


def test_rescrape_db_liste_vide_cible_zero_epreuve(monkeypatch, tmp_path):
    """Fichier vide → « rien à faire », code 0 : la boucle de rejeu converge."""
    fichier = tmp_path / "vide.txt"
    fichier.write_text("", encoding="utf-8")
    espion = _brancher_rescrape(monkeypatch, RescrapeOutcome(total=0))

    result = runner.invoke(app, ["rescrape-db", "--urls-from", str(fichier)])

    assert result.exit_code == 0
    assert espion.kwargs["urls"] == []


def test_rescrape_db_url_avec_provider_est_une_erreur_d_usage(monkeypatch):
    espion = _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(
        app, ["rescrape-db", "--url", "https://k/1", "--provider", "klikego"]
    )

    assert result.exit_code == 2
    assert espion.args == ()  # aucun travail engagé


def test_rescrape_db_url_avec_older_than_est_une_erreur_d_usage(monkeypatch):
    _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(
        app, ["rescrape-db", "--url", "https://k/1", "--older-than", "30"]
    )

    assert result.exit_code == 2


def test_rescrape_db_url_non_http_est_une_erreur_d_usage(monkeypatch):
    _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(app, ["rescrape-db", "--url", "pas-une-url"])

    assert result.exit_code == 2


def test_rescrape_db_urls_from_introuvable_est_une_erreur_d_usage(monkeypatch, tmp_path):
    _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(app, ["rescrape-db", "--urls-from", str(tmp_path / "absent.txt")])

    assert result.exit_code == 2


def test_rescrape_db_url_reste_compatible_avec_limit(monkeypatch):
    """`--limit` ne sélectionne rien : il borne la liste finale."""
    espion = _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(
        app, ["rescrape-db", "--url", "https://k/1", "--url", "https://k/2", "--limit", "1"]
    )

    assert result.exit_code == 0
    assert espion.kwargs["limit"] == 1
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `uv run pytest tests/test_cli/test_commands.py -q -k "url"`
Expected: FAIL — `No such option: --url` (exit_code 2 partout, y compris là où 0 est attendu).

- [ ] **Step 3: Câbler les options**

Dans `backend/app/cli/commands/rescrape_db.py`, ajouter l'import :

```python
from app.cli.url_sources import charger_urls, valider_ciblage_exclusif
```

Ajouter les deux options, juste après `provider` :

```python
    url: list[str] = typer.Option(
        [], "--url",
        help="Cible une épreuve précise (répétable). Court-circuite la base.",
    ),
    urls_from: str | None = typer.Option(
        None, "--urls-from",
        help="Fichier d'URLs (une par ligne), ou « - » pour lire stdin.",
    ),
```

Et remplacer le corps de la fonction par :

```python
    urls = charger_urls(url, urls_from)
    valider_ciblage_exclusif(urls=urls, provider=provider, older_than=older_than)

    settings = get_settings()
    reporter = select_reporter(no_progress=no_progress or dry_run, plain=plain)

    with session_scope() as db:
        outcome = rescrape_service.run_rescrape_db(
            db, settings,
            dry_run=dry_run, older_than=older_than, provider=provider,
            limit=limit, delay=delay, reporter=reporter, urls=urls,
        )
```

Compléter la docstring de la commande par :

```
    Deux modes de sélection, exclusifs l'un de l'autre : par filtre sur la base
    (`--provider`, `--older-than`), ou par URL explicite (`--url`,
    `--urls-from`). Le second court-circuite la base — c'est ce qui permet de
    rejouer une épreuve en échec à l'import, absente de la table `course` :

        … import-sheet --json | jq -r '.failures[].url' \\
          | … rescrape-db --urls-from -
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `uv run pytest tests/test_cli -q`
Expected: PASS — tous les tests CLI.

- [ ] **Step 5: Vérifier la suite complète et le lint**

Run: `uv run pytest -m "not integration" -q && uv run ruff check .`
Expected: tous les tests passent, `All checks passed!`

- [ ] **Step 6: Vérifier le comportement en vrai (dry-run, zéro réseau)**

Run:
```bash
printf 'https://exemple.test/epreuve-inconnue\n# commentée\n' \
  | uv run python -m app.cli rescrape-db --urls-from - --dry-run
echo "code : $?"
```
Expected: « Épreuves ciblées : 1 » + la ligne `- https://exemple.test/epreuve-inconnue`, code 0 — l'URL est inconnue en base et c'est le cas nominal.

Run: `uv run python -m app.cli rescrape-db --url https://exemple.test/x --provider klikego; echo "code : $?"`
Expected: message d'erreur + usage sur stderr, code 2.

- [ ] **Step 7: Commit**

```bash
git add app/cli/commands/rescrape_db.py tests/test_cli/test_commands.py
git commit -m "feat(cli): options --url et --urls-from sur rescrape-db"
```

---

### Task 5 : Documentation

**Files:**
- Modify: `AGENTS.md` (bloc « CLI de batch » et paragraphe « Détail des épreuves en erreur »)
- Modify: `README.md` (seulement si la CLI y est décrite — à vérifier)

**Interfaces:**
- Consumes: le comportement livré par les tâches 1 à 4.
- Produces: rien.

- [ ] **Step 1: Vérifier si le README décrit la CLI**

Run: `grep -n "app.cli\|rescrape-db\|import-sheet" README.md`
Expected: aucune sortie (la spec l'annonce). Si des lignes remontent, y appliquer les mêmes ajouts qu'à `AGENTS.md`.

- [ ] **Step 2: Compléter le bloc de commandes d'`AGENTS.md`**

Dans le bloc ```bash « CLI de batch (depuis backend/) », ajouter après la ligne `rescrape-db --json | jq` :

```bash
uv run python -m app.cli rescrape-db --url <url> --url <url2>   # cible des épreuves précises
uv run python -m app.cli rescrape-db --urls-from echecs.txt     # ou « - » pour lire stdin
# rejeu des échecs, sans fichier intermédiaire ni état persistant :
uv run python -m app.cli import-sheet --json | jq -r '.failures[].url' \
  | uv run python -m app.cli rescrape-db --urls-from -
```

- [ ] **Step 3: Corriger le paragraphe « Détail des épreuves en erreur »**

Dans `AGENTS.md`, section « Sorties de la CLI », la phrase « `import-sheet` liste donc les échecs (URL + cause) sous "Épreuves en erreur (détail) :" » est devenue fausse. La remplacer par :

```
**Détail des épreuves en erreur** : le compteur « Épreuves en erreur : N » dit
*combien*, pas *lesquelles*. **Les deux commandes** listent donc les échecs
(URL + cause) sous « Épreuves en erreur (détail) : » — la boucle `batch`
collecte un `BatchFailure(url, label, message)` par épreuve fautive (phase
`error` ou exception rattrapée). Ce détail est aussi dans la charge `--json`
(`failures`), et borné aux seuls échecs : il reste léger, contrairement à la
liste de toutes les épreuves. C'est lui qui referme la boucle de rejeu
(`… --json | jq -r '.failures[].url' | … rescrape-db --urls-from -`), sans
fichier d'état. À distinguer des **liens non supportés** (`ignored_by_host`,
suivis dans #33) : ces derniers ne sont **jamais** soumis au batch, ils ne
comptent ni en succès ni en échec.
```

- [ ] **Step 4: Documenter les deux modes de sélection**

Toujours dans `AGENTS.md`, sous le paragraphe « Vocabulaire », ajouter :

```
**Deux modes de sélection pour `rescrape-db`**, exclusifs l'un de l'autre :
par filtre sur la base (`--provider`, `--older-than`), ou par URL explicite
(`--url`, répétable, et `--urls-from <fichier|->`). Le second **court-circuite
la base** : une URL inconnue en table `course` est scrapée normalement, sans
avertissement — c'est le cas nominal du rejeu d'un échec d'import, dont
l'épreuve n'a rien persisté. Les combiner est une erreur d'usage (code 2) : ce
sont deux modes, pas des filtres à composer. `--limit` reste compatible avec les
deux : il borne la liste finale, il ne sélectionne rien.
```

- [ ] **Step 5: Relire le rendu**

Run: `grep -n "urls-from" AGENTS.md`
Expected: les lignes ajoutées aux étapes 2, 3 et 4 remontent.

- [ ] **Step 6: Commit**

```bash
git add AGENTS.md
git commit -m "docs: documente le ciblage d'épreuves par URL en CLI"
```

---

## Vérification finale

- [ ] Run: `uv run pytest -m "not integration" -q`
      Expected: 0 failed.
- [ ] Run: `uv run ruff check .`
      Expected: `All checks passed!`
- [ ] Run: `git log --oneline main..HEAD`
      Expected: 5 commits, un par tâche.
