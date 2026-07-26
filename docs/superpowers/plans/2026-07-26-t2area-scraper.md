# Scraper `fftri.t2area.com` (T2Area / FFTRI) — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** ajouter un provider `t2area` qui importe un classement complet de
`fftri.t2area.com` (plateforme officielle FFTRI) en une requête, et charge les
splits des seuls membres du TCN.

**Architecture :** un module `app/scrapers/t2area.py` sur le patron des autres
scrapers HTML (cf. `chronoplace.py`) : fonctions pures de parsing (BeautifulSoup +
lxml) + une seule fonction d'orchestration `scrape_event_all(url)` qui ouvre un
`httpx.Client`. Le module est enregistré dans `scrapers/registry.py` via un
`T2AreaProvider` à allowlist de host. Aucun Playwright, aucune API à
rétro-concevoir : la page est server-rendered et non paginée.

**Tech Stack :** Python 3.13, uv, httpx, BeautifulSoup/lxml, pytest, ruff.

Design de référence : `docs/superpowers/specs/2026-07-26-t2area-scraper-design.md`
(issue [#51](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/51)).

---

## Global Constraints

- Toutes les commandes se lancent **depuis `backend/`**. Aucun venv à activer :
  `uv run …` s'en charge.
- **Langue** : code, docstrings, commentaires, messages de log et noms de tests
  en **français avec accents**. Les noms de tests suivent le style du dépôt :
  `def test_parse_url_tronque_une_fiche_individuelle():`.
- **Tests unitaires sans réseau.** Le seul appel réseau autorisé est derrière le
  marker `@pytest.mark.integration` (exclu de la CI par défaut).
- Commits **Conventional Commits**, un par tâche, suffixés `(#51)`.
- Lint : `uv run ruff check .` doit passer. `E501` (longueur de ligne) est
  volontairement désactivé dans `backend/pyproject.toml`, mais `F` (imports
  inutilisés) et `I` (tri des imports) sont actifs : n'ajouter un import qu'à la
  tâche qui s'en sert, et dans le bon groupe (stdlib / tiers / `app.*` / relatif).
- **Ne jamais réimplémenter l'appartenance au club** : `app.core.club.is_tcn` est
  la définition unique (issue #76).
- Les temps restent des **chaînes** `"HH:MM:SS"`, normalisées via
  `app/scrapers/utils.normalize_time`.
- Nom du provider, exactement : `t2area`.

## Écarts au design (constatés sur la source réelle le 2026-07-26)

Trois points où ce plan diverge du design. Ils viennent d'un re-sondage des pages
réelles (La Baule M 2022, Nevers Duathlon M 2022, Lac du Bouchet L 2025/2026,
Vichy L 2024) et **priment** sur le design.

1. **Colonnes lues par libellé d'en-tête, pas par position.** Le §4 du design
   liste 8 colonnes ; l'en-tête réel en porte **10** — `id_league` et `league`
   s'intercalent entre `Clt/CAT` et `Détails` :

   ```
   Clt | Clt/F | Temps | Nom | Club | CAT | Clt/CAT | id_league | league | Détails
   ```

   Une lecture positionnelle calée sur le tableau du design lirait la ligue à la
   place du lien de fiche. En-tête identique sur les 5 éditions re-sondées
   (2022 → 2026). On indexe donc les colonnes par leur libellé normalisé.

2. **Pas de classe `.edition`.** Le §2.2 du design évoque « les liens
   `.edition` » de la page d'épreuve ; les liens réels portent `class="btn-fx-1"`.
   `_resolve_annee` fait donc une regex sur les `href` bruts
   (`…/<épreuve>/(\d{4})\.html`) et prend le maximum — insensible au décor.

3. **`source_url` = l'URL canonique de l'édition sur chaque `ScrapedResult`**,
   pas l'URL demandée. Une fiche individuelle et son édition désignent le même
   classement ; toutes les lignes d'un même appel partagent donc la même URL —
   cohérence purement *interne* au scrape. **Correction (revue de branche) :**
   la formulation initiale prétendait que ça rendait « le `rescrape-db` suivant
   idempotent » — c'est factuellement faux. `mapping.get_or_create_course`
   persiste `Course.source_url = event_url or scraped.source_url`, et
   `event_url` est toujours l'URL de l'**appelant** (`import_service._Persister`
   la reçoit déjà validée) : `scraped.source_url` n'a aucun consommateur en
   aval. Si le Sheet donne une URL de fiche, `Course.source_url` **est** cette
   URL de fiche — l'idempotence observée vient de ce que ce scraper la tronque
   identiquement à chaque passage, pas d'une réécriture de la clé stockée. Si
   l'idempotence de la clé elle-même était voulue (stocker la forme canonique
   en base plutôt que l'URL de l'appelant), ce serait une modification de la
   couche d'import (`mapping.get_or_create_course` / `import_service`), hors
   périmètre de #51. C'est la seule décision de ce plan qui n'est pas dans le
   design.

4. **Les tests de détection vivent dans `tests/test_t2area.py`**, pas dans
   `tests/test_registry.py` comme l'annonce le §7 : c'est la convention du
   dernier provider ajouté (`test_chronoplace.py` porte ses trois tests de
   registre). `test_registry.py` reste sur ce qu'il teste — le mécanisme du
   registre lui-même, pas les providers un à un.

Restent vraies et vérifiées : absence totale de pagination (901 lignes en une
requête), `00:00:00` sur les DNF, `DQ` absent de `_STATUS_TOKENS`, libellés
d'accordéon `CàP 1` / `CàP 2` en duathlon, clés de fiche `bib-566` / `A44719` /
`id-1228489`, mention « Résultats produits par X » liant l'accueil du
chronométreur, édition inexistante → redirection 303 vers `/calendrier.html`.

## File Structure

| Fichier | Responsabilité |
| --- | --- |
| `backend/app/scrapers/t2area.py` | **Créé.** Tout le scraper : analyse d'URL, lecture du classement, lecture des fiches de splits, orchestration. |
| `backend/app/scrapers/utils.py` | **Modifié.** Une entrée `"dq"` dans `_STATUS_TOKENS`. |
| `backend/app/scrapers/registry.py` | **Modifié.** `T2AreaProvider` + import + entrée dans `PROVIDERS`. |
| `backend/tests/test_t2area.py` | **Créé.** Tous les tests unitaires du scraper. |
| `backend/tests/fixtures/t2area_*.html` | **Créés.** 6 extraits réels réduits. |
| `backend/tests/test_scrapers_utils.py` | **Modifié.** Cas `DQ`. |
| `backend/tests/test_integration_scrapers.py` | **Modifié.** URL réelle + test dédié. |
| `AGENTS.md` | **Modifié.** Section « Fournisseurs supportés ». |

Le scraper tient dans **un seul module** : c'est la convention du dépôt (un
fichier par provider, cf. `chronoplace.py`, `raceresult.py`), et les ~330 lignes
attendues restent sous la taille de `chronoplace.py`.

---

### Task 1 : `DQ` reconnu comme disqualification

Un disqualifié de La Baule 2022 (ALLARD Pierre, colonne `Clt` = `DQ`) serait
compté DNF par l'heuristique de `mapping.derive_status`. `utils` connaît `dsq`,
`disq`, `disqualifie`, mais pas `dq`. Tâche préalable et indépendante du scraper.

**Files:**
- Modify: `backend/app/scrapers/utils.py:135-163` (dict `_STATUS_TOKENS`)
- Test: `backend/tests/test_scrapers_utils.py:9-34` (parametrize existante)

**Interfaces:**
- Consomme : rien.
- Produit : `derive_status_from_label("DQ") == "DSQ"` — utilisé par la Task 3.

- [ ] **Step 1 : écrire le test qui échoue**

Dans `backend/tests/test_scrapers_utils.py`, ajouter le cas dans la liste
`@pytest.mark.parametrize` qui précède `test_derive_status_from_label_recognized`,
juste après la ligne `("Disqualifié", "DSQ"),` :

```python
    # `DQ` : forme employée par fftri.t2area.com dans la colonne Clt (#51).
    ("DQ", "DSQ"),
    ("dq", "DSQ"),
```

- [ ] **Step 2 : lancer le test, vérifier qu'il échoue**

```bash
uv run pytest tests/test_scrapers_utils.py -k derive_status -v
```

Attendu : ÉCHEC sur `[DQ-DSQ]` et `[dq-DSQ]` avec `assert '' == 'DSQ'`.

- [ ] **Step 3 : implémenter**

Dans `backend/app/scrapers/utils.py`, dans `_STATUS_TOKENS`, sous le commentaire
`# Disqualification`, ajouter après `"disq": STATUS_DSQ,` :

```python
    # `DQ` : forme de fftri.t2area.com (colonne Clt), cf. #51.
    "dq": STATUS_DSQ,
```

- [ ] **Step 4 : lancer les tests, vérifier qu'ils passent**

```bash
uv run pytest tests/test_scrapers_utils.py -v
```

Attendu : tout passe.

- [ ] **Step 5 : commit**

```bash
git add app/scrapers/utils.py tests/test_scrapers_utils.py
git commit -m "fix(scrapers): reconnaît DQ comme disqualification (#51)"
```

---

### Task 2 : analyse et résolution d'URL

Quatre profondeurs d'URL, c'est le nombre de segments qui dit le niveau :

```
/calendrier/<événement>.html                          événement → refusé
/calendrier/<événement>/<épreuve>.html                épreuve   → année à résoudre
/calendrier/<événement>/<épreuve>/<année>.html        édition   → le classement
/calendrier/<événement>/<épreuve>/<année>/<clé>.html  fiche     → tronquée vers l'édition
```

**Files:**
- Create: `backend/app/scrapers/t2area.py`
- Create: `backend/tests/fixtures/t2area_epreuve_labaule_m.html`
- Create: `backend/tests/test_t2area.py`

**Interfaces:**
- Consomme : rien.
- Produit, pour les tâches suivantes :
  - `BASE_URL: str`, `HOST: str`, `HEADERS: dict[str, str]`
  - `_parse_url(url: str) -> tuple[str, str, str]` → `(événement, épreuve, année)`,
    année `""` si absente
  - `_epreuve_url(evenement: str, epreuve: str) -> str`
  - `_edition_url(evenement: str, epreuve: str, annee: str) -> str`
  - `_fetch(client: httpx.Client, url: str) -> str`
  - `_resolve_annee(client: httpx.Client, evenement: str, epreuve: str) -> str`
  - `_norm(text: str) -> str` (minuscule, sans accents, espaces aplatis)

- [ ] **Step 1 : créer la fixture de page d'épreuve**

Créer `backend/tests/fixtures/t2area_epreuve_labaule_m.html` :

```html
<!-- Extrait réel de https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m.html (liens d'éditions seuls, décor retiré) -->
<html lang="fr"><body>
<h1>Triathlon de La Baule - M</h1>
<div class="uk-grid">
<a class="btn-fx-1" href="https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2022.html"><span>Résultats 2022</span></a>
<a class="btn-fx-1" href="https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2021.html"><span>Résultats 2021</span></a>
<a class="btn-fx-1" href="https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2019.html"><span>Résultats 2019</span></a>
<a class="btn-fx-1" href="https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2018.html"><span>Résultats 2018</span></a>
<a class="btn-fx-1" href="https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2017.html"><span>Résultats 2017</span></a>
<a class="btn-fx-1" href="https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2016.html"><span>Résultats 2016</span></a>
<a class="btn-fx-1" href="https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2015.html"><span>Résultats 2015</span></a>
</div>
</body></html>
```

- [ ] **Step 2 : écrire les tests qui échouent**

Créer `backend/tests/test_t2area.py` :

```python
"""
Tests unitaires pour scrapers/t2area.py (sans réseau).

Les fixtures sont des extraits réels de fftri.t2area.com (2026-07-26), réduits à
quelques lignes ; les attributs purement décoratifs ont été retirés, la structure
(`#resultList`, en-tête à 10 colonnes, accordéon des fiches) est intacte.
"""
from pathlib import Path

import httpx
import pytest

from app.scrapers import t2area

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


EPREUVE_LABAULE = _fixture("t2area_epreuve_labaule_m.html")

URL_EDITION = (
    "https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2022.html"
)
URL_FICHE = (
    "https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2022/bib-566.html"
)
URL_EPREUVE = "https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m.html"
URL_EVENEMENT = "https://fftri.t2area.com/calendrier/triathlon-de-la-baule.html"


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text, self.status_code = text, status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPError(f"HTTP {self.status_code}")


class FakeClient:
    """Client HTTP factice : sert les fixtures et enregistre les URLs demandées."""

    def __init__(self, pages: dict[str, str] | None = None, defaut: FakeResponse | None = None):
        self.pages = pages or {}
        self.defaut = defaut or FakeResponse("<html>vide</html>")
        self.calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url: str):
        self.calls.append(url)
        for motif, page in self.pages.items():
            if motif in url:
                return page if isinstance(page, FakeResponse) else FakeResponse(page)
        return self.defaut


def test_parse_url_edition():
    assert t2area._parse_url(URL_EDITION) == ("triathlon-de-la-baule", "triathlon-m", "2022")


def test_parse_url_tronque_une_fiche_individuelle():
    """Le cas réel du Sheet : un lien de fiche pointe l'édition qui la contient."""
    assert t2area._parse_url(URL_FICHE) == ("triathlon-de-la-baule", "triathlon-m", "2022")


def test_parse_url_epreuve_sans_annee():
    assert t2area._parse_url(URL_EPREUVE) == ("triathlon-de-la-baule", "triathlon-m", "")


def test_parse_url_refuse_un_evenement():
    """Les épreuves d'un événement ont des dernières éditions d'années différentes."""
    with pytest.raises(ValueError, match="pointez une épreuve"):
        t2area._parse_url(URL_EVENEMENT)


def test_parse_url_refuse_un_autre_host():
    with pytest.raises(ValueError, match="hors fftri.t2area.com"):
        t2area._parse_url("https://autre.t2area.com/calendrier/x/y/2022.html")


def test_parse_url_refuse_une_page_hors_calendrier():
    with pytest.raises(ValueError, match="non reconnue"):
        t2area._parse_url("https://fftri.t2area.com/clubs/triathlon-club-nantais.html")


def test_parse_url_refuse_une_annee_illisible():
    with pytest.raises(ValueError, match="Année illisible"):
        t2area._parse_url(
            "https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/saison.html"
        )


def test_parse_url_refuse_une_profondeur_inconnue():
    with pytest.raises(ValueError, match="non reconnue"):
        t2area._parse_url(
            "https://fftri.t2area.com/calendrier/a/b/2022/bib-1/extra.html"
        )


def test_edition_url():
    assert t2area._edition_url("triathlon-de-la-baule", "triathlon-m", "2022") == URL_EDITION


def test_epreuve_url():
    assert t2area._epreuve_url("triathlon-de-la-baule", "triathlon-m") == URL_EPREUVE


def test_resolve_annee_prend_la_plus_recente():
    """La page d'épreuve liste toutes ses éditions ; la dernière est la plus récente."""
    client = FakeClient({"/triathlon-m.html": EPREUVE_LABAULE})

    assert t2area._resolve_annee(client, "triathlon-de-la-baule", "triathlon-m") == "2022"
    assert client.calls == [URL_EPREUVE]


def test_resolve_annee_sans_edition_leve():
    """Épreuve créée mais jamais courue : erreur explicite, pas de classement vide."""
    client = FakeClient({"/triathlon-m.html": "<html><body>rien</body></html>"})

    with pytest.raises(ValueError, match="Aucune édition publiée"):
        t2area._resolve_annee(client, "triathlon-de-la-baule", "triathlon-m")


def test_fetch_erreur_serveur_remonte():
    client = FakeClient(defaut=FakeResponse("", 500))
    with pytest.raises(httpx.HTTPError):
        t2area._fetch(client, URL_EDITION)
```

- [ ] **Step 3 : lancer les tests, vérifier qu'ils échouent**

```bash
uv run pytest tests/test_t2area.py -v
```

Attendu : ÉCHEC à la collecte, `ImportError: cannot import name 't2area'`.

- [ ] **Step 4 : implémenter**

Créer `backend/app/scrapers/t2area.py` :

```python
"""
Scraper fftri.t2area.com — plateforme de résultats officielle de la FFTRI.

Un Joomla qui rend le classement complet en HTML server-rendered : une requête
ramène toutes les lignes (901 sur La Baule M 2022), il n'y a **aucune
pagination**, donc ni API à rétro-concevoir ni Playwright.

La profondeur du chemin dit à quel niveau on est :

    /calendrier/<événement>.html                          événement (refusé)
    /calendrier/<événement>/<épreuve>.html                épreuve (année à résoudre)
    /calendrier/<événement>/<épreuve>/<année>.html        édition ← le classement
    /calendrier/<événement>/<épreuve>/<année>/<clé>.html  fiche individuelle

Flux (cf. docs/superpowers/specs/2026-07-26-t2area-scraper-design.md) :
  1. `_parse_url`      → (événement, épreuve, année) ; une fiche est tronquée
                         vers son édition (le cas réel du Sheet)
  2. `_resolve_annee`  → année absente : 1 GET sur l'épreuve, on prend la plus récente
  3. `_fetch`          → GET du classement
  4. `_parse_edition`  → `<table id="resultList">` → N `ScrapedResult`
  5. `_parse_fiche`    → pour les **seules** lignes `is_tcn` : GET de la fiche,
                         accordéon → splits (25 requêtes sur La Baule, pas 901)
"""
import logging
import re
from datetime import date
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.club import is_tcn

from .base import ScrapedResult
from .classify import classify_event_type
from .utils import (
    derive_status_from_label,
    normalize_rank,
    normalize_time,
    split_athlete_name,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://fftri.t2area.com"
HOST = "fftri.t2area.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

_PREFIXE = "/calendrier/"
_ANNEE_RE = re.compile(r"^\d{4}$")

_ACCENTS = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")


def _norm(text: str) -> str:
    """Minuscule, sans accents, espaces aplatis. « Détails » → « details »."""
    sans_accents = (text or "").strip().lower().translate(_ACCENTS)
    return re.sub(r"\s+", " ", sans_accents)


def _parse_url(url: str) -> tuple[str, str, str]:
    """(événement, épreuve, année). L'année est "" si l'URL n'en porte pas.

    Une **fiche individuelle est tronquée** vers son édition : c'est la forme que
    porte le Sheet. Une **URL d'événement est refusée** : ses épreuves ont des
    dernières éditions d'années différentes (La Baule : `triathlon-m` en 2022,
    `triathlon-jeunes-1` en 2024), un fan-out dont l'année varierait d'une
    épreuve à l'autre n'aurait pas de sens. Un appel = une `Course`.
    """
    parsed = urlparse(url)
    if (parsed.hostname or "").lower() != HOST:
        raise ValueError(f"URL hors fftri.t2area.com : {url}")
    chemin = parsed.path
    if not chemin.startswith(_PREFIXE) or not chemin.endswith(".html"):
        raise ValueError(f"URL fftri.t2area.com non reconnue : {url}")
    parts = chemin[len(_PREFIXE):-len(".html")].split("/")
    if not all(parts):
        raise ValueError(f"URL fftri.t2area.com non reconnue : {url}")
    if len(parts) == 1:
        raise ValueError(
            f"URL d'événement fftri.t2area.com ({parts[0]}) : pointez une épreuve "
            "ou une édition, un événement en porte plusieurs."
        )
    if len(parts) > 4:
        raise ValueError(f"URL fftri.t2area.com non reconnue : {url}")
    evenement, epreuve = parts[0], parts[1]
    if len(parts) == 2:
        return evenement, epreuve, ""
    annee = parts[2]
    if not _ANNEE_RE.match(annee):
        raise ValueError(f"Année illisible dans l'URL fftri.t2area.com : {url}")
    return evenement, epreuve, annee


def _epreuve_url(evenement: str, epreuve: str) -> str:
    return f"{BASE_URL}{_PREFIXE}{evenement}/{epreuve}.html"


def _edition_url(evenement: str, epreuve: str, annee: str) -> str:
    return f"{BASE_URL}{_PREFIXE}{evenement}/{epreuve}/{annee}.html"


def _fetch(client: httpx.Client, url: str) -> str:
    """GET simple. Une édition inexistante répond **303 vers l'accueil**, donc 200 :
    c'est l'absence de `#resultList` qui la démasque (cf. `_parse_edition`)."""
    response = client.get(url)
    response.raise_for_status()
    return response.text


def _resolve_annee(client: httpx.Client, evenement: str, epreuve: str) -> str:
    """Année de la dernière édition publiée, lue sur la page d'épreuve.

    Regex sur les `href` bruts plutôt que sur une classe CSS : les liens portent
    `class="btn-fx-1"`, un décor qui peut changer, alors que la forme de l'URL
    est structurelle.
    """
    url = _epreuve_url(evenement, epreuve)
    html = _fetch(client, url)
    motif = re.compile(
        rf"{re.escape(_PREFIXE)}{re.escape(evenement)}/{re.escape(epreuve)}/(\d{{4}})\.html"
    )
    annees = set(motif.findall(html))
    if not annees:
        raise ValueError(f"Aucune édition publiée pour l'épreuve fftri.t2area.com : {url}")
    return max(annees)
```

- [ ] **Step 5 : lancer les tests, vérifier qu'ils passent**

```bash
uv run pytest tests/test_t2area.py -v && uv run ruff check .
```

Attendu : 13 tests PASS, ruff sans erreur.

- [ ] **Step 6 : commit**

```bash
git add app/scrapers/t2area.py tests/test_t2area.py tests/fixtures/t2area_epreuve_labaule_m.html
git commit -m "feat(scrapers): analyse d'URL du scraper fftri.t2area.com (#51)"
```

---

### Task 3 : lecture du classement

Le cœur du scraper : une `<table id="resultList">` → N `ScrapedResult`.

**Files:**
- Modify: `backend/app/scrapers/t2area.py` (ajouts en fin de module)
- Create: `backend/tests/fixtures/t2area_edition_labaule_2022.html`
- Create: `backend/tests/fixtures/t2area_edition_bouchet_2025.html`
- Create: `backend/tests/fixtures/t2area_edition_nevers_duathlon_2022.html`
- Modify: `backend/tests/test_t2area.py`

**Interfaces:**
- Consomme : `_norm`, `_parse_url`, `BASE_URL` (Task 2).
- Produit :
  - `_index_colonnes(table) -> dict[str, int]` — clés logiques : `clt`, `clt_f`,
    `temps`, `nom`, `club`, `cat`, `clt_cat`, `id_league`, `league`, `details`
  - `_lignes(table, index: dict[str, int]) -> list[dict[str, str]]` (ajoute
    `details_href` et `club_href`)
  - `_cle_fiche(href: str) -> str`, `_dossard(cle: str) -> str`
  - `_temps_ou_vide(brut: str) -> str`, `_genre(categorie: str) -> str`
  - `_est_relais(epreuve: str) -> bool`
  - `_entete(soup, evenement: str, epreuve: str) -> tuple[str, date | None]`
  - `_parse_edition(html: str, source_url: str, evenement: str, epreuve: str) -> list[ScrapedResult]`
- Provisoire : `_parse_edition` appelle `_chronometreur` et
  `_avertir_source_amont`, **livrés en Task 4**. Cette tâche les déclare en
  version minimale (voir Step 3) ; la Task 4 les remplace.

- [ ] **Step 1 : créer les trois fixtures de classement**

Créer `backend/tests/fixtures/t2area_edition_labaule_2022.html` :

```html
<!-- Extrait réel de https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2022.html (6 des 901 lignes, attributs décoratifs retirés) -->
<html lang="fr"><body>
<h1 class="text-xxxl text-center">Résultats du Triathlon de La Baule - M - 2022 - édition du 18-09-2022</h1>
<div class="container"><p>Résultats produits par <a href="http://www.ipitos.com/">IPITOS </a></p></div>
<table id="resultList">
<thead><tr><th>Clt</th><th class="uk-visible@m">Clt/F</th><th>Temps</th><th>Nom</th><th class="uk-visible@m">Club</th><th class="uk-visible@m">CAT</th><th class="uk-visible@m">Clt/CAT</th><th>id_league</th><th>league</th><th>Détails</th></tr></thead>
<tbody>
<tr class="row1"><td class="uk-text-center"><span class="badge badge--outline text-sm">453</span></td><td class="uk-visible@m"></td><td class="uk-text-center">02:41:52</td><td class="uk-text-left"><a href="/athletes/c15540.html"> ACCENT Baptiste</a></td><td class="uk-text-left uk-visible@m"><a href="/clubs/triathlon-club-nantais.html"> TRIATHLON CLUB NANTAIS</a></td><td class="uk-text-left uk-visible@m"><span class="badge badge--outline text-sm">MS2</span></td><td class="uk-text-center uk-visible@m"><span class="badge badge--outline text-sm">89</span></td><td> 15</td><td> PAYS DE LA LOIRE</td><td class="uk-text-center"><a class="uk-icon-button" href="https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2022/bib-566.html"><i class="fa-regular fa-eye"></i></a></td></tr>
<tr class="row1"><td class="uk-text-center"><span class="badge badge--outline text-sm">737</span></td><td class="uk-visible@m"><span class="badge badge--outline text-sm">80</span></td><td class="uk-text-center">03:00:56</td><td class="uk-text-left">ANTOINE Gabrielle</td><td class="uk-text-left uk-visible@m">N-PELOTON</td><td class="uk-text-left uk-visible@m"><span class="badge badge--outline text-sm">FS4</span></td><td class="uk-text-center uk-visible@m"><span class="badge badge--outline text-sm">5</span></td><td> 28</td><td></td><td class="uk-text-center"><a class="uk-icon-button" href="https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2022/bib-762.html"><i class="fa-regular fa-eye"></i></a></td></tr>
<tr class="row0"><td class="uk-text-center"><span class="badge badge--outline text-sm">286</span></td><td class="uk-visible@m"></td><td class="uk-text-center">02:32:02</td><td class="uk-text-left">AGIS Charly</td><td class="uk-text-left uk-visible@m"></td><td class="uk-text-left uk-visible@m"><span class="badge badge--outline text-sm">MS2</span></td><td class="uk-text-center uk-visible@m"><span class="badge badge--outline text-sm">57</span></td><td> 28</td><td></td><td class="uk-text-center"><a class="uk-icon-button" href="https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2022/bib-878.html"><i class="fa-regular fa-eye"></i></a></td></tr>
<tr class="row0"><td class="uk-text-center"><span class="badge badge--outline text-sm">183</span></td><td class="uk-visible@m"></td><td class="uk-text-center">02:25:40</td><td class="uk-text-left">907 Dossard</td><td class="uk-text-left uk-visible@m"></td><td class="uk-text-left uk-visible@m"></td><td class="uk-text-center uk-visible@m"></td><td> 28</td><td></td><td class="uk-text-center"><a class="uk-icon-button" href="https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2022/bib-907.html"><i class="fa-regular fa-eye"></i></a></td></tr>
<tr class="row1"><td class="uk-text-center"><span class="badge badge-primary text-sm">DNF</span></td><td class="uk-visible@m"></td><td class="uk-text-center">00:00:00</td><td class="uk-text-left"><a href="/athletes/b58068.html"> EPP Arnaud</a></td><td class="uk-text-left uk-visible@m"><a href="/clubs/triathlon-club-nantais.html"> TRIATHLON CLUB NANTAIS</a></td><td class="uk-text-left uk-visible@m"><span class="badge badge--outline text-sm">MS4</span></td><td class="uk-text-center uk-visible@m"></td><td> 15</td><td> PAYS DE LA LOIRE</td><td class="uk-text-center"><a class="uk-icon-button" href="https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2022/bib-983.html"><i class="fa-regular fa-eye"></i></a></td></tr>
<tr class="row1"><td class="uk-text-center"><span class="badge badge-primary text-sm">DQ</span></td><td class="uk-visible@m"></td><td class="uk-text-center">42:23:00</td><td class="uk-text-left"><a href="/athletes/a89924.html"> ALLARD Pierre</a></td><td class="uk-text-left uk-visible@m">INDIV LIGUE PAYS DE LA LOIRE</td><td class="uk-text-left uk-visible@m"><span class="badge badge--outline text-sm">MVE</span></td><td class="uk-text-center uk-visible@m"></td><td> 28</td><td></td><td class="uk-text-center"><a class="uk-icon-button" href="https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2022/bib-716.html"><i class="fa-regular fa-eye"></i></a></td></tr>
</tbody>
</table>
</body></html>
```

Créer `backend/tests/fixtures/t2area_edition_bouchet_2025.html` :

```html
<!-- Extrait réel de https://fftri.t2area.com/calendrier/triathlon-du-lac-du-bouchet/triathlon-l/2025.html (2 des 117 lignes) — clés de fiche = licence FFTRI -->
<html lang="fr"><body>
<h1 class="text-xxxl text-center">Résultats du Triathlon du Lac du Bouchet (43) - L - 2025 - édition du 13-07-2025</h1>
<div class="container"><p>Résultats produits par <a href="https://altichrono.fr/">AltiChrono </a></p></div>
<table id="resultList">
<thead><tr><th>Clt</th><th class="uk-visible@m">Clt/F</th><th>Temps</th><th>Nom</th><th class="uk-visible@m">Club</th><th class="uk-visible@m">CAT</th><th class="uk-visible@m">Clt/CAT</th><th>id_league</th><th>league</th><th>Détails</th></tr></thead>
<tbody>
<tr class="row0"><td class="uk-text-center"><span class="badge badge--outline text-sm">101</span></td><td class="uk-visible@m"><span class="badge badge--outline text-sm">20</span></td><td class="uk-text-center">07:18:16</td><td class="uk-text-left"><a href="/athletes/a44719.html"> ABRANTES Amelie</a></td><td class="uk-text-left uk-visible@m"><a href="/clubs/wild-team-triathlon.html"> WILD TEAM TRIATHLON</a></td><td class="uk-text-left uk-visible@m"><span class="badge badge--outline text-sm">FV1</span></td><td class="uk-text-center uk-visible@m"><span class="badge badge--outline text-sm">4</span></td><td> 9</td><td> ILE-DE-FRANCE</td><td class="uk-text-center"><a class="uk-icon-button" href="https://fftri.t2area.com/calendrier/triathlon-du-lac-du-bouchet/triathlon-l/2025/A44719.html"><i class="fa-regular fa-eye"></i></a></td></tr>
<tr class="row1"><td class="uk-text-center"><span class="badge badge--outline text-sm">91</span></td><td class="uk-visible@m"></td><td class="uk-text-center">06:51:06</td><td class="uk-text-left"><a href="/athletes/a01721.html"> ABRANTES Christophe</a></td><td class="uk-text-left uk-visible@m"><a href="/clubs/wild-team-triathlon.html"> WILD TEAM TRIATHLON</a></td><td class="uk-text-left uk-visible@m"><span class="badge badge--outline text-sm">MV2</span></td><td class="uk-text-center uk-visible@m"><span class="badge badge--outline text-sm">15</span></td><td> 9</td><td> ILE-DE-FRANCE</td><td class="uk-text-center"><a class="uk-icon-button" href="https://fftri.t2area.com/calendrier/triathlon-du-lac-du-bouchet/triathlon-l/2025/A01721.html"><i class="fa-regular fa-eye"></i></a></td></tr>
</tbody>
</table>
</body></html>
```

Créer `backend/tests/fixtures/t2area_edition_nevers_duathlon_2022.html` :

```html
<!-- Extrait réel de https://fftri.t2area.com/calendrier/triathlon-de-nevers/duathlon-m/2022.html (3 des 162 lignes) -->
<html lang="fr"><body>
<h1 class="text-xxxl text-center">Résultats du Duathlon de Nevers - M - 2022 - édition du 14-08-2022</h1>
<div class="container"><p>Résultats produits par <a href="https://chronoweb.com/">ChronoWeb </a></p></div>
<table id="resultList">
<thead><tr><th>Clt</th><th class="uk-visible@m">Clt/F</th><th>Temps</th><th>Nom</th><th class="uk-visible@m">Club</th><th class="uk-visible@m">CAT</th><th class="uk-visible@m">Clt/CAT</th><th>id_league</th><th>league</th><th>Détails</th></tr></thead>
<tbody>
<tr class="row0"><td class="uk-text-center"><span class="badge badge--outline text-sm">112</span></td><td class="uk-visible@m"></td><td class="uk-text-center">02:49:16</td><td class="uk-text-left"><a href="/athletes/c01481.html"> ALLEMAND Clement</a></td><td class="uk-text-left uk-visible@m"><a href="/clubs/velizy-triathlon.html"> VELIZY TRIATHLON</a></td><td class="uk-text-left uk-visible@m"><span class="badge badge--outline text-sm">MS3</span></td><td class="uk-text-center uk-visible@m"><span class="badge badge--outline text-sm">15</span></td><td> 9</td><td> ILE-DE-FRANCE</td><td class="uk-text-center"><a class="uk-icon-button" href="https://fftri.t2area.com/calendrier/triathlon-de-nevers/duathlon-m/2022/bib-56.html"><i class="fa-regular fa-eye"></i></a></td></tr>
<tr class="row1"><td class="uk-text-center"><span class="badge badge--outline text-sm">152</span></td><td class="uk-visible@m"></td><td class="uk-text-center">03:16:08</td><td class="uk-text-left">ALLEMAND Jean-Pierre</td><td class="uk-text-left uk-visible@m"></td><td class="uk-text-left uk-visible@m"><span class="badge badge--outline text-sm">MV5</span></td><td class="uk-text-center uk-visible@m"><span class="badge badge--bronze text-sm">3</span></td><td></td><td></td><td class="uk-text-center"><a class="uk-icon-button" href="https://fftri.t2area.com/calendrier/triathlon-de-nevers/duathlon-m/2022/bib-57.html"><i class="fa-regular fa-eye"></i></a></td></tr>
<tr class="row1"><td class="uk-text-center"><span class="badge badge--outline text-sm">135</span></td><td class="uk-visible@m"><span class="badge badge--outline text-sm">14</span></td><td class="uk-text-center">03:03:11</td><td class="uk-text-left"><a href="/athletes/a36490.html"> PANNIER ANAIS</a></td><td class="uk-text-left uk-visible@m"></td><td class="uk-text-left uk-visible@m"><span class="badge badge--outline text-sm">FS2</span></td><td class="uk-text-center uk-visible@m"><span class="badge badge--outline text-sm">7</span></td><td> 28</td><td></td><td class="uk-text-center"><a class="uk-icon-button" href="https://fftri.t2area.com/calendrier/triathlon-de-nevers/duathlon-m/2022/bib-152.html"><i class="fa-regular fa-eye"></i></a></td></tr>
</tbody>
</table>
</body></html>
```

- [ ] **Step 2 : écrire les tests qui échouent**

Ajouter à `backend/tests/test_t2area.py`, sous la ligne `EPREUVE_LABAULE = …` :

```python
EDITION_LABAULE = _fixture("t2area_edition_labaule_2022.html")     # triathlon M, clés bib-
EDITION_BOUCHET = _fixture("t2area_edition_bouchet_2025.html")     # clés licence FFTRI
EDITION_NEVERS = _fixture("t2area_edition_nevers_duathlon_2022.html")  # duathlon
```

et, en fin de fichier :

```python
def _labaule() -> list:
    return t2area._parse_edition(
        EDITION_LABAULE, URL_EDITION, "triathlon-de-la-baule", "triathlon-m"
    )


def _par_nom(resultats, nom):
    return next(r for r in resultats if r.athlete_name.startswith(nom))


def test_parse_edition_lit_toutes_les_lignes():
    assert len(_labaule()) == 6


def test_parse_edition_colonnes_dun_finisher():
    r = _par_nom(_labaule(), "ACCENT")

    assert (r.athlete_name, r.athlete_firstname) == ("ACCENT", "Baptiste")
    assert r.club == "TRIATHLON CLUB NANTAIS"
    assert r.category == "MS2"
    assert r.gender == "M"
    assert r.rank_overall == 453
    assert r.rank_category == 89
    assert r.rank_gender is None
    assert r.total_time == "02:41:52"
    assert r.bib_number == "566"
    assert r.status == ""          # finisher : laissé à l'heuristique de mapping
    assert r.is_relay is False
    assert r.provider == "t2area"
    assert r.source_url == URL_EDITION


def test_parse_edition_entete_nom_et_date():
    """Nom et date viennent du <h1> ; la date entre dans l'identité de la Course."""
    r = _labaule()[0]

    assert r.event_name == "Triathlon de La Baule - M"
    assert r.event_date == date(2022, 9, 18)
    assert r.event_type == "triathlon-m"


def test_parse_edition_classement_feminin_rempli_pour_les_femmes():
    """`Clt/F` n'est renseigné que sur les lignes féminines (125/125 sur l'épreuve réelle)."""
    r = _par_nom(_labaule(), "ANTOINE")

    assert r.gender == "F"
    assert r.rank_gender == 80


def test_parse_edition_dnf():
    """Un DNF sort avec `00:00:00` dans la colonne Temps : c'est un temps absent."""
    r = _par_nom(_labaule(), "EPP")

    assert r.status == "DNF"
    assert r.total_time == ""
    assert r.rank_overall is None


def test_parse_edition_disqualifie():
    r = _par_nom(_labaule(), "ALLARD")

    assert r.status == "DSQ"
    assert r.rank_overall is None


def test_parse_edition_club_absent():
    assert _par_nom(_labaule(), "AGIS").club == ""


def test_parse_edition_ligne_anonyme_du_site():
    """« 907 Dossard » : une entrée sans identité, telle que la source la publie.

    Aucune heuristique locale — le scraper ne devine pas d'identité. Test de
    verrouillage : le jour où on voudra changer ça, ce sera un choix explicite.
    """
    r = _par_nom(_labaule(), "Dossard")

    assert (r.athlete_name, r.athlete_firstname) == ("Dossard", "907")
    assert r.bib_number == "907"


def test_parse_edition_raw_data_conserve_le_contexte():
    r = _par_nom(_labaule(), "ACCENT")

    assert r.raw_data["cle_fiche"] == "bib-566"
    assert r.raw_data["league"] == "PAYS DE LA LOIRE"
    assert r.raw_data["id_league"] == "15"
    assert r.raw_data["club_href"] == "/clubs/triathlon-club-nantais.html"
    assert r.raw_data["clt"] == "453"
    assert r.raw_data["fiche_url"].endswith("/2022/bib-566.html")


def test_parse_edition_cle_licence_ne_remplit_pas_le_dossard():
    """`bib_number` ne contient jamais autre chose qu'un vrai dossard (§2.3)."""
    resultats = t2area._parse_edition(
        EDITION_BOUCHET,
        "https://fftri.t2area.com/calendrier/triathlon-du-lac-du-bouchet/triathlon-l/2025.html",
        "triathlon-du-lac-du-bouchet",
        "triathlon-l",
    )
    r = _par_nom(resultats, "ABRANTES")

    assert r.bib_number == ""
    assert r.raw_data["cle_fiche"] == "A44719"
    assert r.event_name == "Triathlon du Lac du Bouchet (43) - L"
    assert r.event_date == date(2025, 7, 13)
    assert r.event_type == "triathlon-l"


def test_parse_edition_duathlon():
    resultats = t2area._parse_edition(
        EDITION_NEVERS,
        "https://fftri.t2area.com/calendrier/triathlon-de-nevers/duathlon-m/2022.html",
        "triathlon-de-nevers",
        "duathlon-m",
    )

    assert len(resultats) == 3
    assert {r.event_type for r in resultats} == {"duathlon-m"}
    assert _par_nom(resultats, "PANNIER").rank_gender == 14


def test_parse_edition_sans_result_list_leve():
    """Édition inexistante : le site répond 303 vers son accueil, donc 200."""
    with pytest.raises(ValueError, match="Aucun classement"):
        t2area._parse_edition(
            "<html><body><h1>CALENDRIER DES ÉPREUVES FFTRI</h1></body></html>",
            URL_EDITION,
            "triathlon-de-la-baule",
            "triathlon-m",
        )


def test_parse_edition_entete_ampute_leve():
    """Markup changé : mieux vaut une erreur qu'un import silencieusement faux."""
    html = (
        "<html><body><h1>Résultats du X - 2022 - édition du 18-09-2022</h1>"
        '<table id="resultList"><thead><tr><th>Nom</th><th>Club</th></tr></thead>'
        "<tbody></tbody></table></body></html>"
    )
    with pytest.raises(ValueError, match="En-tête fftri inattendu"):
        t2area._parse_edition(html, URL_EDITION, "x", "triathlon-m")


def test_index_colonnes_place_details_apres_les_colonnes_de_ligue():
    """L'en-tête réel porte 10 colonnes : `id_league`/`league` avant `Détails`.

    C'est pour ça qu'on lit par libellé et non par position.
    """
    from bs4 import BeautifulSoup

    table = BeautifulSoup(EDITION_LABAULE, "lxml").find(id="resultList")

    assert t2area._index_colonnes(table) == {
        "clt": 0, "clt_f": 1, "temps": 2, "nom": 3, "club": 4,
        "cat": 5, "clt_cat": 6, "id_league": 7, "league": 8, "details": 9,
    }


@pytest.mark.parametrize("brut,attendu", [
    ("02:41:52", "02:41:52"),
    ("00:00:00", ""),      # DNF : temps absent, pas un temps nul
    ("", ""),
    ("   ", ""),
])
def test_temps_ou_vide(brut, attendu):
    assert t2area._temps_ou_vide(brut) == attendu


@pytest.mark.parametrize("categorie,attendu", [
    ("MS2", "M"), ("FV1", "F"), ("MHAN", "M"), ("MT1", "M"), ("", ""), ("S3", ""),
])
def test_genre(categorie, attendu):
    assert t2area._genre(categorie) == attendu


@pytest.mark.parametrize("cle,attendu", [
    ("bib-566", "566"),
    ("A44719", ""),        # licence FFTRI
    ("id-1153352", ""),    # identifiant interne
    ("", ""),
])
def test_dossard(cle, attendu):
    assert t2area._dossard(cle) == attendu


@pytest.mark.parametrize("epreuve,attendu", [
    ("swim-run-m-eq", True),
    ("bike-run-s-open-eq", True),
    ("triathlon-jeunes-1-eq", True),
    ("triathlon-relais", True),
    ("triathlon-m", False),
    ("triathlon-s-open", False),
    ("duathlon-l", False),
])
def test_est_relais(epreuve, attendu):
    """Déduit du slug — non vérifié sur données réelles (§8.3 du design)."""
    assert t2area._est_relais(epreuve) is attendu


def test_entete_titre_illisible_garde_la_date():
    """Deux regex indépendantes : un libellé inattendu ne fait pas perdre la date."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(
        "<html><body><h1>Résultats — édition du 18-09-2022</h1></body></html>", "lxml"
    )
    nom, event_date = t2area._entete(soup, "triathlon-de-la-baule", "triathlon-m")

    assert event_date == date(2022, 9, 18)
    assert nom == "Triathlon De La Baule Triathlon M"
```

Ajouter aussi l'import de `date` dans le groupe stdlib du fichier de test,
**avant** `from pathlib import Path` (ordre isort) :

```python
from datetime import date
from pathlib import Path
```

- [ ] **Step 3 : lancer les tests, vérifier qu'ils échouent**

```bash
uv run pytest tests/test_t2area.py -v
```

Attendu : ÉCHEC, `AttributeError: module 'app.scrapers.t2area' has no attribute '_parse_edition'`.

- [ ] **Step 4 : implémenter**

Ajouter à la fin de `backend/app/scrapers/t2area.py` :

```python
# Libellé d'en-tête normalisé → clé logique de colonne. L'en-tête réel porte
# **10** colonnes (`id_league` et `league` s'intercalent entre `Clt/CAT` et
# `Détails`) : lire par position ferait prendre la ligue pour le lien de fiche.
# Stable sur les 5 éditions sondées, de 2022 à 2026.
_COLONNES = {
    "clt": "clt",
    "clt/f": "clt_f",
    "temps": "temps",
    "nom": "nom",
    "club": "club",
    "cat": "cat",
    "clt/cat": "clt_cat",
    "id_league": "id_league",
    "league": "league",
    "details": "details",
}

#: Colonnes sans lesquelles une ligne n'a pas de sens.
_COLONNES_REQUISES = frozenset({"clt", "temps", "nom"})

_BIB_RE = re.compile(r"^bib-(\d+)$", re.I)

# Marqueurs d'équipe dans le **slug d'épreuve** (`swim-run-m-eq`, `triathlon-relais`).
# Jetons isolés : le « eq » de « equipe » ne doit pas être capté par accident.
_RELAIS_RE = re.compile(r"(?<![a-z0-9])(eq|relais|duo)(?![a-z0-9])")

# Le <h1> porte tout l'en-tête :
#   « Résultats du Triathlon de La Baule - M - 2022 - édition du 18-09-2022 »
# Deux regex **indépendantes** : un libellé inattendu ne doit pas faire perdre la
# date, qui entre dans l'identité de la Course (UNIQUE(name, event_date, event_type)).
_RE_NOM = re.compile(r"r[ée]sultats\s+d[eu]s?\s+(.+?)\s+-\s+\d{4}\s+-\s+[ée]dition\b", re.I)
_RE_DATE = re.compile(r"[ée]dition\s+du\s+(\d{2})-(\d{2})-(\d{4})", re.I)


def _index_colonnes(table) -> dict[str, int]:
    """Clé logique → position, lue dans les libellés du `<thead>`."""
    index: dict[str, int] = {}
    for position, th in enumerate(table.select("thead th")):
        cle = _COLONNES.get(_norm(th.get_text(" ", strip=True)))
        if cle and cle not in index:
            index[cle] = position
    return index


def _href(cellule) -> str:
    lien = cellule.find("a", href=True)
    return lien["href"].strip() if lien else ""


def _lignes(table, index: dict[str, int]) -> list[dict[str, str]]:
    """Une ligne = {clé de colonne → texte}, plus les href de Détails et Club.

    Une ligne trop courte est une anomalie de markup : journalisée et sautée
    plutôt que lue de travers.
    """
    attendu = max(index.values()) + 1
    lignes: list[dict[str, str]] = []
    for tr in table.select("tbody tr"):
        cellules = tr.find_all("td")
        if len(cellules) < attendu:
            logger.warning(
                "Ligne fftri ignorée : %d cellules pour %d colonnes", len(cellules), attendu
            )
            continue
        ligne = {
            cle: cellules[position].get_text(" ", strip=True)
            for cle, position in index.items()
        }
        ligne["details_href"] = _href(cellules[index["details"]]) if "details" in index else ""
        ligne["club_href"] = _href(cellules[index["club"]]) if "club" in index else ""
        lignes.append(ligne)
    return lignes


def _cle_fiche(href: str) -> str:
    """Dernier segment du href de la colonne Détails, sans son « .html »."""
    dernier = urlparse(href).path.rsplit("/", 1)[-1]
    return dernier[:-len(".html")] if dernier.endswith(".html") else dernier


def _dossard(cle: str) -> str:
    """Dossard **seulement** si la clé de fiche en est un (`bib-566` → « 566 »).

    La source n'affiche jamais de dossard ; la clé de fiche est tantôt un dossard,
    tantôt une licence FFTRI (`A44719`), tantôt un identifiant interne
    (`id-1153352`). Remplir `bib_number` avec les deux autres ferait mentir le
    champ — le front afficherait « #A44719 ». Les éditions sans dossard retombent
    sur l'appariement par athlète (`import_service._match_without_bib`).
    """
    trouve = _BIB_RE.match(cle)
    return trouve.group(1) if trouve else ""


def _temps_ou_vide(brut: str) -> str:
    """Temps normalisé. **`00:00:00` vaut temps absent** — un DNF sort avec cette
    valeur (La Baule 2022, EPP Arnaud) et la laisser ferait basculer
    `mapping.derive_status` sur « finisher »."""
    normalise = normalize_time((brut or "").strip())
    return "" if normalise in ("", "00:00:00") else normalise


def _genre(categorie: str) -> str:
    """Préfixe M/F de la catégorie fédérale (`MS2`, `FV1`, `MHAN`, `MT1`)."""
    initiale = (categorie or "").strip()[:1].upper()
    return initiale if initiale in ("M", "F") else ""


def _est_relais(epreuve: str) -> bool:
    """Déduit du slug d'épreuve. Non vérifié sur données réelles (§8.3 du design) :
    aucune épreuve équipe sondée n'a de classement publié."""
    return _RELAIS_RE.search(epreuve.lower()) is not None


def _titre(soup) -> str:
    """Texte du `<h1>` de résultats (la page en porte d'autres, décoratifs)."""
    for h1 in soup.find_all("h1"):
        texte = h1.get_text(" ", strip=True)
        if _norm(texte).startswith("resultats"):
            return texte
    return ""


def _entete(soup, evenement: str, epreuve: str) -> tuple[str, date | None]:
    """(nom d'épreuve, date), lus indépendamment dans le `<h1>`.

    Le nom est déjà qualifié par l'épreuve (« - M ») : pas de `qualify_event_name`.
    """
    titre = _titre(soup)
    trouve = _RE_NOM.search(titre)
    if trouve:
        nom = trouve.group(1)
    else:
        nom = f"{evenement} {epreuve}".replace("-", " ").title()
        logger.warning(
            "Titre fftri illisible (%r) : nom d'épreuve replié sur les slugs (%s)", titre, nom
        )
    event_date = None
    jour = _RE_DATE.search(titre)
    if jour:
        try:
            event_date = date(int(jour.group(3)), int(jour.group(2)), int(jour.group(1)))
        except ValueError:
            logger.warning("Date d'édition fftri illisible : %r", jour.group(0))
    else:
        logger.warning("Date d'édition absente du titre fftri : %r", titre)
    return nom, event_date


def _construire(
    ligne: dict[str, str],
    *,
    source_url: str,
    evenement: str,
    epreuve: str,
    event_name: str,
    event_type: str,
    event_date: date | None,
    chrono: tuple[str, str],
) -> ScrapedResult:
    """Une ligne de classement → un participant."""
    nom, prenom = split_athlete_name(ligne.get("nom", ""))
    cle = _cle_fiche(ligne.get("details_href", ""))
    categorie = ligne.get("cat", "")
    clt = ligne.get("clt", "")

    result = ScrapedResult(source_url=source_url, provider="t2area")
    result.event_name = event_name
    result.event_type = event_type
    result.event_date = event_date
    result.athlete_name = nom
    result.athlete_firstname = prenom
    result.club = ligne.get("club", "")
    result.category = categorie
    result.gender = _genre(categorie)
    result.bib_number = _dossard(cle)
    result.rank_overall = normalize_rank(clt)
    result.rank_gender = normalize_rank(ligne.get("clt_f", ""))
    result.rank_category = normalize_rank(ligne.get("clt_cat", ""))
    result.total_time = _temps_ou_vide(ligne.get("temps", ""))
    # La colonne Clt porte le statut quand elle ne porte pas de rang (DNF, DQ).
    result.status = derive_status_from_label(clt)
    result.is_relay = _est_relais(epreuve)
    # De quoi diagnostiquer sans re-scraper : clé brute, ligue, lien club, chronométreur.
    result.raw_data = {
        "cle_fiche": cle,
        "fiche_url": ligne.get("details_href", ""),
        "clt": clt,
        "id_league": ligne.get("id_league", ""),
        "league": ligne.get("league", ""),
        "club_href": ligne.get("club_href", ""),
        "chronometreur": chrono[0],
        "chronometreur_url": chrono[1],
        "evenement": evenement,
        "epreuve": epreuve,
    }
    return result


def _chronometreur(soup) -> tuple[str, str]:
    """(nom, lien) du chronométreur amont. Remplacé en Task 4."""
    return "", ""


def _avertir_source_amont(nom: str, lien: str, url: str) -> None:
    """Journalise si le chronométreur amont est supporté. Remplacé en Task 4."""


def _parse_edition(
    html: str, source_url: str, evenement: str, epreuve: str
) -> list[ScrapedResult]:
    """HTML d'une édition → participants. **Pur** : aucune requête."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find(id="resultList")
    if table is None:
        raise ValueError(
            f"Aucun classement (#resultList) sur {source_url} : édition inexistante "
            "— le site redirige alors vers son accueil — ou markup fftri modifié."
        )
    index = _index_colonnes(table)
    manquantes = _COLONNES_REQUISES - set(index)
    if manquantes:
        raise ValueError(
            f"En-tête fftri inattendu sur {source_url} : "
            f"colonnes manquantes {sorted(manquantes)}."
        )
    event_name, event_date = _entete(soup, evenement, epreuve)
    # Le type vient du **slug d'épreuve**, vérifié sur les slugs réels :
    # `swim-run-m` → swimrun-m, `triathlon-xs-jeunes` → triathlon-xs,
    # `bike-run-s-open-eq` → bike-run.
    event_type = classify_event_type(epreuve)
    chrono = _chronometreur(soup)
    _avertir_source_amont(chrono[0], chrono[1], source_url)
    return [
        _construire(
            ligne,
            source_url=source_url,
            evenement=evenement,
            epreuve=epreuve,
            event_name=event_name,
            event_type=event_type,
            event_date=event_date,
            chrono=chrono,
        )
        for ligne in _lignes(table, index)
    ]
```

- [ ] **Step 5 : lancer les tests, vérifier qu'ils passent**

```bash
uv run pytest tests/test_t2area.py -v && uv run ruff check .
```

Attendu : tout PASS (≈ 37 tests), ruff sans erreur.

- [ ] **Step 6 : commit**

```bash
git add app/scrapers/t2area.py tests/test_t2area.py tests/fixtures/t2area_edition_*.html
git commit -m "feat(scrapers): lecture du classement fftri.t2area.com (#51)"
```

---

### Task 4 : mention du chronométreur amont et avertissement

La FFTRI republie : chaque classement porte « Résultats produits par X ». Quand X
est un provider qu'on sait lire, la source amont est **plus riche** (dossards
partout, splits de tous les participants). Mais la mention ne lie que **l'accueil**
du chronométreur (`http://my3.raceresult.com/`), jamais l'épreuve : aucune URL
source n'est constructible. On journalise donc, on ne délègue pas.

**Files:**
- Modify: `backend/app/scrapers/t2area.py` (remplace les deux stubs de la Task 3)
- Modify: `backend/tests/test_t2area.py`

**Interfaces:**
- Consomme : `_norm` (Task 2), `_parse_edition` (Task 3).
- Produit : `_chronometreur(soup) -> tuple[str, str]`,
  `_avertir_source_amont(nom: str, lien: str, url: str) -> None`.

- [ ] **Step 1 : écrire les tests qui échouent**

Ajouter en fin de `backend/tests/test_t2area.py` :

```python
# Mention réelle de Vichy L 2024 : un chronométreur que nous savons lire.
EDITION_RACERESULT = EDITION_LABAULE.replace(
    '<a href="http://www.ipitos.com/">IPITOS </a>',
    '<a href="http://my3.raceresult.com/">RaceResult </a>',
)


def test_chronometreur_lit_la_mention():
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(EDITION_LABAULE, "lxml")

    assert t2area._chronometreur(soup) == ("IPITOS", "http://www.ipitos.com/")


def test_chronometreur_absent():
    from bs4 import BeautifulSoup

    soup = BeautifulSoup("<html><body><p>rien</p></body></html>", "lxml")

    assert t2area._chronometreur(soup) == ("", "")


def test_chronometreur_dans_raw_data():
    r = _par_nom(_labaule(), "ACCENT")

    assert r.raw_data["chronometreur"] == "IPITOS"
    assert r.raw_data["chronometreur_url"] == "http://www.ipitos.com/"


def test_avertissement_quand_le_chronometreur_est_supporte(caplog):
    """L'opérateur doit savoir qu'une meilleure source existe — lui seul peut la fournir."""
    with caplog.at_level(logging.WARNING, logger="app.scrapers.t2area"):
        t2area._parse_edition(
            EDITION_RACERESULT, URL_EDITION, "triathlon-de-la-baule", "triathlon-m"
        )

    assert "raceresult" in caplog.text
    assert "my3.raceresult.com" in caplog.text


def test_pas_davertissement_pour_un_chronometreur_non_supporte(caplog):
    """IPITOS est hors de notre périmètre : rien à signaler, le scraper fait le travail."""
    with caplog.at_level(logging.WARNING, logger="app.scrapers.t2area"):
        _labaule()

    assert "IPITOS" not in caplog.text


def test_pas_davertissement_sans_mention(caplog):
    from bs4 import BeautifulSoup

    with caplog.at_level(logging.WARNING, logger="app.scrapers.t2area"):
        t2area._avertir_source_amont(*t2area._chronometreur(BeautifulSoup("", "lxml")), URL_EDITION)

    assert caplog.text == ""
```

Ajouter `import logging` en **première** ligne du groupe stdlib du fichier de
test (isort place les `import X` avant les `from X import …`) :

```python
import logging
from datetime import date
from pathlib import Path
```

- [ ] **Step 2 : lancer les tests, vérifier qu'ils échouent**

```bash
uv run pytest tests/test_t2area.py -k "chronometreur or avertissement" -v
```

Attendu : ÉCHEC — `assert ('', '') == ('IPITOS', 'http://www.ipitos.com/')`.

- [ ] **Step 3 : implémenter**

Dans `backend/app/scrapers/t2area.py`, remplacer les deux stubs de la Task 3 par :

```python
_RE_CHRONO = re.compile(r"r[ée]sultats\s+produits\s+par", re.I)


def _chronometreur(soup) -> tuple[str, str]:
    """(nom, lien) du chronométreur amont : « Résultats produits par X »."""
    for p in soup.find_all("p"):
        texte = p.get_text(" ", strip=True)
        if not _RE_CHRONO.search(texte):
            continue
        lien = p.find("a", href=True)
        if lien:
            return lien.get_text(" ", strip=True), lien["href"].strip()
        return _RE_CHRONO.sub("", texte).strip(), ""
    return "", ""


def _avertir_source_amont(nom: str, lien: str, url: str) -> None:
    """Journalise quand le chronométreur amont est un provider **supporté**.

    La FFTRI ne chronomètre pas, elle republie : à la source, on aurait les
    dossards de tout le monde et les splits de tous les participants. Cette
    délégation ne peut pas être automatisée — la mention ne lie que la page
    d'accueil du chronométreur, jamais l'épreuve, et aucun identifiant d'épreuve
    n'est récupérable (§1.1 du design). L'opérateur reste seul à pouvoir fournir
    l'URL source.

    Import local de `registry` : `registry` importe ce module au chargement,
    l'inverse au niveau module créerait un cycle (même procédé que les helpers
    Klikego appelés depuis `registry`).
    """
    if not lien:
        return
    from app.scrapers.registry import detect_provider

    provider = detect_provider(lien)
    if provider == "playwright":
        return
    logger.warning(
        "%s : résultats produits par %s (%s) — le provider « %s » est supporté et "
        "sa source est plus riche (dossards et splits de tous les participants). "
        "L'URL d'épreuve n'est pas déductible de cette page : à fournir à la main.",
        url, nom or provider, lien, provider,
    )
```

- [ ] **Step 4 : lancer les tests, vérifier qu'ils passent**

```bash
uv run pytest tests/test_t2area.py -v && uv run ruff check .
```

Attendu : tout PASS.

- [ ] **Step 5 : commit**

```bash
git add app/scrapers/t2area.py tests/test_t2area.py
git commit -m "feat(scrapers): signale une meilleure source amont sur fftri.t2area.com (#51)"
```

---

### Task 5 : splits des fiches individuelles

Le classement ne contient **aucun** split : ils vivent sur la fiche individuelle,
soit une requête HTTP par participant. On ne charge donc que les fiches des
membres du TCN (25 requêtes sur La Baule, pas 901). Cette tâche livre le parsing
et l'application ; la boucle réseau arrive en Task 6.

**Files:**
- Modify: `backend/app/scrapers/t2area.py`
- Create: `backend/tests/fixtures/t2area_fiche_triathlon.html`
- Create: `backend/tests/fixtures/t2area_fiche_duathlon.html`
- Modify: `backend/tests/test_t2area.py`

**Interfaces:**
- Consomme : `_norm`, `_temps_ou_vide` (Tasks 2-3).
- Produit :
  - `_parse_fiche(html: str) -> list[tuple[str, str]]` — segments `(libellé, temps)`,
    « Général » exclu
  - `_appliquer_splits(result: ScrapedResult, segments: list[tuple[str, str]]) -> None`

- [ ] **Step 1 : créer les deux fixtures de fiche**

Créer `backend/tests/fixtures/t2area_fiche_triathlon.html` :

```html
<!-- Extrait réel de https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2022/bib-566.html — accordéon seul, panneaux de détail retirés -->
<html lang="fr"><body>
<h1 class="text-xxxl text-center">Résultats du Triathlon de La Baule - M - 2022 de ACCENT Baptiste</h1>
<ul class="accordion js-accordion"><li class="accordion__item js-accordion__item"><button class="accordion__header" type="button"><span class="text-md"><div class="uk-width-1-6"></div><div class="uk-width-3-6"><span class="title">Général</span></div><div class="uk-width-2-6"><span class="title">02:41:52 </span></div></span></button></li><li class="accordion__item js-accordion__item"><button class="accordion__header" type="button"><span class="text-md"><div class="uk-width-1-6"></div><div class="uk-width-3-6"><span class="title">Natation</span></div><div class="uk-width-2-6"><span class="title">00:41:16</span></div></span></button></li><!-- Transition 1 --><li class="accordion__item js-accordion__item"><button class="accordion__header" type="button"><span class="text-md"><div class="uk-width-1-6"></div><div class="uk-width-3-6"><span class="title">Transition 1</span></div><div class="uk-width-2-6"><span class="title">00:00:00</span></div></span></button></li><li class="accordion__item js-accordion__item"><button class="accordion__header" type="button"><span class="text-md"><div class="uk-width-1-6"></div><div class="uk-width-3-6"><span class="title">Vélo</span></div><div class="uk-width-2-6"><span class="title">01:14:59</span></div></span></button></li><li class="accordion__item js-accordion__item"><button class="accordion__header" type="button"><span class="text-md"><div class="uk-width-1-6"></div><div class="uk-width-3-6"><span class="title">Transition 2</span></div><div class="uk-width-2-6"><span class="title">00:00:00</span></div></span></button></li><li class="accordion__item js-accordion__item"><button class="accordion__header" type="button"><span class="text-md"><div class="uk-width-1-6"></div><div class="uk-width-3-6"><span class="title">Course à Pied</span></div><div class="uk-width-2-6"><span class="title">00:45:39</span></div></span></button></li></ul>
</body></html>
```

Créer `backend/tests/fixtures/t2area_fiche_duathlon.html` :

```html
<!-- Extrait réel de https://fftri.t2area.com/calendrier/triathlon-de-nevers/duathlon-m/2022/bib-56.html — accordéon seul, panneaux de détail retirés -->
<html lang="fr"><body>
<h1 class="text-xxxl text-center">Résultats du Duathlon de Nevers - M - 2022 de ALLEMAND Clement</h1>
<ul class="accordion js-accordion"><li class="accordion__item js-accordion__item"><button class="accordion__header" type="button"><span class="text-md"><div class="uk-width-1-6"></div><div class="uk-width-3-6"><span class="title">Général</span></div><div class="uk-width-2-6"><span class="title">02:49:16 </span></div></span></button></li><li class="accordion__item js-accordion__item"><button class="accordion__header" type="button"><span class="text-md"><div class="uk-width-1-6"></div><div class="uk-width-3-6"><span class="title">CàP 1</span></div><div class="uk-width-2-6"><span class="title">00:22:47</span></div></span></button></li><!-- Transition 1 --><li class="accordion__item js-accordion__item"><button class="accordion__header" type="button"><span class="text-md"><div class="uk-width-1-6"></div><div class="uk-width-3-6"><span class="title">Transition 1</span></div><div class="uk-width-2-6"><span class="title">00:01:29</span></div></span></button></li><li class="accordion__item js-accordion__item"><button class="accordion__header" type="button"><span class="text-md"><div class="uk-width-1-6"></div><div class="uk-width-3-6"><span class="title">Vélo</span></div><div class="uk-width-2-6"><span class="title">01:24:14</span></div></span></button></li><li class="accordion__item js-accordion__item"><button class="accordion__header" type="button"><span class="text-md"><div class="uk-width-1-6"></div><div class="uk-width-3-6"><span class="title">Transition 2</span></div><div class="uk-width-2-6"><span class="title">00:02:07</span></div></span></button></li><li class="accordion__item js-accordion__item"><button class="accordion__header" type="button"><span class="text-md"><div class="uk-width-1-6"></div><div class="uk-width-3-6"><span class="title">CàP 2</span></div><div class="uk-width-2-6"><span class="title">00:58:39</span></div></span></button></li></ul>
</body></html>
```

- [ ] **Step 2 : écrire les tests qui échouent**

Ajouter à `backend/tests/test_t2area.py`, sous les constantes de fixtures :

```python
FICHE_TRIATHLON = _fixture("t2area_fiche_triathlon.html")
FICHE_DUATHLON = _fixture("t2area_fiche_duathlon.html")

# Fiche au découpage inattendu : `_appliquer_splits` doit basculer sur `segments`.
FICHE_LIBELLE_INCONNU = """
<html lang="fr"><body>
<ul class="accordion"><li class="accordion__item"><button><span>
<span class="title">Général</span><span class="title">01:00:00</span>
</span></button></li><li class="accordion__item"><button><span>
<span class="title">Natation 1</span><span class="title">00:10:00</span>
</span></button></li><li class="accordion__item"><button><span>
<span class="title">Trail 1</span><span class="title">00:20:00</span>
</span></button></li></ul>
</body></html>
"""
```

et, en fin de fichier :

```python
def test_parse_fiche_triathlon_exclut_le_general():
    """« Général » est le temps total, déjà lu dans le classement."""
    segments = t2area._parse_fiche(FICHE_TRIATHLON)

    assert [libelle for libelle, _ in segments] == [
        "Natation", "Transition 1", "Vélo", "Transition 2", "Course à Pied",
    ]


def test_parse_fiche_transition_a_zero_est_absente():
    """La Baule 2022 ne chronomètre pas les transitions : 0 s serait un faux."""
    segments = dict(t2area._parse_fiche(FICHE_TRIATHLON))

    assert segments["Transition 1"] == ""
    assert segments["Natation"] == "00:41:16"


def test_appliquer_splits_triathlon():
    r = ScrapedResult(source_url=URL_EDITION, provider="t2area")

    t2area._appliquer_splits(r, t2area._parse_fiche(FICHE_TRIATHLON))

    assert r.swim_time == "00:41:16"
    assert r.bike_time == "01:14:59"
    assert r.run_time == "00:45:39"
    assert r.t1_time == ""
    assert r.t2_time == ""
    assert r.segments is None


def test_appliquer_splits_duathlon_par_libelle_et_non_par_position():
    """« CàP 1 » va au slot natation, « CàP 2 » au slot course : c'est ce qu'attend
    `_SPLIT_KEYS_BY_SPORT`, qui les ré-étiquette en course1/course2."""
    r = ScrapedResult(source_url=URL_EDITION, provider="t2area")

    t2area._appliquer_splits(r, t2area._parse_fiche(FICHE_DUATHLON))

    assert r.swim_time == "00:22:47"
    assert r.t1_time == "00:01:29"
    assert r.bike_time == "01:24:14"
    assert r.t2_time == "00:02:07"
    assert r.run_time == "00:58:39"


def test_appliquer_splits_duathlon_reetiquete_par_mapping():
    """Bout à bout avec la couche service : les clés finales sont celles du sport."""
    from app.services.mapping import build_splits

    r = ScrapedResult(source_url=URL_EDITION, provider="t2area")
    r.event_type = "duathlon-m"
    t2area._appliquer_splits(r, t2area._parse_fiche(FICHE_DUATHLON))

    assert build_splits(r) == {
        "course1": "00:22:47", "t1": "00:01:29", "bike": "01:24:14",
        "t2": "00:02:07", "course2": "00:58:39",
    }


def test_appliquer_splits_libelle_inconnu_bascule_sur_segments():
    """Un seul libellé hors table suffit : rien n'est perdu silencieusement."""
    r = ScrapedResult(source_url=URL_EDITION, provider="t2area")

    t2area._appliquer_splits(r, t2area._parse_fiche(FICHE_LIBELLE_INCONNU))

    assert r.segments == [("Natation 1", "00:10:00"), ("Trail 1", "00:20:00")]
    assert r.swim_time == ""
    assert r.bike_time == ""
```

Ajouter l'import du dataclass dans le groupe `app.*` du fichier de test,
**après** `from app.scrapers import t2area` (ordre isort) :

```python
from app.scrapers import t2area
from app.scrapers.base import ScrapedResult
```

- [ ] **Step 3 : lancer les tests, vérifier qu'ils échouent**

```bash
uv run pytest tests/test_t2area.py -k "fiche or splits" -v
```

Attendu : ÉCHEC, `AttributeError: … has no attribute '_parse_fiche'`.

- [ ] **Step 4 : implémenter**

Ajouter à la fin de `backend/app/scrapers/t2area.py` :

```python
# Libellé d'accordéon normalisé → slot positionnel de ScrapedResult. Les libellés
# **changent selon le sport** (triathlon : Natation / … / Course à Pied ;
# duathlon : CàP 1 / … / CàP 2), d'où un mapping par libellé et jamais par
# position : un mapping positionnel rangerait le 3ᵉ segment d'un aquathlon
# (Natation / T1 / CàP) dans le vélo.
_SLOTS = {
    "natation": "swim_time",
    "cap 1": "swim_time",
    "transition 1": "t1_time",
    "velo": "bike_time",
    "transition 2": "t2_time",
    "course a pied": "run_time",
    "cap 2": "run_time",
}


def _parse_fiche(html: str) -> list[tuple[str, str]]:
    """Segments (libellé, temps) de l'accordéon d'une fiche individuelle.

    « Général » est écarté : c'est le temps total, déjà lu dans le classement.
    Un segment à `00:00:00` ressort à "" (cf. `_temps_ou_vide`).
    """
    soup = BeautifulSoup(html, "lxml")
    segments: list[tuple[str, str]] = []
    for item in soup.select("ul.accordion li.accordion__item"):
        titres = [t.get_text(" ", strip=True) for t in item.select("button .title")]
        if len(titres) < 2:
            continue
        libelle, temps = titres[0], titres[1]
        if _norm(libelle) == "general":
            continue
        segments.append((libelle, _temps_ou_vide(temps)))
    return segments


def _appliquer_splits(result: ScrapedResult, segments: list[tuple[str, str]]) -> None:
    """Range les segments dans les 5 slots, ou bascule **tout** sur `segments`.

    Filet : un seul libellé hors table suffit à basculer sur la liste ordonnée
    étiquetée, déplafonnée et prioritaire dans `mapping.build_splits`. Rien n'est
    perdu silencieusement sur un sport au découpage inattendu, et le cas nominal
    garde les clés canoniques que le front sait afficher.
    """
    ranges: dict[str, str] = {}
    for libelle, temps in segments:
        slot = _SLOTS.get(_norm(libelle))
        if slot is None:
            result.segments = [(lib, tps) for lib, tps in segments if tps]
            return
        if temps:
            ranges[slot] = temps
    for slot, temps in ranges.items():
        setattr(result, slot, temps)
```

- [ ] **Step 5 : lancer les tests, vérifier qu'ils passent**

```bash
uv run pytest tests/test_t2area.py -v && uv run ruff check .
```

Attendu : tout PASS.

- [ ] **Step 6 : commit**

```bash
git add app/scrapers/t2area.py tests/test_t2area.py tests/fixtures/t2area_fiche_*.html
git commit -m "feat(scrapers): splits des fiches TCN sur fftri.t2area.com (#51)"
```

---

### Task 6 : orchestration, enregistrement au registre et documentation

Assemble le tout : `scrape_event_all`, le `T2AreaProvider`, le test réseau réel
et la doc. C'est la tâche qui rend le provider utilisable par l'API et la CLI.

**Files:**
- Modify: `backend/app/scrapers/t2area.py`
- Modify: `backend/app/scrapers/registry.py:19-28` (imports), `:175-184` (après
  `ChronoplaceProvider`), `:201-210` (liste `PROVIDERS`)
- Modify: `backend/tests/test_t2area.py`
- Modify: `backend/tests/test_integration_scrapers.py:20-38` (dict `LIVE_URLS`)
- Modify: `AGENTS.md` (section « Fournisseurs supportés »)

**Interfaces:**
- Consomme : tout ce qui précède.
- Produit : `scrape_event_all(url: str) -> list[ScrapedResult]` et
  `registry.T2AreaProvider` (`name = "t2area"`).

- [ ] **Step 1 : écrire les tests qui échouent**

Ajouter en fin de `backend/tests/test_t2area.py` :

```python
PAGES_LABAULE = {
    "/triathlon-m/2022.html": EDITION_LABAULE,
    "/triathlon-m.html": EPREUVE_LABAULE,
    "/2022/bib-566.html": FICHE_TRIATHLON,
    "/2022/bib-983.html": FICHE_TRIATHLON,
}


def _client_factice(monkeypatch, pages=None, defaut=None):
    client = FakeClient(pages if pages is not None else dict(PAGES_LABAULE), defaut)
    monkeypatch.setattr(t2area.httpx, "Client", lambda *a, **k: client)
    return client


def test_scrape_event_all_ne_charge_que_les_fiches_tcn(monkeypatch):
    """25 requêtes sur les 901 lignes réelles : le coût est borné par l'effectif du club."""
    client = _client_factice(monkeypatch)

    resultats = t2area.scrape_event_all(URL_EDITION)

    assert len(resultats) == 6
    assert client.calls == [
        URL_EDITION,
        "https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2022/bib-566.html",
        "https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2022/bib-983.html",
    ]


def test_scrape_event_all_applique_les_splits_aux_seuls_tcn(monkeypatch):
    _client_factice(monkeypatch)

    resultats = t2area.scrape_event_all(URL_EDITION)

    assert _par_nom(resultats, "ACCENT").swim_time == "00:41:16"
    assert _par_nom(resultats, "ANTOINE").swim_time == ""


def test_scrape_event_all_tronque_une_url_de_fiche(monkeypatch):
    """Le cas réel du Sheet : le lien pointe une fiche, on importe toute l'édition."""
    client = _client_factice(monkeypatch)

    resultats = t2area.scrape_event_all(URL_FICHE)

    assert len(resultats) == 6
    assert client.calls[0] == URL_EDITION


def test_scrape_event_all_source_url_est_ledition_canonique(monkeypatch):
    """Fiche et édition désignent le même classement : on stocke la forme canonique,
    pour qu'un `rescrape-db` ne reparte pas d'une URL de fiche."""
    _client_factice(monkeypatch)

    resultats = t2area.scrape_event_all(URL_FICHE)

    assert {r.source_url for r in resultats} == {URL_EDITION}


def test_scrape_event_all_url_depreuve_resout_la_derniere_edition(monkeypatch):
    client = _client_factice(monkeypatch)

    resultats = t2area.scrape_event_all(URL_EPREUVE)

    assert client.calls[0] == URL_EPREUVE
    assert client.calls[1] == URL_EDITION
    assert len(resultats) == 6


def test_scrape_event_all_fiche_en_echec_nemporte_pas_lepreuve(monkeypatch, caplog):
    pages = dict(PAGES_LABAULE)
    pages["/2022/bib-983.html"] = FakeResponse("", 500)
    _client_factice(monkeypatch, pages=pages)

    with caplog.at_level(logging.WARNING, logger="app.scrapers.t2area"):
        resultats = t2area.scrape_event_all(URL_EDITION)

    assert len(resultats) == 6
    assert _par_nom(resultats, "ACCENT").swim_time == "00:41:16"
    assert "bib-983" in caplog.text


def test_scrape_event_all_edition_inexistante_leve(monkeypatch):
    """Le site répond 303 vers son accueil : pas de classement vide silencieux."""
    _client_factice(monkeypatch, pages={}, defaut=FakeResponse(
        "<html><body><h1>CALENDRIER DES ÉPREUVES FFTRI</h1></body></html>"
    ))

    with pytest.raises(ValueError, match="Aucun classement"):
        t2area.scrape_event_all(URL_EDITION)


def test_registry_detecte_le_provider():
    from app.scrapers import registry

    assert registry.detect_provider(URL_EDITION) == "t2area"
    assert registry.detect_provider(URL_FICHE) == "t2area"


def test_registry_nattrape_pas_les_autres_sous_domaines_t2area():
    """Allowlist explicite : T2Area sert d'autres fédérations, hors périmètre."""
    from app.scrapers import registry

    assert registry.detect_provider("https://ffn.t2area.com/calendrier/x/y.html") != "t2area"


def test_registry_expose_t2area_comme_ciblable():
    """`provider_names()` alimente la validation de `--provider` en CLI."""
    from app.scrapers import registry

    assert "t2area" in registry.provider_names()
```

Ajouter à `backend/tests/test_integration_scrapers.py`, dans le dict `LIVE_URLS`,
après l'entrée `"chronoplace"` :

```python
    # fftri.t2area.com : plateforme officielle FFTRI, édition figée (901 lignes).
    "t2area": (
        "https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2022.html"
    ),
```

et, en fin de ce même fichier :

```python
@pytest.mark.integration
def test_t2area_epreuve_complete():
    """La Baule M 2022 : classement complet en une requête, splits des seuls TCN."""
    results = registry.scrape_event_all(LIVE_URLS["t2area"])

    assert len(results) > 800
    assert min(r.rank_overall for r in results if r.rank_overall) == 1
    assert any(r.club and "NANTAIS" in r.club.upper() for r in results)
    assert all(r.event_date == date(2022, 9, 18) for r in results)
```

- [ ] **Step 2 : lancer les tests, vérifier qu'ils échouent**

```bash
uv run pytest tests/test_t2area.py -k "scrape_event_all or registry" -v
```

Attendu : ÉCHEC, `AttributeError: … has no attribute 'scrape_event_all'`.

- [ ] **Step 3 : implémenter l'orchestration**

Ajouter à la fin de `backend/app/scrapers/t2area.py` :

```python
def scrape_event_all(url: str) -> list[ScrapedResult]:
    """Tous les participants d'une **édition**. Un appel = une `Course`.

    Les splits ne sont chargés que pour les lignes dont le club passe
    `core.club.is_tcn` : ils vivent sur la fiche individuelle, soit une requête
    par participant. Coût mesuré sur La Baule M 2022 : 25 requêtes (1 classement
    + 24 membres TCN sur 901 lignes) — borné par l'effectif du club, pas par la
    taille de l'épreuve. Le scraper devient conscient du club, mais **réutilise**
    la définition unique de `core/club.py` (règle de #76).

    `source_url` est l'URL **canonique** de l'édition, même si l'appel est parti
    d'une fiche individuelle : les deux désignent le même classement, et la forme
    canonique rend le `rescrape-db` suivant idempotent.
    """
    evenement, epreuve, annee = _parse_url(url)
    with httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS) as client:
        if not annee:
            annee = _resolve_annee(client, evenement, epreuve)
        edition_url = _edition_url(evenement, epreuve, annee)
        resultats = _parse_edition(_fetch(client, edition_url), edition_url, evenement, epreuve)
        fiches = 0
        for resultat in resultats:
            if not is_tcn(resultat.club):
                continue
            fiche_url = resultat.raw_data.get("fiche_url") or ""
            if not fiche_url:
                continue
            try:
                html = _fetch(client, fiche_url)
            except httpx.HTTPError as exc:
                # Une fiche qui tombe ne doit pas emporter l'épreuve entière.
                logger.warning("Fiche fftri %s ignorée : %s", fiche_url, exc)
                continue
            _appliquer_splits(resultat, _parse_fiche(html))
            fiches += 1
    logger.info(
        "fftri.t2area.com : %d participants sur %s (%d fiche(s) TCN chargée(s))",
        len(resultats), edition_url, fiches,
    )
    return resultats
```

- [ ] **Step 4 : enregistrer le provider**

Dans `backend/app/scrapers/registry.py`, ajouter `t2area` à l'import groupé (ordre
alphabétique, après `sportinnovation`) :

```python
from app.scrapers import (
    breizhchrono,
    chronoplace,
    klikego,
    prolivesport,
    raceresult,
    sportinnovation,
    t2area,
    timepulse,
    wiclax,
)
```

Ajouter la classe juste après `ChronoplaceProvider` :

```python
class T2AreaProvider:
    name = "t2area"

    def matches(self, url: str) -> bool:
        # Allowlist **explicite** du seul host FFTRI : T2Area sert d'autres
        # fédérations sur d'autres sous-domaines, hors périmètre de #51.
        # `hostname` (et non `netloc`) : un port explicite ou des credentials
        # feraient rater le match.
        return (urlparse(url).hostname or "").lower() == "fftri.t2area.com"

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return t2area.scrape_event_all(url)
```

Ajouter l'instance en fin de liste `PROVIDERS` (aucune ambiguïté avec un provider
existant → pas de contrainte d'ordre) :

```python
PROVIDERS: list[ScraperProtocol] = [
    BreizhChronoProvider(),
    WiclaxProvider(),
    KlikegoProvider(),
    TimePulseProvider(),
    ProLiveSportProvider(),
    SportInnovationProvider(),
    RaceResultProvider(),
    ChronoplaceProvider(),
    T2AreaProvider(),
]
```

- [ ] **Step 5 : lancer toute la suite unitaire**

```bash
uv run pytest -m "not integration" -q && uv run ruff check .
```

Attendu : toute la suite PASS (≈ 800 tests), ruff sans erreur.

- [ ] **Step 6 : lancer le test réseau réel**

```bash
uv run pytest -m integration -k t2area -v
```

Attendu : `test_detection[t2area-…]`, `test_scrape_event_all_live[t2area-…]` et
`test_t2area_epreuve_complete` PASS. Si le site est injoignable, le noter et
relancer — ne pas « corriger » le scraper sur la foi d'un échec réseau.

- [ ] **Step 7 : documenter**

Dans `AGENTS.md`, section « Fournisseurs supportés » :

1. Ajouter `T2Area (FFTRI)` à la liste d'ouverture :

```
Klikego, Breizh Chrono, TimePulse, Wiclax/G-Live, ProLiveSport, Sportinnovation,
RaceResult, Chronoplace, T2Area (FFTRI) — tous en **épreuve complète**.
```

2. Ajouter, à la fin de la section (juste avant la ligne « Types : Triathlon
   XS/S/M/L/XL… ») :

```markdown
`fftri.t2area.com` (T2Area) est la plateforme officielle de la FFTRI : Joomla
server-rendered, classement complet en **une** requête, **aucune pagination**.
L'URL accepte trois profondeurs — édition (`/calendrier/<événement>/<épreuve>/<année>.html`,
le cas nominal), fiche individuelle (**tronquée** vers son édition, la forme du
Sheet) et épreuve sans année (1 GET de plus, on prend la dernière édition
publiée). Une URL d'**événement** est refusée : ses épreuves ont des dernières
éditions d'années différentes, un fan-out n'aurait pas d'année lisible. Un appel
= une `Course`.

Deux particularités structurantes. **Les splits ne sont pas dans le classement** :
ils vivent sur la fiche individuelle, soit une requête par participant — le
scraper ne charge donc que les fiches des membres du TCN (25 requêtes sur les 901
lignes de La Baule M 2022). C'est le seul scraper conscient du club ; il
**réutilise** `core/club.py`, il ne le réimplémente pas (#76). Et **la FFTRI
republie** : chaque page porte « Résultats produits par X ». Quand X est un
provider supporté, un avertissement est journalisé — mais la mention ne lie que
l'accueil du chronométreur, jamais l'épreuve, donc aucune URL source n'est
constructible : seul l'opérateur peut la fournir.

Détails de lecture : colonnes lues **par libellé d'en-tête** (l'en-tête réel en
porte 10, `id_league` et `league` s'intercalant avant `Détails`) ; `00:00:00` vaut
temps absent (un DNF sort avec cette valeur) ; `bib_number` n'est rempli que
lorsque la clé de fiche est un vrai dossard (`bib-566`), jamais avec une licence
(`A44719`) ni un identifiant interne (`id-1153352`) ; splits mappés **par
libellé** (`CàP 1`/`CàP 2` en duathlon), un libellé inconnu faisant basculer
toute la fiche sur `segments`. Design :
`docs/superpowers/specs/2026-07-26-t2area-scraper-design.md`, plan :
`docs/superpowers/plans/2026-07-26-t2area-scraper.md`.
```

- [ ] **Step 8 : commit**

```bash
git add app/scrapers/t2area.py app/scrapers/registry.py tests/test_t2area.py \
        tests/test_integration_scrapers.py ../AGENTS.md
git commit -m "feat(scrapers): support de fftri.t2area.com (#51)"
```

---

## Limites assumées (à ne pas « corriger » en cours de route)

Reprises du §8 du design, plus une constatée au re-sondage.

1. **Noms tout en majuscules** (`PANNIER ANAIS`, 69 lignes sur 163 à Embrun 2025) :
   `split_athlete_name` en fait un nom sans prénom. Limite documentée et
   irréductible sans information supplémentaire. **Aucune heuristique locale au
   scraper** : elle divergerait du reste du code. Les licenciés français sortent
   en casse propre (`ACCENT Baptiste`).
2. **Lignes anonymes** (`907 Dossard`, 1 sur 901 à La Baule 2022) : la source
   publie un libellé de remplacement, le scraper le transcrit tel quel.
   `test_parse_edition_ligne_anonyme_du_site` verrouille ce comportement.
3. **Doublon de `Course` inter-provider** : une même épreuve déjà importée depuis
   son chronométreur portera un nom différent ;
   `UNIQUE(name, event_date, event_type)` ne les fusionnera pas. Hors périmètre de #51.
4. **Relais / épreuves `-eq`** : `is_relay` déduit du slug, **non vérifié sur
   données réelles** — aucune épreuve équipe sondée n'a de classement publié.
5. **Splits des non-TCN** : jamais chargés. Un membre qui rejoint le club après
   coup n'aura ses splits qu'au prochain `rescrape-db`, une fois son libellé de
   club à jour.
6. **AltiChrono et EventiCom** sont deux chronométreurs que #33 ne recense pas
   encore : à y remonter, hors de ce plan.
