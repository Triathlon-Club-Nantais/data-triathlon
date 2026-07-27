# Scraper ok-time.fr — plan d'implémentation (issue #52)

> **Pour les agents :** SOUS-COMPÉTENCE REQUISE — utiliser
> `superpowers:subagent-driven-development` (recommandé) ou
> `superpowers:executing-plans` pour exécuter ce plan tâche par tâche. Les étapes
> sont en cases à cocher (`- [ ]`) pour le suivi.

**Objectif :** ajouter `ok-time.fr` à la liste des fournisseurs de chronométrage
supportés, en lisant l'API JSON WordPress publique du site — un seul appel rend
l'événement entier, toutes épreuves comprises.

**Architecture :** un module `backend/app/scrapers/oktime.py` qui sépare l'I/O
(deux fonctions seulement touchent le réseau : `_resolve_event_id` et
`_fetch_results`) des fonctions pures de transformation. Un `OkTimeProvider`
enregistré dans `scrapers/registry.py` sur une allowlist de host. Les points de
passage cumulés sont différenciés en durées de segment et rangés dans
`ScrapedResult.segments` (chemin générique déplafonné), pas dans les 5 slots
positionnels.

**Pile technique :** Python 3.13, `uv`, `httpx`, `BeautifulSoup`/`lxml`
(uniquement pour la page HTML de résolution de slug), `pytest`, `ruff`.

**État de vérification :** le code et les tests de ce plan ont été assemblés et
**exécutés** avant publication, contre le vrai paquet `app.scrapers` —
103 tests verts à l'origine (108 aujourd'hui, après les correctifs de revue
finale détaillés dans l'encadré ci-dessous), `ruff check` propre, et
l'allowlist de host validée contre les providers existants (aucun conflit ;
`ok-time.fr` tombe aujourd'hui sur le fallback `playwright`). Les comptes de
tests annoncés à chaque tâche sont donc des cibles réelles, pas des
estimations. Seul le test `integration` (réseau réel) reste à confronter à la
source.

> **Amendement de revue finale (2026-07-27, #52).** Trois constats de la revue de
> branche ont fait diverger le code livré de ce plan. Le plan a été amendé pour
> ne plus le contredire — un plan qui contredit le code est un piège pour le
> prochain lecteur. Chaque écart est signalé sur place par une note encadrée :
>
> | Constat | Où | En un mot |
> | --- | --- | --- |
> | **I1** — la garde « liste d'engagés » jetait les courses **en cours** | tâche 7 | deux prédicats séparés au lieu d'un seul `non_chronometree` (+ `_points_cumules`, tâche 5) |
> | **I2** — cinq invariants de course recalculés par participant | tâche 7 | sortis de la compréhension ; le coût redevient linéaire |
> | **M1** — l'identité anonyme fusionnait les participants **sans dossard** | tâche 3 | identité synthétique seulement quand le dossard la rend discriminante |
>
> Le module compte désormais 108 tests unitaires (103 + 5 ajoutés en revue). Les
> comptes annoncés à chaque tâche ont été ajustés en conséquence. La spec
> (`docs/superpowers/specs/2026-07-26-oktime-scraper-design.md`) reste inchangée
> et prime toujours : ces corrections la servent, elles ne la contredisent pas —
> I1 réalise enfin l'intention explicite de son §3.1.

**Spec de référence :** `docs/superpowers/specs/2026-07-26-oktime-scraper-design.md`
(design approuvé, chiffres mesurés sur un panel de 21 événements / 99 courses /
12 644 participations le 2026-07-26). En cas de doute, la spec prime sur ce plan.

## Contraintes globales

Elles s'appliquent implicitement à **toutes** les tâches :

- **Langue** : code, commentaires, docstrings, messages de log et messages
  d'erreur en **français avec accents**. Les noms de tests aussi
  (`test_parse_url_forme_classement`), à l'image de `tests/test_chronoplace.py`.
- **Tests sans réseau** : tout test unitaire passe `uv run pytest -m "not integration"`
  hors ligne. Le seul appel réseau réel vit derrière `@pytest.mark.integration`.
- **Commandes** : toutes lancées depuis `backend/`. Pas de venv à activer,
  `uv run` s'en charge.
- **Lint** : `uv run ruff check .` doit passer à chaque commit. Les règles `E`, `F`,
  `I`, `W`, `UP`, `B` sont actives (`backend/pyproject.toml`) : **tous les imports
  restent en tête de fichier** (E402) et **aucun import inutilisé** n'est toléré
  (F401). Chaque tâche complète donc le bloc d'imports existant plutôt que
  d'ajouter un import au milieu du fichier — et n'ajoute que ceux qu'elle
  utilise. Un import ponctuel à l'intérieur d'une fonction de test reste permis
  (motif déjà présent dans `tests/test_chronoplace.py`).
- **TDD strict** : test qui échoue → implémentation minimale → test qui passe →
  commit. Ne jamais écrire d'implémentation avant d'avoir vu le test rouge.
- **Commits** : Conventional Commits, un par tâche, suffixés `(#52)`.
  Ex. `feat(scrapers): oktime résout les deux formes d'URL (#52)`.
- **Nom de provider** : `oktime` (minuscules, sans tiret) — il part en base dans
  `Course.provider` et sert de valeur à `--provider` en CLI. **Ne pas** écrire
  `ok-time` ni `ok_time`.
- **Ne jamais réimplémenter** : `split_athlete_name`, `normalize_time`,
  `normalize_rank`, `qualify_event_name` (dans `scrapers/utils.py`),
  `classify_event_type` (dans `scrapers/classify.py`), `is_tcn`
  (`app/core/club.py`). Les importer.
- **`ScrapedResult`** (`app/scrapers/base.py`) est le seul type de sortie ;
  les temps y sont des **strings** `"hh:mm:ss"`.
- **Aucun Playwright, aucun parsing HTML sur le chemin nominal** : une seule
  requête API suffit. Le seul GET HTML sert à résoudre un slug en id.

---

## Structure des fichiers

| Fichier | Responsabilité |
| --- | --- |
| `backend/app/scrapers/oktime.py` (créé) | Tout le scraper : résolution d'URL, appel API, transformation en `ScrapedResult`. |
| `backend/tests/test_oktime.py` (créé) | Tests unitaires sans réseau. |
| `backend/tests/fixtures/oktime_evenement_page.html` (créé) | Page `/evenement/<slug>/` réduite, porteuse du lien de classement. |
| `backend/tests/fixtures/oktime_lacanau_48555.json` (créé) | Charge API réduite : 2 courses, splits cumulés, statuts, mojibake, relais, RGPD. |
| `backend/tests/fixtures/oktime_engages_48999.json` (créé) | Charge API réduite : une liste d'engagés à écarter + une course enfants non chronométrée. |
| `backend/app/scrapers/registry.py` (modifié) | Ajout de `OkTimeProvider` et de son entrée dans `PROVIDERS`. |
| `backend/tests/test_integration_scrapers.py` (modifié) | Ajout de l'URL réelle 48555 dans `LIVE_URLS`. |
| `AGENTS.md` (modifié) | Section « Fournisseurs supportés ». |

Un seul module de scraper : c'est la convention du projet (`chronoplace.py`,
`timepulse.py`… sont chacun d'un seul tenant), et le découpage interne se fait
par fonctions pures, pas par fichiers.

---

## Rappel : les fonctions partagées à réutiliser

Lire ces signatures avant de commencer, elles reviennent dans presque toutes les
tâches.

```python
# app/scrapers/base.py
STATUS_FINISHER = "finisher"; STATUS_DNF = "DNF"; STATUS_DNS = "DNS"; STATUS_DSQ = "DSQ"

@dataclass
class ScrapedResult:
    source_url: str
    provider: str
    athlete_name: str = ""       # NOM de famille
    athlete_firstname: str = ""
    club: str = ""
    category: str = ""
    gender: str = ""             # "M" / "F" / ""
    bib_number: str = ""
    event_name: str = ""
    event_date: date | None = None
    event_type: str = ""
    rank_overall: int | None = None
    rank_category: int | None = None
    rank_gender: int | None = None
    total_time: str = ""
    swim_time: str = ""; t1_time: str = ""; bike_time: str = ""
    t2_time: str = ""; run_time: str = ""      # 5 slots positionnels — NON utilisés ici
    segments: list[tuple[str, str]] | None = None   # chemin générique, déplafonné
    distance_km: float | None = None
    is_relay: bool = False
    status: str = ""             # "" = l'infra applique son heuristique
    raw_data: dict[str, Any] = field(default_factory=dict)

# app/scrapers/utils.py
def normalize_time(raw: str) -> str          # "1:23:45" → "01:23:45" ; "" → ""
def normalize_rank(val) -> int | None        # "3e" → 3 ; None → None ; 0 → 0
def split_athlete_name(full: str) -> tuple[str, str]   # → (nom, prénom)
def qualify_event_name(event_name: str, qualifiant: str) -> str
    # « Triathlon de X » + « Distance M » → « Triathlon de X - Distance M »
    # Un qualifiant déjà contenu dans le nom n'est pas ré-ajouté.

# app/scrapers/classify.py
def classify_event_type(text: str) -> str    # texte libre → slug canonique
```

---

### Tâche 1 : squelette du module et résolution d'URL

Le point d'entrée du scraper : reconnaître les deux formes d'URL vivantes, et
rejeter explicitement les trois formes obsolètes du Sheet (§2.1 du design) avec
un message qui se lit sans enquête dans le détail des échecs de la CLI.

**Fichiers :**
- Créer : `backend/app/scrapers/oktime.py`
- Créer : `backend/tests/test_oktime.py`

**Interfaces :**
- Consomme : rien (première tâche).
- Produit :
  - `BASE_URL: str` = `"https://ok-time.fr"`
  - `API_PATH: str` = `"/wp-json/gmcap/v1/evenements/{event_id}/results"`
  - `HEADERS: dict[str, str]`
  - `logger: logging.Logger`
  - `_parse_url(url: str) -> tuple[str, str]` → `(event_id, slug)`. Exactement
    l'un des deux est non vide. Lève `ValueError` sur toute autre forme.

- [ ] **Étape 1 : écrire les tests qui échouent**

Créer `backend/tests/test_oktime.py` :

```python
"""
Tests unitaires pour scrapers/oktime.py (sans réseau).

Les fixtures sont des charges API réduites, calquées sur le schéma mesuré au
panel du 2026-07-26 (cf. docs/superpowers/specs/2026-07-26-oktime-scraper-design.md).
Le schéma réel est revérifié par le test `integration` sur l'événement 48555.
"""
import pytest

from app.scrapers import oktime


def test_parse_url_forme_classement():
    """`classement.ok-time.fr/<id>` : l'id du chemin EST le post-id WordPress."""
    assert oktime._parse_url("https://classement.ok-time.fr/48555") == ("48555", "")


def test_parse_url_ignore_le_segment_race():
    """L'API ne sait pas filtrer par épreuve : `/race/<id>` est sans effet."""
    assert oktime._parse_url("https://classement.ok-time.fr/48555/race/59697") == ("48555", "")


def test_parse_url_tolere_le_slash_final():
    assert oktime._parse_url("https://classement.ok-time.fr/48555/") == ("48555", "")


def test_parse_url_forme_evenement_rend_le_slug():
    """La forme éditoriale n'expose pas l'id : il faudra une requête pour le lire."""
    assert oktime._parse_url("https://ok-time.fr/evenement/triathlon-de-lacanau-2026/") == (
        "",
        "triathlon-de-lacanau-2026",
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://ok-time.fr/course/format-s-individuel-3/",
        "https://ok-time.fr/competition/t24-ile-de-re-2025/",
        "https://ok-time.fr/course/triathlon-l/",
    ],
)
def test_parse_url_rejette_les_formes_obsoletes(url):
    """Les 3 URLs mortes du Sheet : erreur qualifiée, pour se lire sans enquête.

    ok-time devenant un host supporté, elles quittent `ignored_by_host` et
    deviennent des épreuves en erreur dans les bilans CLI (§2.1 du design). Le
    message doit dire pourquoi.
    """
    with pytest.raises(ValueError, match="obsolète"):
        oktime._parse_url(url)


def test_parse_url_rejette_une_page_hors_resultats():
    with pytest.raises(ValueError, match="non reconnue"):
        oktime._parse_url("https://ok-time.fr/contact/")
```

- [ ] **Étape 2 : lancer les tests et vérifier qu'ils échouent**

```bash
uv run pytest tests/test_oktime.py -v
```
Attendu : ÉCHEC — `ModuleNotFoundError` / `ImportError: cannot import name 'oktime'`.

> **Note sur les imports du fichier de test** : le bloc d'imports ci-dessus est
> volontairement minimal. Les tâches suivantes le **complètent en place**
> (`json`, `logging`, `html`, `date`, `Path`, `httpx`), jamais au milieu du
> fichier — ruff refuserait (E402), et un import ajouté trop tôt serait refusé
> comme inutilisé (F401).

- [ ] **Étape 3 : écrire l'implémentation minimale**

Créer `backend/app/scrapers/oktime.py` :

```python
"""
Scraper ok-time.fr — API JSON WordPress publique (issue #52).

`classement.ok-time.fr` est une SPA React, mais toutes ses données transitent par
une route WordPress publique. **Un seul appel** rend l'événement entier, toutes
épreuves comprises :

    GET https://ok-time.fr/wp-json/gmcap/v1/evenements/{eventId}/results

Ni Playwright ni parsing HTML sur le chemin nominal : le seul GET HTML sert à
lire l'id d'événement quand l'URL est de la forme éditoriale `/evenement/<slug>/`.

Flux (cf. docs/superpowers/specs/2026-07-26-oktime-scraper-design.md) :
  1. `_parse_url`         → id direct, ou slug à résoudre
  2. `_resolve_event_id`  → 1 GET HTML, id lu dans le lien de classement
  3. `_fetch_results`     → l'appel API, erreurs de la source traduites
  4. `_course_results`    → une épreuve de la charge → participants
  5. toutes les épreuves de l'événement sont importées (comme les heats
     Breizh Chrono et les onglets chronoplace)

L'API n'expose aucune route par épreuve : une URL pointant une épreuve rapporte
toujours l'événement entier.
"""
import logging
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

BASE_URL = "https://ok-time.fr"
API_PATH = "/wp-json/gmcap/v1/evenements/{event_id}/results"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# `classement.ok-time.fr/<id>` ou `.../<id>/race/<raceId>`. Le segment `race`
# est **ignoré** : l'API ne sait pas filtrer par épreuve, elle rend l'événement.
_ID_PATH_RE = re.compile(r"^/(?P<id>\d+)(?:/race/\d+)?/?$")
# Forme éditoriale actuelle du site.
_SLUG_PATH_RE = re.compile(r"^/evenement/(?P<slug>[^/]+)/?$")
# Formes retirées du site : les 3 URLs mortes du Sheet (§2.1 du design).
_PREFIXES_OBSOLETES = ("/course/", "/competition/")


def _parse_url(url: str) -> tuple[str, str]:
    """(id d'événement, slug) — exactement l'un des deux est non vide.

    Un slug devra être résolu par une requête HTML ; un id part directement à
    l'API. L'id de l'URL de classement **est** le post-id WordPress attendu par
    l'API (vérifié sur les 21 événements du panel) : aucune table de
    correspondance à maintenir.
    """
    path = urlparse(url).path or "/"
    m = _ID_PATH_RE.match(path)
    if m:
        return m.group("id"), ""
    m = _SLUG_PATH_RE.match(path)
    if m:
        return "", m.group("slug")
    if any(path.startswith(prefixe) for prefixe in _PREFIXES_OBSOLETES):
        raise ValueError(
            f"URL ok-time.fr obsolète : {url} — les préfixes /course/ et "
            "/competition/ ont été retirés du site, qui publie sous "
            "/evenement/<slug>/. Lien à corriger à la source."
        )
    raise ValueError(f"URL ok-time.fr non reconnue : {url}")
```

- [ ] **Étape 4 : lancer les tests et vérifier qu'ils passent**

```bash
uv run pytest tests/test_oktime.py -v && uv run ruff check .
```
Attendu : 8 tests PASS, ruff sans erreur.

- [ ] **Étape 5 : commit**

```bash
git add backend/app/scrapers/oktime.py backend/tests/test_oktime.py
git commit -m "feat(scrapers): oktime résout les deux formes d'URL (#52)"
```

---

### Tâche 2 : accès réseau — résolution du slug et appel API

Les deux seules fonctions du module qui touchent le réseau. Les trois erreurs
distinguées par la source (§1.3 du design) deviennent des `ValueError` au message
exploitable : c'est ce message qui apparaît dans « Épreuves en erreur (détail) »
des bilans CLI.

**Fichiers :**
- Modifier : `backend/app/scrapers/oktime.py`
- Modifier : `backend/tests/test_oktime.py`
- Créer : `backend/tests/fixtures/oktime_evenement_page.html`

**Interfaces :**
- Consomme : `BASE_URL`, `API_PATH`, `logger` (tâche 1).
- Produit :
  - `_resolve_event_id(client, slug: str) -> str`
  - `_fetch_results(client, event_id: str) -> dict`
  - Les tests produisent `FakeResponse` / `FakeClient`, réutilisés en tâche 8.

- [ ] **Étape 1 : créer la fixture HTML**

Créer `backend/tests/fixtures/oktime_evenement_page.html` :

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>Triathlon de Lacanau 2026 &#8211; OK TIME</title>
</head>
<body>
  <article class="evenement">
    <h1>Triathlon de Lacanau 2026</h1>
    <p>Rendez-vous le samedi 02 mai 2026.</p>
    <a class="btn btn-classement" href="https://classement.ok-time.fr/48555" target="_blank">
      Voir les classements
    </a>
    <a class="btn" href="https://ok-time.fr/inscriptions/">S'inscrire</a>
  </article>
</body>
</html>
```

- [ ] **Étape 2 : écrire les tests qui échouent**

D'abord, **remplacer** le bloc d'imports en tête de `backend/tests/test_oktime.py` par :

```python
import json
from pathlib import Path

import httpx
import pytest

from app.scrapers import oktime
```

Puis ajouter à la fin du fichier :

```python
FIXTURES = Path(__file__).parent / "fixtures"

PAGE_EVENEMENT = (FIXTURES / "oktime_evenement_page.html").read_text(encoding="utf-8")


class FakeResponse:
    """Réponse HTTP factice, texte + JSON."""

    def __init__(self, contenu, status_code: int = 200):
        self.status_code = status_code
        if isinstance(contenu, str):
            self.text, self._json = contenu, None
        else:
            self.text, self._json = json.dumps(contenu), contenu

    def json(self):
        if self._json is None:
            raise ValueError("réponse non-JSON")
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPError(f"HTTP {self.status_code}")


class FakeClient:
    """Client HTTP factice : sert les réponses et enregistre les URLs demandées."""

    def __init__(self, pages: dict | None = None, defaut: FakeResponse | None = None):
        self.pages = pages or {}
        self.defaut = defaut or FakeResponse("<html>404</html>", 404)
        self.calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url: str):
        self.calls.append(url)
        for motif, reponse in self.pages.items():
            if motif in url:
                return reponse if isinstance(reponse, FakeResponse) else FakeResponse(reponse)
        return self.defaut


def test_resolve_event_id_lit_le_lien_de_classement():
    client = FakeClient({"/evenement/": PAGE_EVENEMENT})

    assert oktime._resolve_event_id(client, "triathlon-de-lacanau-2026") == "48555"
    assert client.calls == ["https://ok-time.fr/evenement/triathlon-de-lacanau-2026/"]


def test_resolve_event_id_sans_lien_leve():
    """Page 200 mais sans lien de classement : la forme `/course/triathlon-l/`
    redirigée vers le listing générique n'a aucun id à offrir."""
    client = FakeClient({"/evenement/": "<html><body>Aucun classement.</body></html>"})

    with pytest.raises(ValueError, match="aucun lien de classement"):
        oktime._resolve_event_id(client, "triathlon-l")


def test_fetch_results_rend_la_charge():
    charge = {"success": True, "evenement_id": 48555, "count": 0, "data": []}
    client = FakeClient({"/wp-json/gmcap/v1/evenements/48555/results": charge})

    assert oktime._fetch_results(client, "48555") == charge
    assert client.calls == [
        "https://ok-time.fr/wp-json/gmcap/v1/evenements/48555/results"
    ]


def test_fetch_results_404_id_inconnu():
    client = FakeClient(
        defaut=FakeResponse({"message": "Ce post n'est pas un evenement."}, 404)
    )

    with pytest.raises(ValueError, match="introuvable"):
        oktime._fetch_results(client, "1")


def test_fetch_results_400_sans_resultats_publies():
    """Événement réel mais sans fichier de résultats : cause distincte du 404."""
    client = FakeClient(
        defaut=FakeResponse(
            {"message": "Aucun fichier_gmcap défini pour cet evenement."}, 400
        )
    )

    with pytest.raises(ValueError, match="aucun résultat publié"):
        oktime._fetch_results(client, "48555")


def test_fetch_results_500_remonte_en_erreur_http():
    """Une panne serveur n'est pas une erreur métier : elle ne doit pas être
    traduite en ValueError, qui la ferait passer pour un lien invalide."""
    client = FakeClient(defaut=FakeResponse("boom", 500))

    with pytest.raises(httpx.HTTPError):
        oktime._fetch_results(client, "48555")


def test_fetch_results_charge_sans_data_leve():
    client = FakeClient({"/results": {"success": False}})

    with pytest.raises(ValueError, match="Charge ok-time inattendue"):
        oktime._fetch_results(client, "48555")
```

`match` est une **regex sensible à la casse** appliquée par `re.search` : elle
doit refléter la casse exacte du message levé.

- [ ] **Étape 3 : lancer les tests et vérifier qu'ils échouent**

```bash
uv run pytest tests/test_oktime.py -v -k "resolve or fetch"
```
Attendu : ÉCHEC — `AttributeError: module 'app.scrapers.oktime' has no attribute '_resolve_event_id'`.

- [ ] **Étape 4 : écrire l'implémentation minimale**

Dans `backend/app/scrapers/oktime.py`, ajouter `import httpx` en tête (après
`import re`) puis, à la suite de `_parse_url` :

```python
# Le lien de classement d'une page `/evenement/<slug>/`. Cherché à la regex sur
# le HTML brut plutôt qu'au parseur : le lien peut vivre dans un attribut, un
# bloc de script ou une iframe selon le thème, et un seul motif les couvre tous.
_CLASSEMENT_ID_RE = re.compile(r"classement\.ok-time\.fr/(\d+)")


def _resolve_event_id(client: httpx.Client, slug: str) -> str:
    """Id d'événement lu sur la page éditoriale. 1 GET HTML, aucun autre usage.

    Une page servie mais dépourvue de lien de classement est le cas des slugs
    redirigés vers le listing générique (§2.1 du design) : il n'y a rien à en
    tirer, l'erreur doit le dire.
    """
    url = f"{BASE_URL}/evenement/{slug}/"
    response = client.get(url)
    response.raise_for_status()
    m = _CLASSEMENT_ID_RE.search(response.text)
    if not m:
        raise ValueError(
            f"Page ok-time.fr « {slug} » sans aucun lien de classement : "
            "événement sans résultats publiés, ou slug redirigé vers le listing."
        )
    return m.group(1)


def _fetch_results(client: httpx.Client, event_id: str) -> dict:
    """La charge JSON de l'événement entier. Erreurs de la source traduites.

    L'API distingue ses deux échecs métier (§1.3 du design), on les garde
    distincts : un 404 dit « cet id n'existe pas », un 400 dit « cet événement
    existe mais n'a rien publié ». Toute autre erreur HTTP (5xx…) remonte telle
    quelle : ce n'est pas un problème de lien, et la traduire en ValueError la
    ferait passer pour tel dans le bilan CLI.
    """
    url = f"{BASE_URL}{API_PATH.format(event_id=event_id)}"
    response = client.get(url)
    if response.status_code == 404:
        raise ValueError(
            f"Événement ok-time introuvable (id {event_id}) : seul un id "
            "d'événement est accepté, pas un id d'épreuve."
        )
    if response.status_code == 400:
        raise ValueError(
            f"Événement ok-time {event_id} : aucun résultat publié à ce jour."
        )
    response.raise_for_status()
    charge = response.json()
    if not isinstance(charge, dict) or "data" not in charge:
        raise ValueError(
            f"Charge ok-time inattendue pour l'événement {event_id} : "
            "clé « data » absente."
        )
    return charge
```

- [ ] **Étape 5 : lancer les tests et vérifier qu'ils passent**

```bash
uv run pytest tests/test_oktime.py -v && uv run ruff check .
```
Attendu : 15 tests PASS.

- [ ] **Étape 6 : commit**

```bash
git add backend/app/scrapers/oktime.py backend/tests/test_oktime.py \
        backend/tests/fixtures/oktime_evenement_page.html
git commit -m "feat(scrapers): oktime interroge l'API et traduit ses erreurs (#52)"
```

---

### Tâche 3 : identité de l'athlète — mojibake, équipes, RGPD

Trois fonctions pures qui décident sous quel nom un participant entre en base.
Chacune répare un travers mesuré de la source : encodage cp1252 dans `nom`, noms
d'équipe qu'il ne faut pas découper, et participants anonymisés qu'il ne faut pas
fusionner entre épreuves.

**Fichiers :**
- Modifier : `backend/app/scrapers/oktime.py`
- Modifier : `backend/tests/test_oktime.py`

**Interfaces :**
- Consomme : `split_athlete_name` (`scrapers/utils.py`).
- Produit :
  - `_repair_mojibake(s: str) -> str`
  - `_is_relay_course(title: str, runners: list[dict]) -> bool`
  - `_athlete_identity(runner: dict, *, is_relay: bool, epreuve_id: str) -> tuple[str, str]`
    → `(nom, prénom)`

- [ ] **Étape 1 : écrire les tests qui échouent**

Ajouter à `backend/tests/test_oktime.py` :

```python
# --------------------------------------------------------------------------- #
# Identité : mojibake, équipes, RGPD
# --------------------------------------------------------------------------- #

def test_repair_mojibake_repare_un_nom_cp1252():
    """173 participations du panel portent ce travers, sur les événements anciens."""
    assert oktime._repair_mojibake("AnaÃ¯s MOUSQUET") == "Anaïs MOUSQUET"


def test_repair_mojibake_laisse_intact_un_nom_accentue_sain():
    """Non-régression mesurée : les 1 061 noms accentués sains du panel traversent
    la réparation inchangés. Un faux positif scinderait un athlète en deux."""
    assert oktime._repair_mojibake("Anaïs MOUSQUET") == "Anaïs MOUSQUET"


@pytest.mark.parametrize("nom", ["", "Paul MARTIN", "Łukasz KOWALSKI", "T... B..."])
def test_repair_mojibake_neutre_sur_les_autres_cas(nom):
    """Chaîne vide, ASCII pur, caractère hors cp1252, nom anonymisé : inchangés."""
    assert oktime._repair_mojibake(nom) == nom


@pytest.mark.parametrize(
    "titre",
    ["Relais L", "Triathlon M Équipe", "Course Duo", "Team Challenge"],
)
def test_is_relay_course_par_le_titre(titre):
    assert oktime._is_relay_course(titre, []) is True


def test_is_relay_course_binome_non_titre():
    """Bike & Run de la pomme et de la châtaigne : « Course S » est un binôme
    qui ne le dit pas — 100 % de ses noms portent « / »."""
    runners = [{"nom": "A DUPONT / B MARTIN"}, {"nom": "C DURAND / D PETIT"}]

    assert oktime._is_relay_course("Course S", runners) is True


def test_is_relay_course_binome_isole_ne_bascule_pas_la_course():
    """« Format M individuel » : 1 nom sur 57 porte « / ». Un « au moins un »
    ferait basculer la course entière en relais."""
    runners = [{"nom": "A DUPONT / B MARTIN"}] + [{"nom": f"Paul MARTIN{i}"} for i in range(56)]

    assert oktime._is_relay_course("Format M individuel", runners) is False


def test_is_relay_course_sans_participant():
    assert oktime._is_relay_course("Triathlon S", []) is False


def test_athlete_identity_convention_prenom_nom():
    nom, prenom = oktime._athlete_identity(
        {"nom": "Valentin ROUVIER"}, is_relay=False, epreuve_id="59697"
    )

    assert (nom, prenom) == ("ROUVIER", "Valentin")


def test_athlete_identity_repare_le_mojibake_avant_de_scinder():
    nom, prenom = oktime._athlete_identity(
        {"nom": "AnaÃ¯s MOUSQUET"}, is_relay=False, epreuve_id="59697"
    )

    assert (nom, prenom) == ("MOUSQUET", "Anaïs")


def test_athlete_identity_nom_dequipe_non_mutile():
    """Précédent RaceResult (#63) : un nom d'équipe entre entier dans `nom`."""
    nom, prenom = oktime._athlete_identity(
        {"nom": "GUILLON RÉMI / CHARPENTIER EMMANUEL"}, is_relay=True, epreuve_id="59698"
    )

    assert (nom, prenom) == ("GUILLON RÉMI / CHARPENTIER EMMANUEL", "")


def test_athlete_identity_binome_isole_en_course_individuelle():
    """Garde par valeur : « / » suffit, même hors course de relais."""
    nom, prenom = oktime._athlete_identity(
        {"nom": "A DUPONT / B MARTIN"}, is_relay=False, epreuve_id="59697"
    )

    assert (nom, prenom) == ("A DUPONT / B MARTIN", "")


def test_athlete_identity_nom_dequipe_pur_en_course_relais():
    nom, prenom = oktime._athlete_identity(
        {"nom": "TEAM TCC"}, is_relay=True, epreuve_id="59698"
    )

    assert (nom, prenom) == ("TEAM TCC", "")


def test_athlete_identity_rgpd_identite_synthetique():
    """`rgpd:"N"` → nom amputé à la source (« T... B... ») : identité synthétique."""
    nom, prenom = oktime._athlete_identity(
        {"nom": "T... B...", "dossard": 927, "rgpd": "N"},
        is_relay=False,
        epreuve_id="59697",
    )

    assert (nom, prenom) == ("Anonyme 59697-927", "")


def test_athlete_identity_rgpd_distincte_entre_deux_epreuves():
    """`Athlete` est unique sur (nom, prénom, date de naissance) : sans la clé
    d'épreuve, les dossards 927 anonymes de deux courses fusionneraient en un
    athlète agrégeant deux personnes."""
    commun = {"nom": "T... B...", "dossard": 927, "rgpd": "N"}

    a = oktime._athlete_identity(commun, is_relay=False, epreuve_id="59697")
    b = oktime._athlete_identity(commun, is_relay=False, epreuve_id="60101")

    assert a != b


# Ajoutés en revue finale (cf. la note de fin de tâche) : sans dossard,
# l'identité synthétique n'est plus discriminante.
def test_athlete_identity_rgpd_sans_dossard_garde_le_nom_ampute():
    nom, prenom = oktime._athlete_identity(
        {"nom": "T... B...", "dossard": None, "rgpd": "N"},
        is_relay=False,
        epreuve_id="59697",
    )

    assert (nom, prenom) == ("T... B...", "")


def test_athlete_identity_rgpd_sans_dossard_ne_fusionne_pas_deux_personnes():
    a = oktime._athlete_identity(
        {"nom": "T... B...", "dossard": None, "rgpd": "N"}, is_relay=False, epreuve_id="59697"
    )
    b = oktime._athlete_identity(
        {"nom": "M... D...", "dossard": None, "rgpd": "N"}, is_relay=False, epreuve_id="59697"
    )

    assert a != b
```

- [ ] **Étape 2 : lancer les tests et vérifier qu'ils échouent**

```bash
uv run pytest tests/test_oktime.py -v -k "mojibake or relay_course or identity"
```
Attendu : ÉCHEC — `AttributeError: ... has no attribute '_repair_mojibake'`.

- [ ] **Étape 3 : écrire l'implémentation minimale**

Ajouter en tête de `oktime.py`, dans les imports :

```python
from .utils import split_athlete_name
```

Puis, à la suite de `_fetch_results` :

```python
# --------------------------------------------------------------------------- #
# Identité de l'athlète
# --------------------------------------------------------------------------- #

def _repair_mojibake(s: str) -> str:
    """Répare un texte UTF-8 relu en cp1252 (« AnaÃ¯s » → « Anaïs »).

    Mesuré sur `nom` **uniquement** (173 participations du panel, concentrées sur
    les 4 événements les plus anciens) : `club` et `categorie` en sont indemnes,
    on ne les touche donc pas.

    La conversion n'est retenue que si elle **aboutit** : un nom déjà sain
    échoue au décodage UTF-8 (« Anaïs » → b'Ana\\xefs', 0xEF sans continuation
    valide) et ressort inchangé. Un caractère hors cp1252 (« Łukasz ») échoue à
    l'encodage, même issue. Contrôle de non-régression : les 1 061 noms
    accentués sains du panel traversent intacts.
    """
    try:
        return s.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


_ACCENTS = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")
# Marqueurs d'une course d'équipes dans le titre, comparés sans accents ni casse.
_RELAY_TITRE_RE = re.compile(r"relais|equipe|duo|team")
# Séparateur de coéquipiers dans un nom (« GUILLON RÉMI / CHARPENTIER EMMANUEL »).
# Testé sans les espaces qui l'entourent : une graphie collée resterait un binôme.
_SEPARATEUR_EQUIPE = "/"


def _is_relay_course(title: str, runners: list[dict]) -> bool:
    """`is_relay` de **toute** la course : titre parlant, ou majorité de binômes.

    Décidé au niveau de la course, jamais du participant : sinon
    `Course.is_relay` et `Participation.is_relay` divergeraient selon l'ordre des
    participants dans la charge.

    Le titre seul ne suffit pas (les courses du Bike & Run de la pomme et de la
    châtaigne sont des binômes muets), et « au moins un » ne convient pas non
    plus (il basculerait « Format M individuel », 1 nom sur 57, en relais). D'où
    la **majorité stricte**.
    """
    if _RELAY_TITRE_RE.search((title or "").lower().translate(_ACCENTS)):
        return True
    noms = [str(runner.get("nom") or "") for runner in runners]
    if not noms:
        return False
    binomes = sum(1 for nom in noms if _SEPARATEUR_EQUIPE in nom)
    return binomes * 2 > len(noms)


def _athlete_identity(runner: dict, *, is_relay: bool, epreuve_id: str) -> tuple[str, str]:
    """(nom, prénom) — un nom d'équipe n'est jamais découpé (précédent #63).

    Trois régimes :

    1. `rgpd:"N"` **avec dossard** — la source ampute le nom (« T... B... ») mais
       publie temps et rang. Identité synthétique « Anonyme <epreuve_id>-<dossard> »,
       prénom vide. La clé d'épreuve est **indispensable** : `Athlete` étant
       unique sur (nom, prénom, date de naissance), un simple « Anonyme 927 »
       fusionnerait les dossards 927 anonymes de deux courses en un athlète
       agrégeant les résultats de deux personnes. `epreuve_id` et `dossard` étant
       stables, l'identité l'est d'un re-scrape à l'autre. Si ok-time levait
       l'anonymat, la réconciliation d'identité (#66) rattacherait les
       participations au nom réel au prochain `rescrape-db`.
    2. équipe (course de relais, ou nom porteur d'un « / ») — le nom entier va
       dans `nom`, le prénom reste vide. Ne pas mutiler un nom d'équipe.
    3. sinon — convention « Prénom NOM » de la source, déléguée à
       `split_athlete_name`. **Y compris un anonyme sans dossard** : sans dossard,
       « Anonyme <epreuve_id>-None » serait identique pour tous les anonymes de
       l'épreuve et les fusionnerait en un seul `Athlete` — exactement le défaut
       que la clé d'épreuve sert à écarter, et que `UNIQUE(course_id, bib_number)`
       ne rattraperait pas, `bib_number` étant vide lui aussi. Le nom amputé de
       la source discrimine au moins autant qu'une identité synthétique
       constante, et ne prétend rien qu'on ne sache : on le laisse passer par le
       chemin ordinaire. Deux noms amputés identiques fusionneraient encore, mais
       c'est l'ambiguïté de la source, pas une que le scraper introduit (les
       participants sans dossard restent hors périmètre, §7 du design).
    """
    dossard = "" if runner.get("dossard") is None else str(runner.get("dossard")).strip()
    if str(runner.get("rgpd") or "").strip().upper() == "N" and dossard:
        return f"Anonyme {epreuve_id}-{dossard}", ""
    nom = _repair_mojibake(str(runner.get("nom") or "").strip())
    if is_relay or _SEPARATEUR_EQUIPE in nom:
        return nom, ""
    return split_athlete_name(nom)
```

> **Note de revue finale (#52) — constat M1.** Le plan d'origine prenait la
> branche synthétique dès `rgpd:"N"`, sans regarder le dossard :
> `f"Anonyme {epreuve_id}-{runner.get('dossard')}"`. Deux anonymes **sans
> dossard** d'une même épreuve produisaient alors la même identité
> (« Anonyme 59697-None ») et se fondaient en un seul `Athlete` agrégeant deux
> personnes — le défaut même que le raisonnement du §4.3 du design sert à
> écarter, le garde-fou tombant dès que `dossard` est nul. La branche est donc
> conditionnée au dossard, la seule chose qui la rende discriminante ; sinon on
> retombe sur le chemin ordinaire. Le seuil est calé sur celui de `bib_number`
> dans `_build_result` : identité synthétique **si et seulement si**
> `UNIQUE(course_id, bib_number)` a de quoi mordre.

- [ ] **Étape 4 : lancer les tests et vérifier qu'ils passent**

```bash
uv run pytest tests/test_oktime.py -v && uv run ruff check .
```
Attendu : 37 tests PASS (35 au plan d'origine + les 2 tests de revue finale).

- [ ] **Étape 5 : commit**

```bash
git add backend/app/scrapers/oktime.py backend/tests/test_oktime.py
git commit -m "feat(scrapers): oktime — identité, mojibake et noms d'équipe (#52)"
```

---

### Tâche 4 : statut, rangs, genre et temps total

Les scalaires du participant. Chaque règle vient d'une mesure du panel : rang `0`
signifie « non classé » et non « premier », `X` est un genre que le front ne sait
pas rendre, `"00:00:00"` est un temps absent, et une course d'enfants terminée
mais non chronométrée ne doit pas sortir en DNF collectif.

**Fichiers :**
- Modifier : `backend/app/scrapers/oktime.py`
- Modifier : `backend/tests/test_oktime.py`

**Interfaces :**
- Consomme : `STATUS_DNF/DNS/DSQ/FINISHER` (`scrapers/base.py`),
  `normalize_time`, `normalize_rank` (`scrapers/utils.py`).
- Produit :
  - `_status(runner: dict, *, course_non_chronometree: bool) -> str`
  - `_rank(value) -> int | None`
  - `_gender(raw) -> str`
  - `_total_time(runner: dict) -> str`

- [ ] **Étape 1 : écrire les tests qui échouent**

Ajouter à `backend/tests/test_oktime.py` :

```python
# --------------------------------------------------------------------------- #
# Statut, rangs, genre, temps
# --------------------------------------------------------------------------- #

def test_status_non_partant():
    runner = {"pris_depart": "N", "abandon": "N", "disqualifie": "N"}

    assert oktime._status(runner, course_non_chronometree=False) == "DNS"


def test_status_abandon():
    runner = {"pris_depart": "O", "abandon": "O", "disqualifie": "N"}

    assert oktime._status(runner, course_non_chronometree=False) == "DNF"


def test_status_disqualifie():
    runner = {"pris_depart": "O", "abandon": "N", "disqualifie": "O"}

    assert oktime._status(runner, course_non_chronometree=False) == "DSQ"


def test_status_dns_prioritaire_sur_dnf():
    """1 participation du panel cumule les deux : ne pas être parti prime."""
    runner = {"pris_depart": "N", "abandon": "O", "disqualifie": "N"}

    assert oktime._status(runner, course_non_chronometree=False) == "DNS"


def test_status_course_non_chronometree_est_finisher():
    """Les 3 courses enfants (UNICEF, 52 participations) : courues et déclarées
    terminées, mais sans chronométrage individuel. Sans cette règle,
    `mapping.derive_status` les classerait DNF en bloc et le front afficherait un
    badge d'abandon sur une course entière d'enfants."""
    runner = {"pris_depart": "O", "abandon": "N", "disqualifie": "N"}

    assert oktime._status(runner, course_non_chronometree=True) == "finisher"


def test_status_par_defaut_delegue_a_lheuristique():
    """Un participant sans temps dans une course par ailleurs chronométrée reste
    traité par l'heuristique du projet : rien ne le distingue d'un abandon non
    saisi."""
    runner = {"pris_depart": "O", "abandon": "N", "disqualifie": "N"}

    assert oktime._status(runner, course_non_chronometree=False) == ""


def test_status_abandon_prime_sur_course_non_chronometree():
    """Un statut explicite de la source n'est jamais écrasé par le repli."""
    runner = {"pris_depart": "O", "abandon": "O", "disqualifie": "N"}

    assert oktime._status(runner, course_non_chronometree=True) == "DNF"


def test_rank_zero_devient_none():
    """1 336 finishers valides du panel portent `classement_general: 0` (= non
    classé). `normalize_rank` rendrait 0, qui s'afficherait comme une place."""
    assert oktime._rank(0) is None


@pytest.mark.parametrize("valeur, attendu", [(1, 1), (42, 42), (None, None), ("", None)])
def test_rank_cas_courants(valeur, attendu):
    assert oktime._rank(valeur) == attendu


@pytest.mark.parametrize("brut, attendu", [("M", "M"), ("F", "F"), ("m", "M")])
def test_gender_conserve_m_et_f(brut, attendu):
    assert oktime._gender(brut) == attendu


@pytest.mark.parametrize("brut", ["X", "", None, "?"])
def test_gender_vide_hors_m_et_f(brut):
    """`X` (relais mixtes, 323 participations) : chaîne vide plutôt qu'une valeur
    que le front ne sait pas rendre."""
    assert oktime._gender(brut) == ""


def test_total_time_normalise():
    assert oktime._total_time({"temps_finish": "3:31:57"}) == "03:31:57"


@pytest.mark.parametrize("brut", ["00:00:00", "", None])
def test_total_time_absent(brut):
    """`"00:00:00"` est la façon dont la source dit « pas de temps »."""
    assert oktime._total_time({"temps_finish": brut}) == ""
```

- [ ] **Étape 2 : lancer les tests et vérifier qu'ils échouent**

```bash
uv run pytest tests/test_oktime.py -v -k "status or rank or gender or total_time"
```
Attendu : ÉCHEC — `AttributeError: ... has no attribute '_status'`.

- [ ] **Étape 3 : écrire l'implémentation minimale**

Compléter les imports de `oktime.py` :

```python
from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, STATUS_FINISHER
from .utils import normalize_rank, normalize_time, split_athlete_name
```

Puis ajouter à la suite de `_athlete_identity` :

```python
# --------------------------------------------------------------------------- #
# Scalaires du participant
# --------------------------------------------------------------------------- #

def _drapeau(runner: dict, champ: str) -> str:
    """Un drapeau O/N de la source, normalisé en majuscule."""
    return str(runner.get(champ) or "").strip().upper()


def _status(runner: dict, *, course_non_chronometree: bool) -> str:
    """Statut sportif, ou "" pour laisser l'heuristique du projet trancher.

    Ordre de priorité : **DNS avant DNF** — 1 participation du panel porte
    `abandon="O"` et `pris_depart="N"`, et ne pas être parti prime.

    Le repli `finisher` est borné à une course **entièrement** non chronométrée
    (les 3 courses enfants du panel, `status="finish"` sans aucun temps) : dans
    une course par ailleurs chronométrée, un participant sans temps reste traité
    par l'heuristique, faute de savoir le distinguer d'un abandon non saisi.
    """
    if _drapeau(runner, "pris_depart") == "N":
        return STATUS_DNS
    if _drapeau(runner, "abandon") == "O":
        return STATUS_DNF
    if _drapeau(runner, "disqualifie") == "O":
        return STATUS_DSQ
    if course_non_chronometree:
        return STATUS_FINISHER
    return ""


def _rank(value) -> int | None:
    """Rang, avec `0 → None` : la source dit « non classé » avec un zéro.

    1 336 finishers valides du panel sur 11 816 sont dans ce cas.
    `normalize_rank` rendrait 0, qui s'afficherait comme une place.
    """
    return normalize_rank(value) or None


def _gender(raw) -> str:
    """« M » / « F » tels quels ; tout le reste → "".

    `X` (relais mixtes, 323 participations) n'est pas rendu par le front : mieux
    vaut vide qu'une valeur qu'il ne sait pas afficher.
    """
    genre = str(raw or "").strip().upper()
    return genre if genre in ("M", "F") else ""


def _total_time(runner: dict) -> str:
    """`temps_finish` normalisé, vide si `"00:00:00"` — la façon dont la source
    dit « pas de temps » (`temps_finish` est toujours renseigné, 12 644/12 644)."""
    brut = normalize_time(str(runner.get("temps_finish") or "").strip())
    return "" if brut == "00:00:00" else brut
```

- [ ] **Étape 4 : lancer les tests et vérifier qu'ils passent**

```bash
uv run pytest tests/test_oktime.py -v && uv run ruff check .
```
Attendu : 60 tests PASS (58 au plan d'origine + les 2 tests de revue finale de la tâche 3).

- [ ] **Étape 5 : commit**

```bash
git add backend/app/scrapers/oktime.py backend/tests/test_oktime.py
git commit -m "feat(scrapers): oktime — statut, rangs, genre et temps total (#52)"
```

---

### Tâche 5 : splits — différenciation des points de passage cumulés

Les points de passage sont des temps **cumulés depuis le départ**. Le projet range
des **durées de segment** (convention déjà appliquée par `klikego` et
`timepulse`). La différenciation se fait ici, avec une garde sur les 10
participations du panel dont les points sortent dans le désordre à la source.

**Fichiers :**
- Modifier : `backend/app/scrapers/oktime.py`
- Modifier : `backend/tests/test_oktime.py`

**Interfaces :**
- Consomme : `normalize_time` (`scrapers/utils.py`).
- Produit :
  - `_secs(t: str) -> int`, `_fmt_secs(s: int) -> str`
  - `_points_cumules(points: list[dict] | None) -> list[tuple[str, str]]` (ajout de
    revue finale, partagé avec `_course_results`)
  - `_segments(points: list[dict]) -> tuple[list[tuple[str, str]], bool]`
    → `(segments, cumuls_conserves)`. Le second membre vaut `True` quand un delta
    négatif a fait replier sur les valeurs cumulées brutes.

- [ ] **Étape 1 : écrire les tests qui échouent**

Ajouter à `backend/tests/test_oktime.py` :

```python
# --------------------------------------------------------------------------- #
# Splits : cumulés → durées de segment
# --------------------------------------------------------------------------- #

POINTS_TRIATHLON = [
    {"id": "11|1", "nom": "NATATION", "time": "00:23:56"},
    {"id": "12|2", "nom": "VELO", "time": "02:20:10"},
    {"id": "13|3", "nom": "COURSE A PIED", "time": "03:31:57"},
]


def test_segments_differencie_les_cumules():
    """4 512 des 4 522 participations à ≥ 2 points ont des cumulés croissants."""
    segments, cumuls_conserves = oktime._segments(POINTS_TRIATHLON)

    assert segments == [
        ("NATATION", "00:23:56"),
        ("VELO", "01:56:14"),
        ("COURSE A PIED", "01:11:47"),
    ]
    assert cumuls_conserves is False


def test_segments_conserve_les_libelles_de_la_source():
    """Les `id` ne sont pas sémantiques (« 12|2 » vaut T2 ici, VELO là) et 55 des
    99 courses sortent du motif triathlon : un remapping devinerait."""
    points = [
        {"id": "1|1", "nom": "CP1", "time": "00:15:00"},
        {"id": "2|2", "nom": "CP2", "time": "00:40:00"},
    ]

    assert oktime._segments(points)[0] == [("CP1", "00:15:00"), ("CP2", "00:25:00")]


def test_segments_delta_negatif_replie_sur_les_bruts():
    """Mimizan : `Vélo 01:30:46` puis `T2 01:30:19` — ordre incohérent à la
    source, 10 participations. Mieux vaut un cumulé qu'un temps absurde."""
    points = [
        {"id": "1|1", "nom": "NATATION", "time": "00:20:00"},
        {"id": "2|2", "nom": "VELO", "time": "01:30:46"},
        {"id": "3|3", "nom": "T2", "time": "01:30:19"},
    ]

    segments, cumuls_conserves = oktime._segments(points)

    assert segments == [
        ("NATATION", "00:20:00"),
        ("VELO", "01:30:46"),
        ("T2", "01:30:19"),
    ]
    assert cumuls_conserves is True


def test_segments_sans_point():
    assert oktime._segments([]) == ([], False)


def test_segments_tolere_une_liste_absente():
    assert oktime._segments(None) == ([], False)


def test_segments_ignore_les_points_sans_temps():
    """Un point à `"00:00:00"` ne porte aucune durée : le garder ferait sortir un
    delta négatif au point suivant et déclencherait le repli à tort."""
    points = [
        {"id": "0|0", "nom": "DEPART", "time": "00:00:00"},
        {"id": "1|1", "nom": "NATATION", "time": "00:23:56"},
    ]

    assert oktime._segments(points) == ([("NATATION", "00:23:56")], False)


def test_segments_un_seul_point():
    points = [{"id": "1|1", "nom": "NATATION", "time": "00:23:56"}]

    assert oktime._segments(points) == ([("NATATION", "00:23:56")], False)
```

- [ ] **Étape 2 : lancer les tests et vérifier qu'ils échouent**

```bash
uv run pytest tests/test_oktime.py -v -k "segments"
```
Attendu : ÉCHEC — `AttributeError: ... has no attribute '_segments'`.

- [ ] **Étape 3 : écrire l'implémentation minimale**

Ajouter à `oktime.py`, à la suite de `_total_time` :

```python
# --------------------------------------------------------------------------- #
# Splits
# --------------------------------------------------------------------------- #
# `_secs` / `_fmt_secs` sont des copies locales de celles de `timepulse` : leur
# factorisation dans `utils.py` est un refacto à part (cf. la note d'en-tête de
# `registry.py`), qu'on n'entame pas au fil d'un nouveau provider.

def _secs(t: str) -> int:
    if not t:
        return 0
    p = t.split(":")
    try:
        return int(p[0]) * 3600 + int(p[1]) * 60 + int(p[2])
    except (IndexError, ValueError):
        return 0


def _fmt_secs(s: int) -> str:
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def _points_cumules(points: list[dict] | None) -> list[tuple[str, str]]:
    """(libellé, temps cumulé) des points **porteurs d'une durée**, dans l'ordre.

    Un point à zéro ne porte aucune durée : le garder ferait sortir un delta
    négatif au point suivant et déclencherait le repli à tort.

    Extrait de `_segments` pour servir aussi à `_course_results`, qui doit savoir
    si une course détient des données chronométriques **de quelque nature que ce
    soit** avant de l'écarter comme liste d'engagés.
    """
    cumules = [
        (str(point.get("nom") or "").strip(), normalize_time(str(point.get("time") or "").strip()))
        for point in points or []
    ]
    return [(label, temps) for label, temps in cumules if _secs(temps) > 0]


def _segments(points: list[dict] | None) -> tuple[list[tuple[str, str]], bool]:
    """Points de passage cumulés → durées de segment. (segments, cumuls_conservés).

    Les points sont cumulés depuis le départ (4 512 des 4 522 participations à
    ≥ 2 points le vérifient) ; le projet range des **durées**, convention déjà
    appliquée par `klikego` et `timepulse`.

    Les libellés sont ceux de la source, et les durées vont dans
    `ScrapedResult.segments` — le chemin générique déplafonné — plutôt que dans
    les 5 slots positionnels : les `id` de points ne sont pas sémantiques
    (« 12|2 » vaut « T2 » sur une épreuve et « VELO » sur une autre) et 55 des 99
    courses du panel sortent du motif triathlon. Un remapping devinerait.

    **Garde sur les deltas négatifs** : si un delta sort négatif (les 10
    participations de Mimizan à l'ordre incohérent), la participation conserve
    ses valeurs **cumulées brutes** plutôt qu'un temps absurde, et le second
    membre du tuple le signale à l'appelant, qui journalise par épreuve.

    Le temps total ne vient **jamais** du dernier point : 392 participations ont
    un dernier point différent de `temps_finish` (épreuves finissant sur
    « Départ CAP2 »). `temps_finish` fait seul foi.
    """
    cumules = _points_cumules(points)
    if not cumules:
        return [], False

    durees: list[tuple[str, str]] = []
    precedent = 0
    for label, temps in cumules:
        courant = _secs(temps)
        if courant < precedent:
            return cumules, True
        durees.append((label, _fmt_secs(courant - precedent)))
        precedent = courant
    return durees, False
```

> **Note de revue finale (#52).** `_points_cumules` n'était pas dans le plan
> d'origine : le filtrage des points à zéro vivait en ligne dans `_segments`. Il
> en a été extrait parce que `_course_results` a besoin du **même** critère
> « ce point porte-t-il une durée ? » pour décider si une course détient des
> données chronométriques (cf. la note de la tâche 7). Aucun changement de
> comportement de `_segments`.

- [ ] **Étape 4 : lancer les tests et vérifier qu'ils passent**

```bash
uv run pytest tests/test_oktime.py -v && uv run ruff check .
```
Attendu : 67 tests PASS (65 au plan d'origine + les 2 tests de revue finale de la tâche 3).

- [ ] **Étape 5 : commit**

```bash
git add backend/app/scrapers/oktime.py backend/tests/test_oktime.py
git commit -m "feat(scrapers): oktime différencie les points de passage cumulés (#52)"
```

---

### Tâche 6 : `_build_result` — un participant → `ScrapedResult`

L'assemblage : toutes les fonctions des tâches 3 à 5 convergent ici. `raw_data`
conserve la charge brute du participant **plus** le contexte d'épreuve, de sorte
qu'une erreur de différenciation reste diagnosticable sans re-scraper.

**Fichiers :**
- Modifier : `backend/app/scrapers/oktime.py`
- Modifier : `backend/tests/test_oktime.py`

**Interfaces :**
- Consomme : `_athlete_identity`, `_status`, `_rank`, `_gender`, `_total_time`,
  `_segments`, `_repair_mojibake`.
- Produit :

```python
def _build_result(
    runner: dict,
    *,
    url: str,
    event_name: str,
    event_type: str,
    event_date: date | None,
    distance_km: float | None,
    is_relay: bool,
    epreuve_id: str,
    course_non_chronometree: bool,
    contexte: dict,
) -> ScrapedResult
```

  Le drapeau de repli sur cumulés bruts voyage dans
  `result.raw_data["splits_cumules_conserves"]` (booléen) : il sert au log agrégé
  de la tâche 7 et reste diagnosticable en base.

- [ ] **Étape 1 : écrire les tests qui échouent**

Compléter d'abord le bloc d'imports en tête du fichier (E402 : pas d'import au
milieu du fichier) :

```python
import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.scrapers import oktime
```

Puis ajouter à la fin du fichier :

```python
# --------------------------------------------------------------------------- #
# _build_result
# --------------------------------------------------------------------------- #

RUNNER_NOMINAL = {
    "nom": "Valentin ROUVIER", "sexe": "M", "dossard": 1217,
    "club": "TRIATHLON CLUB NANTAIS", "categorie": "Senior", "categorie_abbrev": "SE",
    "temps_finish": "03:31:57", "temp-reel": None,
    "classement_general": 1, "classement_categorie": 1, "classement_sexe": 1,
    "rgpd": "O", "abandon": "N", "disqualifie": "N", "pris_depart": "O",
    "points_de_passage": POINTS_TRIATHLON,
}

CONTEXTE = {
    "epreuve_id": "59697",
    "heuredebut_course": "08:00:00",
    "reference_epreuve": "LAC-L-IND",
    "status_course": "finish",
}


def _resultat(runner, **surcharges):
    kwargs = {
        "url": "https://classement.ok-time.fr/48555",
        "event_name": "Triathlon de Lacanau 2026 - Triathlon L Individuel",
        "event_type": "triathlon-l",
        "event_date": date(2026, 5, 2),
        "distance_km": 110.0,
        "is_relay": False,
        "epreuve_id": "59697",
        "course_non_chronometree": False,
        "contexte": CONTEXTE,
    }
    kwargs.update(surcharges)
    return oktime._build_result(runner, **kwargs)


def test_build_result_champs_nominaux():
    r = _resultat(RUNNER_NOMINAL)

    assert r.provider == "oktime"
    assert r.source_url == "https://classement.ok-time.fr/48555"
    assert (r.athlete_name, r.athlete_firstname) == ("ROUVIER", "Valentin")
    assert r.club == "TRIATHLON CLUB NANTAIS"
    assert r.category == "Senior"
    assert r.gender == "M"
    assert r.bib_number == "1217"
    assert r.event_name == "Triathlon de Lacanau 2026 - Triathlon L Individuel"
    assert r.event_type == "triathlon-l"
    assert r.event_date == date(2026, 5, 2)
    assert r.distance_km == 110.0
    assert r.is_relay is False
    assert r.total_time == "03:31:57"
    assert r.status == ""


def test_build_result_range_les_splits_dans_segments():
    """Chemin générique déplafonné, pas les 5 slots positionnels."""
    r = _resultat(RUNNER_NOMINAL)

    assert r.segments == [
        ("NATATION", "00:23:56"),
        ("VELO", "01:56:14"),
        ("COURSE A PIED", "01:11:47"),
    ]
    assert (r.swim_time, r.t1_time, r.bike_time, r.t2_time, r.run_time) == ("", "", "", "", "")


def test_build_result_total_time_ne_vient_jamais_du_dernier_point():
    """392 participations ont un dernier point ≠ `temps_finish` (épreuves
    finissant sur « Départ CAP2 »). `temps_finish` fait seul foi."""
    runner = {
        **RUNNER_NOMINAL,
        "temps_finish": "01:12:00",
        "points_de_passage": [
            {"id": "1|1", "nom": "RUN1", "time": "00:20:00"},
            {"id": "2|2", "nom": "DEPART CAP2", "time": "00:55:00"},
        ],
    }

    r = _resultat(runner)

    assert r.total_time == "01:12:00"
    assert r.segments == [("RUN1", "00:20:00"), ("DEPART CAP2", "00:35:00")]


def test_build_result_dossard_absent():
    r = _resultat({**RUNNER_NOMINAL, "dossard": None})

    assert r.bib_number == ""


def test_build_result_bascule_le_drapeau_de_cumuls_conserves():
    runner = {
        **RUNNER_NOMINAL,
        "points_de_passage": [
            {"id": "1|1", "nom": "VELO", "time": "01:30:46"},
            {"id": "2|2", "nom": "T2", "time": "01:30:19"},
        ],
    }

    r = _resultat(runner)

    assert r.raw_data["splits_cumules_conserves"] is True
    assert r.segments == [("VELO", "01:30:46"), ("T2", "01:30:19")]


def test_build_result_raw_data_conserve_le_brut_et_le_contexte():
    """Une erreur de différenciation doit rester diagnosticable sans re-scraper :
    les points de passage **cumulés** d'origine sont conservés tels quels."""
    r = _resultat(RUNNER_NOMINAL)

    assert r.raw_data["temp-reel"] is None
    assert r.raw_data["categorie_abbrev"] == "SE"
    assert r.raw_data["points_de_passage"] == POINTS_TRIATHLON
    assert r.raw_data["heuredebut_course"] == "08:00:00"
    assert r.raw_data["reference_epreuve"] == "LAC-L-IND"
    assert r.raw_data["status_course"] == "finish"
    assert r.raw_data["splits_cumules_conserves"] is False


def test_build_result_rgpd_identite_synthetique_mais_resultat_publie():
    """La source ampute le nom mais publie temps et rang : on importe les deux."""
    runner = {
        **RUNNER_NOMINAL, "nom": "T... B...", "dossard": 927, "rgpd": "N", "club": "",
    }

    r = _resultat(runner)

    assert (r.athlete_name, r.athlete_firstname) == ("Anonyme 59697-927", "")
    assert r.total_time == "03:31:57"
    assert r.rank_overall == 1


def test_build_result_genre_mixte_vide():
    r = _resultat({**RUNNER_NOMINAL, "sexe": "X"})

    assert r.gender == ""


def test_build_result_rangs_zero_a_none():
    runner = {
        **RUNNER_NOMINAL,
        "classement_general": 0, "classement_categorie": 0, "classement_sexe": 0,
    }

    r = _resultat(runner)

    assert (r.rank_overall, r.rank_category, r.rank_gender) == (None, None, None)


def test_build_result_course_non_chronometree_est_finisher():
    runner = {**RUNNER_NOMINAL, "temps_finish": "00:00:00", "points_de_passage": []}

    r = _resultat(runner, course_non_chronometree=True)

    assert r.status == "finisher"
    assert r.total_time == ""
```

- [ ] **Étape 2 : lancer les tests et vérifier qu'ils échouent**

```bash
uv run pytest tests/test_oktime.py -v -k "build_result"
```
Attendu : ÉCHEC — `AttributeError: ... has no attribute '_build_result'`.

- [ ] **Étape 3 : écrire l'implémentation minimale**

Compléter les imports de `oktime.py` :

```python
from datetime import date
...
from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, STATUS_FINISHER, ScrapedResult
```

Ajouter à la suite de `_segments` :

```python
# --------------------------------------------------------------------------- #
# Assemblage
# --------------------------------------------------------------------------- #

def _build_result(
    runner: dict,
    *,
    url: str,
    event_name: str,
    event_type: str,
    event_date: date | None,
    distance_km: float | None,
    is_relay: bool,
    epreuve_id: str,
    course_non_chronometree: bool,
    contexte: dict,
) -> ScrapedResult:
    """Un participant de la charge API → un `ScrapedResult`.

    `raw_data` conserve la charge brute du participant — donc les points de
    passage **cumulés d'origine** — plus le contexte d'épreuve non porté par les
    champs typés, de sorte qu'une erreur de différenciation reste diagnosticable
    sans re-scraper.
    """
    nom, prenom = _athlete_identity(runner, is_relay=is_relay, epreuve_id=epreuve_id)
    segments, cumuls_conserves = _segments(runner.get("points_de_passage"))

    result = ScrapedResult(source_url=url, provider="oktime")
    result.event_name = event_name
    result.event_type = event_type
    result.event_date = event_date
    result.distance_km = distance_km
    result.is_relay = is_relay
    result.athlete_name = nom
    result.athlete_firstname = prenom
    result.club = str(runner.get("club") or "").strip()
    result.category = str(runner.get("categorie") or "").strip()
    result.gender = _gender(runner.get("sexe"))
    dossard = runner.get("dossard")
    result.bib_number = "" if dossard is None else str(dossard).strip()
    result.rank_overall = _rank(runner.get("classement_general"))
    result.rank_category = _rank(runner.get("classement_categorie"))
    result.rank_gender = _rank(runner.get("classement_sexe"))
    result.total_time = _total_time(runner)
    result.segments = segments
    result.status = _status(runner, course_non_chronometree=course_non_chronometree)
    result.raw_data = {
        **runner,
        **contexte,
        "splits_cumules_conserves": cumuls_conserves,
    }
    return result
```

- [ ] **Étape 4 : lancer les tests et vérifier qu'ils passent**

```bash
uv run pytest tests/test_oktime.py -v && uv run ruff check .
```
Attendu : 77 tests PASS (75 au plan d'origine + les 2 tests de revue finale de la tâche 3).

- [ ] **Étape 5 : commit**

```bash
git add backend/app/scrapers/oktime.py backend/tests/test_oktime.py
git commit -m "feat(scrapers): oktime mappe un participant vers ScrapedResult (#52)"
```

---

### Tâche 7 : `_course_results` — une épreuve de la charge → participants

Le niveau course : nom qualifié, type classé sur la **concaténation** des deux
titres, date, distance, drapeau relais, écartement des listes d'engagés, et le
log agrégé (une ligne par épreuve, pas une par participation).

**Fichiers :**
- Modifier : `backend/app/scrapers/oktime.py`
- Modifier : `backend/tests/test_oktime.py`
- Créer : `backend/tests/fixtures/oktime_lacanau_48555.json`
- Créer : `backend/tests/fixtures/oktime_engages_48999.json`

**Interfaces :**
- Consomme : `_build_result`, `_is_relay_course`, `_total_time`, `_points_cumules` ;
  `qualify_event_name` (`scrapers/utils.py`), `classify_event_type`
  (`scrapers/classify.py`).
- Produit :
  - `_parse_date(raw) -> date | None`
  - `_parse_distance(raw) -> float | None`
  - `_course_results(course: dict, *, url: str, evenement_title: str) -> list[ScrapedResult]`
    — `evenement_title` est reçu **déjà** passé à `html.unescape` par l'appelant.

- [ ] **Étape 1 : créer les fixtures**

Créer `backend/tests/fixtures/oktime_lacanau_48555.json` :

```json
{
  "success": true,
  "evenement_id": 48555,
  "evenement_title": "Triathlon de Lacanau 2026 &#8211; Samedi 02 mai",
  "count": 2,
  "data": [
    {
      "title_course": "Triathlon L Individuel",
      "epreuve_id": 59697,
      "date_course": "02/05/2026",
      "distance_course": "110,000",
      "heuredebut_course": "08:00:00",
      "reference_epreuve": "LAC-L-IND",
      "status": "finish",
      "runners": [
        {
          "nom": "Valentin ROUVIER",
          "sexe": "M",
          "dossard": 1217,
          "club": "TRIATHLON CLUB NANTAIS",
          "categorie": "Senior",
          "categorie_abbrev": "SE",
          "temps_finish": "03:31:57",
          "temp-reel": null,
          "classement_general": 1,
          "classement_categorie": 1,
          "classement_sexe": 1,
          "rgpd": "O",
          "abandon": "N",
          "disqualifie": "N",
          "pris_depart": "O",
          "points_de_passage": [
            {"id": "11|1", "nom": "NATATION", "time": "00:23:56"},
            {"id": "12|2", "nom": "VELO", "time": "02:20:10"},
            {"id": "13|3", "nom": "COURSE A PIED", "time": "03:31:57"}
          ]
        },
        {
          "nom": "AnaÃ¯s MOUSQUET",
          "sexe": "F",
          "dossard": 1042,
          "club": "",
          "categorie": "Senior",
          "categorie_abbrev": "SE",
          "temps_finish": "04:12:03",
          "temp-reel": null,
          "classement_general": 0,
          "classement_categorie": 0,
          "classement_sexe": 0,
          "rgpd": "O",
          "abandon": "N",
          "disqualifie": "N",
          "pris_depart": "O",
          "points_de_passage": []
        },
        {
          "nom": "T... B...",
          "sexe": "M",
          "dossard": 927,
          "club": "",
          "categorie": "Vétéran 1",
          "categorie_abbrev": "V1",
          "temps_finish": "00:00:00",
          "temp-reel": null,
          "classement_general": 0,
          "classement_categorie": 0,
          "classement_sexe": 0,
          "rgpd": "N",
          "abandon": "O",
          "disqualifie": "N",
          "pris_depart": "N",
          "points_de_passage": []
        }
      ]
    },
    {
      "title_course": "Relais L &#038; Duo",
      "epreuve_id": 59698,
      "date_course": "02/05/2026",
      "distance_course": "110,000",
      "heuredebut_course": "08:05:00",
      "reference_epreuve": "LAC-L-REL",
      "status": "finish",
      "runners": [
        {
          "nom": "GUILLON RÉMI / CHARPENTIER EMMANUEL",
          "sexe": "X",
          "dossard": 2001,
          "club": "TEAM TCC",
          "categorie": "Relais",
          "categorie_abbrev": "RE",
          "temps_finish": "03:58:41",
          "temp-reel": null,
          "classement_general": 3,
          "classement_categorie": 1,
          "classement_sexe": 0,
          "rgpd": "O",
          "abandon": "N",
          "disqualifie": "O",
          "pris_depart": "O",
          "points_de_passage": []
        }
      ]
    }
  ]
}
```

Créer `backend/tests/fixtures/oktime_engages_48999.json` :

```json
{
  "success": true,
  "evenement_id": 48999,
  "evenement_title": "Triathlon du Lac 2026",
  "count": 2,
  "data": [
    {
      "title_course": "Triathlon S Individuel",
      "epreuve_id": 60101,
      "date_course": "12/07/2026",
      "distance_course": "25,750",
      "heuredebut_course": "09:00:00",
      "reference_epreuve": "LAC26-S",
      "status": "",
      "runners": [
        {
          "nom": "Paul MARTIN",
          "sexe": "M",
          "dossard": 12,
          "club": "",
          "categorie": "Senior",
          "categorie_abbrev": "SE",
          "temps_finish": "00:00:00",
          "temp-reel": null,
          "classement_general": 0,
          "classement_categorie": 0,
          "classement_sexe": 0,
          "rgpd": "O",
          "abandon": "N",
          "disqualifie": "N",
          "pris_depart": "O",
          "points_de_passage": []
        }
      ]
    },
    {
      "title_course": "Course des enfants UNICEF",
      "epreuve_id": 60102,
      "date_course": "12/07/2026",
      "distance_course": "1,000",
      "heuredebut_course": "14:00:00",
      "reference_epreuve": "LAC26-KID",
      "status": "finish",
      "runners": [
        {
          "nom": "Lou BERNARD",
          "sexe": "F",
          "dossard": 501,
          "club": "",
          "categorie": "Poussin",
          "categorie_abbrev": "PO",
          "temps_finish": "00:00:00",
          "temp-reel": null,
          "classement_general": 0,
          "classement_categorie": 0,
          "classement_sexe": 0,
          "rgpd": "O",
          "abandon": "N",
          "disqualifie": "N",
          "pris_depart": "O",
          "points_de_passage": []
        }
      ]
    }
  ]
}
```

- [ ] **Étape 2 : écrire les tests qui échouent**

Compléter d'abord le bloc d'imports en tête du fichier (E402) :

```python
import html
import json
import logging
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.scrapers import oktime
```

Puis ajouter à la fin du fichier :

```python
# --------------------------------------------------------------------------- #
# _course_results : niveau course
# --------------------------------------------------------------------------- #

LACANAU = json.loads((FIXTURES / "oktime_lacanau_48555.json").read_text(encoding="utf-8"))
ENGAGES = json.loads((FIXTURES / "oktime_engages_48999.json").read_text(encoding="utf-8"))

URL_48555 = "https://classement.ok-time.fr/48555"


def _courses(charge, index):
    """Les participants d'une course de la charge, titre d'événement déjà décodé."""
    return oktime._course_results(
        charge["data"][index],
        url=URL_48555,
        evenement_title=html.unescape(charge["evenement_title"]),
    )


@pytest.mark.parametrize("brut, attendu", [("02/05/2026", date(2026, 5, 2)), ("", None), (None, None)])
def test_parse_date(brut, attendu):
    assert oktime._parse_date(brut) == attendu


def test_parse_date_format_inattendu():
    assert oktime._parse_date("2026-05-02") is None


@pytest.mark.parametrize(
    "brut, attendu",
    [("110,000", 110.0), ("27,5", 27.5), ("9,500", 9.5), ("", None), (None, None), ("0,000", None)],
)
def test_parse_distance(brut, attendu):
    """Virgule décimale. Renseignée partout au panel : évite le repli sur
    l'extraction depuis le nom, qui lit « Course chronométrée 9,5 km » comme 5 km."""
    assert oktime._parse_distance(brut) == attendu


def test_course_results_nom_qualifie_par_lepreuve():
    """Sans le titre d'épreuve, les épreuves de Lacanau, qui partagent date et
    type, fusionneraient sur `uq_course_identity` et leurs dossards entreraient
    en collision (issue #21)."""
    resultats = _courses(LACANAU, 0)

    assert all(
        r.event_name == "Triathlon de Lacanau 2026 – Samedi 02 mai - Triathlon L Individuel"
        for r in resultats
    )


def test_course_results_entites_html_decodees_dans_le_nom():
    """`&#038;` partirait en base tel quel sans `html.unescape`."""
    resultats = _courses(LACANAU, 1)

    assert resultats[0].event_name.endswith("Relais L & Duo")
    assert "&#" not in resultats[0].event_name


def test_course_results_classification_sur_la_concatenation():
    """Le titre d'épreuve seul est trompeur : « Format M individuel » du SwimRun
    Côte Beauté sortirait en triathlon-m. La concaténation corrige 5 courses du
    panel et n'en dégrade aucune."""
    course = {
        "title_course": "Format M individuel",
        "epreuve_id": 1,
        "date_course": "01/06/2025",
        "distance_course": "20,000",
        "status": "finish",
        "runners": [{"nom": "Paul MARTIN", "temps_finish": "01:00:00"}],
    }

    resultats = oktime._course_results(
        course, url=URL_48555, evenement_title="SwimRun de la Côte de Beauté"
    )

    assert resultats[0].event_type == "swimrun-m"


def test_course_results_concatenation_reste_correcte_si_les_titres_se_contredisent():
    """« Aquathlon 10 13 ans » dans « Triathlon de Lacanau » sort bien en aquathlon."""
    course = {
        "title_course": "Aquathlon 10 13 ans",
        "epreuve_id": 1,
        "date_course": "02/05/2026",
        "distance_course": "2,000",
        "status": "finish",
        "runners": [{"nom": "Lou BERNARD", "temps_finish": "00:12:00"}],
    }

    resultats = oktime._course_results(
        course, url=URL_48555, evenement_title="Triathlon de Lacanau 2026"
    )

    assert resultats[0].event_type == "aquathlon"


def test_course_results_date_et_distance():
    resultats = _courses(LACANAU, 0)

    assert all(r.event_date == date(2026, 5, 2) for r in resultats)
    assert all(r.distance_km == 110.0 for r in resultats)


def test_course_results_relais_uniforme_sur_la_course():
    """Décider par course garantit que `Course.is_relay` et
    `Participation.is_relay` ne divergent pas selon l'ordre des participants."""
    assert all(r.is_relay for r in _courses(LACANAU, 1))
    assert not any(r.is_relay for r in _courses(LACANAU, 0))


def test_course_results_statuts_de_la_source():
    individuel = _courses(LACANAU, 0)
    relais = _courses(LACANAU, 1)

    assert individuel[0].status == ""      # finisher laissé à l'heuristique
    assert individuel[2].status == "DNS"   # pris_depart="N" ET abandon="O"
    assert relais[0].status == "DSQ"


def test_course_results_ecarte_une_liste_dengages(caplog):
    """`status != "finish"` **et** aucune donnée chronométrique : épreuve inscrite
    mais pas courue. Les importer créerait des participations sans temps, que
    l'heuristique du projet classerait DNF."""
    with caplog.at_level(logging.INFO, logger="app.scrapers.oktime"):
        resultats = _courses(ENGAGES, 0)

    assert resultats == []
    assert "liste d'engagés" in caplog.text


def test_course_results_course_enfants_non_chronometree_est_finisher():
    """`status="finish"` sans aucun temps : courue et déclarée terminée. La double
    condition l'épargne de l'écartement, et le statut explicite lui évite le DNF
    collectif."""
    resultats = _courses(ENGAGES, 1)

    assert len(resultats) == 1
    assert resultats[0].status == "finisher"
    assert resultats[0].total_time == ""


# Ajoutés en revue finale (cf. la note de fin de tâche) : une course **en cours**
# n'est pas une liste d'engagés, et ses partants ne sont pas des finishers.
COURSE_EN_COURS = {
    "title_course": "Triathlon M Individuel",
    "epreuve_id": 60201,
    "date_course": "12/07/2026",
    "distance_course": "51,500",
    "heuredebut_course": "09:00:00",
    "reference_epreuve": "LAC26-M",
    "status": "live",
    "runners": [
        {
            "nom": "Paul MARTIN", "sexe": "M", "dossard": 12, "club": "",
            "categorie": "Senior", "temps_finish": "00:00:00",
            "classement_general": 0, "classement_categorie": 0, "classement_sexe": 0,
            "rgpd": "O", "abandon": "N", "disqualifie": "N", "pris_depart": "O",
            "points_de_passage": [
                {"id": "11|1", "nom": "NATATION", "time": "00:23:56"},
                {"id": "12|2", "nom": "VELO", "time": "01:40:10"},
            ],
        }
    ],
}


def test_course_results_course_en_cours_avec_points_de_passage_nest_pas_ecartee(caplog):
    with caplog.at_level(logging.INFO, logger="app.scrapers.oktime"):
        resultats = oktime._course_results(
            COURSE_EN_COURS, url=URL_48555, evenement_title="Triathlon du Lac 2026"
        )

    assert len(resultats) == 1
    assert "liste d'engagés" not in caplog.text
    assert resultats[0].segments == [("NATATION", "00:23:56"), ("VELO", "01:16:14")]


def test_course_results_course_en_cours_ne_sort_pas_en_finisher():
    resultats = oktime._course_results(
        COURSE_EN_COURS, url=URL_48555, evenement_title="Triathlon du Lac 2026"
    )

    assert resultats[0].status == ""
    assert resultats[0].total_time == ""


def test_course_results_invariants_de_course_calcules_une_seule_fois(monkeypatch):
    """Cinq invariants par course, pas par participant."""
    appels: list[str] = []
    vrai_relais, vrai_type = oktime._is_relay_course, oktime.classify_event_type
    monkeypatch.setattr(
        oktime, "_is_relay_course",
        lambda titre, runners: appels.append("relais") or vrai_relais(titre, runners),
    )
    monkeypatch.setattr(
        oktime, "classify_event_type",
        lambda texte: appels.append("type") or vrai_type(texte),
    )
    course = {
        "title_course": "Triathlon M", "epreuve_id": 1, "date_course": "01/06/2025",
        "distance_course": "51,500", "status": "finish",
        "runners": [
            {"nom": f"Paul MARTIN{i}", "temps_finish": "02:00:00"} for i in range(5)
        ],
    }

    resultats = oktime._course_results(
        course, url=URL_48555, evenement_title="Triathlon de Mimizan"
    )

    assert len(resultats) == 5
    assert appels.count("relais") == 1
    assert appels.count("type") == 1


def test_course_results_log_agrege_des_cumuls_conserves(caplog):
    """Une ligne par épreuve, pas une par participation."""
    course = {
        "title_course": "Triathlon M",
        "epreuve_id": 1,
        "date_course": "01/06/2025",
        "distance_course": "51,500",
        "status": "finish",
        "runners": [
            {
                "nom": f"Paul MARTIN{i}",
                "temps_finish": "02:00:00",
                "points_de_passage": [
                    {"id": "1|1", "nom": "VELO", "time": "01:30:46"},
                    {"id": "2|2", "nom": "T2", "time": "01:30:19"},
                ],
            }
            for i in range(3)
        ],
    }

    with caplog.at_level(logging.WARNING, logger="app.scrapers.oktime"):
        oktime._course_results(course, url=URL_48555, evenement_title="Triathlon de Mimizan")

    messages = [r for r in caplog.records if "décroissants" in r.getMessage()]
    assert len(messages) == 1
    assert "3 participation" in messages[0].getMessage()
```

- [ ] **Étape 3 : lancer les tests et vérifier qu'ils échouent**

```bash
uv run pytest tests/test_oktime.py -v -k "parse_date or parse_distance or course_results"
```
Attendu : ÉCHEC — `AttributeError: ... has no attribute '_parse_date'`.

- [ ] **Étape 4 : écrire l'implémentation minimale**

Compléter les imports de `oktime.py` :

```python
import html
...
from datetime import date, datetime
...
from .classify import classify_event_type
from .utils import normalize_rank, normalize_time, qualify_event_name, split_athlete_name
```

Ajouter à la suite de `_build_result` :

```python
# --------------------------------------------------------------------------- #
# Niveau course
# --------------------------------------------------------------------------- #

def _parse_date(raw) -> date | None:
    """`dd/mm/yyyy` — la forme de `date_course` sur les 99 courses du panel."""
    try:
        return datetime.strptime(str(raw or "").strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def _parse_distance(raw) -> float | None:
    """`distance_course` en km, virgule décimale (« 27,5 » → 27.5).

    Renseignée sur tout le panel : la fournir évite le repli de
    `mapping.get_or_create_course` sur l'extraction depuis le nom, qui lit
    « Course chronométrée 9,5 km » comme un 5 km. Une distance nulle vaut absence.
    """
    valeur = str(raw or "").strip().replace(",", ".")
    if not valeur:
        return None
    try:
        km = float(valeur)
    except ValueError:
        return None
    return km or None


def _log_cumuls_conserves(resultats: list[ScrapedResult], title_course: str) -> None:
    """Signal **agrégé** (une ligne par épreuve, pas une par participation) du
    repli sur cumulés bruts. Pas d'état global : tout vit dans cet appel."""
    n = sum(1 for r in resultats if r.raw_data.get("splits_cumules_conserves"))
    if n:
        logger.warning(
            "Épreuve ok-time « %s » : %d participation(s) aux points de passage "
            "décroissants — splits conservés en cumulés bruts plutôt qu'en durées.",
            title_course, n,
        )


def _course_results(course: dict, *, url: str, evenement_title: str) -> list[ScrapedResult]:
    """Une épreuve de la charge → ses participants. Pure : aucune requête.

    `evenement_title` est reçu **déjà** décodé (`html.unescape`) par l'appelant :
    la charge porte des entités brutes (`&#8211;`, `&#038;`) dans tous les titres
    concernés, qui partiraient en base telles quelles.

    Deux prédicats distincts, à ne pas confondre en un seul (correction de revue
    finale, cf. plus bas) :

    - **écartement d'une liste d'engagés** — `status != "finish"` **et** aucune
      donnée chronométrique d'aucune sorte, ni `temps_finish` ni point de passage
      exploitable. Ce sont les 11 courses / 1 035 participations du panel
      inscrites mais pas encore courues, dont l'import créerait autant de
      participations sans temps que l'heuristique du projet classerait DNF. La
      double condition est délibérée : le comportement de `status` sur une course
      **en cours** n'a pas été observé au panel, et écarter sur ce seul critère
      jetterait des résultats partiels — lesquels vivent dans
      `points_de_passage`, d'où leur prise en compte ici. Une course en cours
      écartée rendrait un import **vide et sans erreur** ; pire, aucune
      `Participation` n'étant créée, le TTL de cache « course en cours » (10 min)
      ne pourrait jamais s'armer et la course resterait absente jusqu'au passage
      de `status` à « finish » par l'organisateur.
    - **repli `finisher`** (`course_non_chronometree`) — aucun `temps_finish`
      **et** `status == "finish"` : une course déclarée terminée mais non
      chronométrée, c'est-à-dire les 3 courses d'enfants du panel. La condition
      sur `status` est ce qui empêche des coureurs **encore en course** de sortir
      en `finisher`.
    """
    title_course = html.unescape(str(course.get("title_course") or "").strip())
    runners = course.get("runners") or []
    statut_course = str(course.get("status") or "").strip()
    terminee = statut_course == "finish"
    aucun_temps_final = not any(_total_time(runner) for runner in runners)

    if not terminee and aucun_temps_final and not any(
        _points_cumules(runner.get("points_de_passage")) for runner in runners
    ):
        logger.info(
            "Épreuve ok-time « %s » écartée : liste d'engagés (status=%r, "
            "%d participant(s), aucun temps ni point de passage).",
            title_course, statut_course, len(runners),
        )
        return []

    epreuve_id = str(course.get("epreuve_id") or "")
    # Invariants de la course, calculés **une fois** : les remonter dans la
    # compréhension rendait `_course_results` quadratique, `_is_relay_course`
    # parcourant tous les `runners` à chaque participant.
    # Le type est classé sur la **concaténation** des deux titres : le titre
    # d'épreuve seul est trompeur (« Format M individuel » du SwimRun Côte Beauté
    # sortirait en triathlon-m, « La Bourriquette » du Trail du Bourraid en
    # triathlon). Sur les 99 courses du panel, la concaténation en corrige 5 et
    # n'en dégrade aucune.
    event_name = qualify_event_name(evenement_title, title_course)
    event_type = classify_event_type(f"{evenement_title} {title_course}")
    event_date = _parse_date(course.get("date_course"))
    distance_km = _parse_distance(course.get("distance_course"))
    is_relay = _is_relay_course(title_course, runners)
    contexte = {
        "epreuve_id": epreuve_id,
        "heuredebut_course": course.get("heuredebut_course"),
        "reference_epreuve": course.get("reference_epreuve"),
        "status_course": statut_course,
    }

    resultats = [
        _build_result(
            runner,
            url=url,
            event_name=event_name,
            event_type=event_type,
            event_date=event_date,
            distance_km=distance_km,
            is_relay=is_relay,
            epreuve_id=epreuve_id,
            course_non_chronometree=aucun_temps_final and terminee,
            contexte=contexte,
        )
        for runner in runners
    ]
    _log_cumuls_conserves(resultats, title_course)
    return resultats
```

> **Notes de revue finale (#52) — constats I1 et I2.** Le plan d'origine dictait
> un seul prédicat, `non_chronometree = not any(_total_time(r) for r in runners)`,
> servant **à la fois** l'écartement des listes d'engagés et le repli `finisher`,
> et il recalculait les cinq invariants de course dans la compréhension.
>
> **I1** — `_total_time` ne lit que `temps_finish`, alors que les résultats
> partiels d'une course **en cours** vivent dans `points_de_passage`. Une épreuve
> `status="live"` aux participants chronométrés en passage mais à
> `temps_finish="00:00:00"` était donc **entièrement écartée** : `scrape_event_all`
> rendait une liste vide, `import_service` un import silencieusement vide et
> **sans erreur**, et — faute de `Participation` — le TTL de cache « course en
> cours » (10 min) ne pouvait jamais s'armer. Élargir naïvement le prédicat
> unique aurait cassé son second usage et fait sortir en `finisher` des coureurs
> encore en course : les deux décisions sont donc désormais **deux prédicats
> distincts**, `aucun_temps_final and terminee` d'un côté, l'absence de toute
> donnée chronométrique de l'autre. Cela reste conforme au §3.1 du design, dont
> ce code réalise enfin l'intention (« ne pas jeter de résultats partiels »).
>
> **I2** — `_is_relay_course` parcourt tous les `runners` : le rappeler par
> participant rendait `_course_results` **quadratique**. Mesuré en re-revue
> (2026-07-27, la mesure la plus récente et la plus complète — d'anciennes
> mesures sur d'autres machines avaient donné des valeurs différentes, sans
> changer le constat) à 500 / 1 000 / 2 000 participants : 0,060 / 0,196 /
> 0,706 s avant correction, contre 0,010 / 0,016 / 0,035 s après. La valeur
> absolue dépend de la machine ; ce qui compte est le passage de quadratique à
> linéaire. Le gros du coût tombait sur les plus grosses courses du panel,
> celles de Mimizan, l'épreuve la plus fournie (1 336 participations toutes
> courses confondues — un total d'épreuve, pas celui d'une course unique que
> `_course_results` traite). Les cinq invariants — relais, nom qualifié, type,
> date, distance — et le dictionnaire `contexte` sont sortis de la
> compréhension. Changement mécanique, sans effet sur le comportement : les
> valeurs sont identiques par construction.

- [ ] **Étape 5 : lancer les tests et vérifier qu'ils passent**

```bash
uv run pytest tests/test_oktime.py -v && uv run ruff check .
```
Attendu : 100 tests PASS (95 au plan d'origine + les 5 tests de revue finale).

- [ ] **Étape 6 : commit**

```bash
git add backend/app/scrapers/oktime.py backend/tests/test_oktime.py \
        backend/tests/fixtures/oktime_lacanau_48555.json \
        backend/tests/fixtures/oktime_engages_48999.json
git commit -m "feat(scrapers): oktime construit une Course par épreuve (#52)"
```

---

### Tâche 8 : `scrape_event_all` — orchestration

Le point d'entrée public : une URL, une (ou deux) requête(s), tous les
participants de toutes les épreuves de l'événement.

**Fichiers :**
- Modifier : `backend/app/scrapers/oktime.py`
- Modifier : `backend/tests/test_oktime.py`

**Interfaces :**
- Consomme : `_parse_url`, `_resolve_event_id`, `_fetch_results`,
  `_course_results`.
- Produit : `scrape_event_all(url: str) -> list[ScrapedResult]` — la seule voie
  d'import du projet, celle qu'appelle `registry.scrape_event_all`.

- [ ] **Étape 1 : écrire les tests qui échouent**

Ajouter à `backend/tests/test_oktime.py` :

```python
# --------------------------------------------------------------------------- #
# scrape_event_all
# --------------------------------------------------------------------------- #

def _client_factice(monkeypatch, pages=None, defaut=None):
    client = FakeClient(pages if pages is not None else {"/results": LACANAU}, defaut)
    monkeypatch.setattr(oktime.httpx, "Client", lambda *a, **k: client)
    return client


def test_scrape_event_all_un_seul_appel_pour_tout_levenement(monkeypatch):
    """L'API n'a pas de route par épreuve : un GET rend l'événement entier."""
    client = _client_factice(monkeypatch)

    resultats = oktime.scrape_event_all(URL_48555)

    assert client.calls == [
        "https://ok-time.fr/wp-json/gmcap/v1/evenements/48555/results"
    ]
    assert len(resultats) == 4  # 3 participants + 1 relais


def test_scrape_event_all_importe_toutes_les_epreuves(monkeypatch):
    _client_factice(monkeypatch)

    resultats = oktime.scrape_event_all(URL_48555)

    assert {r.event_name for r in resultats} == {
        "Triathlon de Lacanau 2026 – Samedi 02 mai - Triathlon L Individuel",
        "Triathlon de Lacanau 2026 – Samedi 02 mai - Relais L & Duo",
    }


def test_scrape_event_all_ignore_le_segment_race(monkeypatch):
    """L'URL du Sheet pointe une épreuve ; l'API rend quand même l'événement."""
    client = _client_factice(monkeypatch)

    resultats = oktime.scrape_event_all("https://classement.ok-time.fr/48555/race/59697")

    assert len(client.calls) == 1
    assert len(resultats) == 4


def test_scrape_event_all_source_url_est_lurl_demandee(monkeypatch):
    """`source_url` sert de clé de cache TTL : toutes les Course partagent celle
    du Sheet, pas une URL reconstruite."""
    _client_factice(monkeypatch)
    url = "https://classement.ok-time.fr/48555/race/59697"

    resultats = oktime.scrape_event_all(url)

    assert {r.source_url for r in resultats} == {url}


def test_scrape_event_all_resout_le_slug_avant_lapi(monkeypatch):
    """Forme éditoriale : 1 GET HTML pour l'id, puis l'appel API."""
    client = _client_factice(
        monkeypatch, pages={"/evenement/": PAGE_EVENEMENT, "/results": LACANAU}
    )

    resultats = oktime.scrape_event_all(
        "https://ok-time.fr/evenement/triathlon-de-lacanau-2026/"
    )

    assert client.calls == [
        "https://ok-time.fr/evenement/triathlon-de-lacanau-2026/",
        "https://ok-time.fr/wp-json/gmcap/v1/evenements/48555/results",
    ]
    assert len(resultats) == 4


def test_scrape_event_all_ecarte_les_listes_dengages(monkeypatch):
    """L'événement ne rend que la course enfants ; la liste d'engagés est écartée."""
    _client_factice(monkeypatch, pages={"/results": ENGAGES})

    resultats = oktime.scrape_event_all("https://classement.ok-time.fr/48999")

    assert len(resultats) == 1
    assert resultats[0].event_name.endswith("Course des enfants UNICEF")


def test_scrape_event_all_url_obsolete_leve_avant_toute_requete(monkeypatch):
    client = _client_factice(monkeypatch)

    with pytest.raises(ValueError, match="obsolète"):
        oktime.scrape_event_all("https://ok-time.fr/course/triathlon-l/")

    assert client.calls == []


def test_scrape_event_all_evenement_sans_epreuve(monkeypatch):
    """Charge valide mais `data` vide : liste vide, sans exception."""
    _client_factice(
        monkeypatch,
        pages={"/results": {"success": True, "evenement_title": "X", "count": 0, "data": []}},
    )

    assert oktime.scrape_event_all(URL_48555) == []
```

- [ ] **Étape 2 : lancer les tests et vérifier qu'ils échouent**

```bash
uv run pytest tests/test_oktime.py -v -k "scrape_event_all"
```
Attendu : ÉCHEC — `AttributeError: ... has no attribute 'scrape_event_all'`.

- [ ] **Étape 3 : écrire l'implémentation minimale**

Ajouter à la fin de `oktime.py` :

```python
# --------------------------------------------------------------------------- #
# Point d'entrée
# --------------------------------------------------------------------------- #

def scrape_event_all(url: str) -> list[ScrapedResult]:
    """Tous les participants de **toutes** les épreuves de l'événement.

    L'API n'expose aucune route par épreuve : une URL pointant une épreuve
    rapporte l'événement entier, et on l'importe entier — comme les heats Breizh
    Chrono et les onglets chronoplace. Coût : un appel, deux si l'URL est de la
    forme éditoriale `/evenement/<slug>/`.

    `source_url` reste l'URL **demandée** : c'est la clé de cache TTL, elle doit
    correspondre au lien du Sheet et non à une forme reconstruite.
    """
    event_id, slug = _parse_url(url)
    with httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS) as client:
        if not event_id:
            event_id = _resolve_event_id(client, slug)
        charge = _fetch_results(client, event_id)

    evenement_title = html.unescape(str(charge.get("evenement_title") or "").strip())
    resultats: list[ScrapedResult] = []
    for course in charge.get("data") or []:
        resultats.extend(
            _course_results(course, url=url, evenement_title=evenement_title)
        )
    return resultats
```

- [ ] **Étape 4 : lancer les tests et vérifier qu'ils passent**

```bash
uv run pytest tests/test_oktime.py -v && uv run ruff check .
```
Attendu : 108 tests PASS (103 au plan d'origine + les 5 tests de revue finale)
— le total du module, vérifié en exécutant l'ensemble
du plan avant sa publication.

- [ ] **Étape 5 : commit**

```bash
git add backend/app/scrapers/oktime.py backend/tests/test_oktime.py
git commit -m "feat(scrapers): oktime importe l'événement entier (#52)"
```

---

### Tâche 9 : enregistrement dans le registre, intégration et documentation

Le scraper n'est atteignable qu'une fois enregistré. C'est aussi le moment où
`ok-time.fr` quitte `ignored_by_host` dans les bilans CLI — conséquence assumée
et documentée (§2.1 du design).

**Fichiers :**
- Modifier : `backend/app/scrapers/registry.py`
- Modifier : `backend/tests/test_registry.py`
- Modifier : `backend/tests/test_integration_scrapers.py`
- Modifier : `AGENTS.md`

**Interfaces :**
- Consomme : `oktime.scrape_event_all` (tâche 8).
- Produit : `registry.OkTimeProvider`, `"oktime"` dans `registry.provider_names()`.

- [ ] **Étape 1 : écrire les tests qui échouent**

`backend/tests/test_registry.py` n'importe aujourd'hui que `registry`. Ajouter
`import pytest` **dans le bloc d'imports en tête** (E402), de sorte qu'il
devienne :

```python
import pytest

from app.scrapers import registry
```

Puis ajouter les tests à la fin du fichier :

```python
@pytest.mark.parametrize(
    "url",
    [
        "https://classement.ok-time.fr/48555",
        "https://classement.ok-time.fr/48555/race/59697",
        "https://ok-time.fr/evenement/triathlon-de-lacanau-2026/",
        "https://www.ok-time.fr/evenement/triathlon-de-lacanau-2026/",
        "https://classement.ok-time.fr:443/48555",
    ],
)
def test_detect_provider_oktime(url):
    """Domaine exact, vrais sous-domaines, port explicite."""
    assert registry.detect_provider(url) == "oktime"


def test_detect_provider_rejette_un_host_sosie():
    """`hostname` et non `netloc`, et suffixe précédé d'un point : sans cette
    garde, `evilok-time.fr` matcherait (cf. la garde RaceResultProvider)."""
    assert registry.detect_provider("https://evilok-time.fr/48555") != "oktime"


def test_provider_names_contient_oktime():
    assert "oktime" in registry.provider_names()
```

Ajouter à `backend/tests/test_integration_scrapers.py`, dans le dict `LIVE_URLS`
(après l'entrée `chronoplace`) :

```python
    # Triathlon de Lacanau 2026 : 5 épreuves partageant date et type — l'épreuve
    # qui a servi au sondage d'API. La forme `/race/<id>` est celle du Sheet.
    "oktime": "https://classement.ok-time.fr/48555/race/59697",
```

- [ ] **Étape 2 : lancer les tests et vérifier qu'ils échouent**

```bash
uv run pytest tests/test_registry.py -v
```
Attendu : ÉCHEC — `assert 'playwright' == 'oktime'` (les URLs tombent sur le
fallback tant que le provider n'existe pas).

- [ ] **Étape 3 : écrire l'implémentation minimale**

Dans `backend/app/scrapers/registry.py` :

1. ajouter `oktime` à la liste d'imports `from app.scrapers import (...)`, dans
   l'ordre alphabétique (entre `klikego` et `prolivesport`) ;
2. ajouter la classe après `ChronoplaceProvider` :

```python
class OkTimeProvider:
    name = "oktime"

    # `ok-time.fr` et ses sous-domaines : `classement.ok-time.fr` (la SPA de
    # classement) et l'apex (le site éditorial, qui sert l'API JSON). Allowlist
    # explicite, comme Wiclax et RaceResult.
    _HOST = "ok-time.fr"

    def matches(self, url: str) -> bool:
        # `hostname` (et non `netloc`) : sans lui, un port explicite ou des
        # credentials feraient rater le match. Domaine exact ou **vrai**
        # sous-domaine : un suffixe brut suivrait aussi un host sosie du type
        # `evilok-time.fr` (cf. la garde RaceResultProvider).
        host = (urlparse(url).hostname or "").lower()
        return host == self._HOST or host.endswith(f".{self._HOST}")

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return oktime.scrape_event_all(url)
```

3. ajouter `OkTimeProvider(),` à la fin de la liste `PROVIDERS`, après
   `ChronoplaceProvider()`. Aucun conflit d'ordre avec les providers existants :
   aucun autre ne matche `ok-time.fr`, la place est donc libre.

- [ ] **Étape 4 : lancer les tests et vérifier qu'ils passent**

```bash
uv run pytest tests/test_registry.py -v
uv run pytest -m "not integration" -q
uv run ruff check .
```
Attendu : suite complète verte, ruff sans erreur. Aucun test préexistant ne doit
changer de résultat : l'ajout d'un provider est purement additif.

- [ ] **Étape 5 : vérifier le scraper contre la source réelle**

```bash
uv run pytest -m integration -k oktime -v
```
Attendu : `test_detection[oktime-...]` et `test_scrape_event_all_live[oktime-...]`
PASS. Si le schéma de l'API a bougé depuis le sondage du 2026-07-26, c'est ici
qu'on le voit — corriger le scraper **et** mettre à jour les fixtures, pas
l'inverse.

- [ ] **Étape 6 : mettre à jour la documentation**

Dans `AGENTS.md`, section « Fournisseurs supportés » :

- ajouter `ok-time` à l'énumération de tête : `…, RaceResult, Chronoplace, ok-time — tous en **épreuve complète**.`
- ajouter le paragraphe suivant, après celui de Chronoplace :

```markdown
ok-time.fr (issue #52) se lit sur une API JSON WordPress publique
(`/wp-json/gmcap/v1/evenements/{id}/results`) : **un seul appel** rend
l'événement entier, toutes épreuves comprises — ni Playwright ni parsing HTML
sur le chemin nominal. Les points de passage sont **cumulés** et différenciés en
durées de segment, rangées dans `segments` (chemin générique) avec les libellés
de la source : les `id` de points ne sont pas sémantiques (`12|2` vaut « T2 »
sur une épreuve, « VELO » sur une autre) et 55 des 99 courses du panel sortent
du motif triathlon. Le type de course est classé sur la **concaténation**
`evenement_title + title_course` (le titre d'épreuve seul est trompeur). Deux
formes d'URL sont supportées, `classement.ok-time.fr/<id>[/race/<raceId>]` et
`ok-time.fr/evenement/<slug>/` ; les préfixes `/course/` et `/competition/` sont
**obsolètes** et rejetés avec un message qui le dit — trois URLs du Sheet en
relèvent et deviennent, ok-time étant désormais supporté, des épreuves en erreur
dans les bilans plutôt que des liens ignorés. Vérité d'API (panel de 21
événements / 99 courses / 12 644 participations) :
`docs/superpowers/specs/2026-07-26-oktime-scraper-design.md`.
```

- [ ] **Étape 7 : commit**

```bash
git add backend/app/scrapers/registry.py backend/tests/test_registry.py \
        backend/tests/test_integration_scrapers.py AGENTS.md
git commit -m "feat(scrapers): enregistre ok-time dans le registre (#52)"
```

---

## Hors périmètre (rappel du §7 du design)

Ne pas traiter dans cette branche, même si l'occasion se présente :

- **Les 3 URLs obsolètes du Sheet** — c'est le Sheet qu'on corrige, pas le
  scraper. Le message d'erreur les qualifie, c'est tout ce que le code doit faire.
- **Participants sans dossard** (30 au panel, dont 27 dans une course d'engagés
  écartée) : `Participation` étant unique sur `(course_id, bib_number)`, un
  `bib_number` vide échappe à l'upsert et se redouble au re-scrape. Limite connue
  du projet, déjà rencontrée sur Sportinnovation, non spécifique à ok-time.
- **`club` absent sur certaines épreuves** (0/781 à Lacanau 2026) : vide à la
  source, comme Carnac 2025 chez Sportinnovation.
- **Route `/runner/{id}`** : le scraping athlète-unique a été supprimé du projet.
- **Factorisation de `_secs`/`_fmt_secs`** entre `klikego`, `timepulse` et
  `oktime` : refacto à part (cf. la note d'en-tête de `registry.py`).
