# Moteur RaceResult générique — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un scraper `raceresult` couvrant `my*.raceresult.com`, `espace-competition.com` et `chronoconsult.fr` via l'API JSON publique RaceResult, sans Playwright.

**Architecture :** Un module `backend/app/scrapers/raceresult.py` (fonctions, pas classe — calqué sur `wiclax.py` / `sportinnovation.py`), plus un `RaceResultProvider` dans `registry.py`. Un unique `httpx.Client(follow_redirects=True)` est ouvert dans `scrape_event_all` et passé à tous les helpers, ce qui rend l'ensemble testable sans réseau. Aucune autre couche n'est touchée : `provider_names()` dérive de `PROVIDERS`, les consommateurs suivent automatiquement.

**Tech Stack :** Python 3.13, uv, httpx, BeautifulSoup/lxml (JSON-LD), pytest, ruff.

---

## ⚠️ ERRATA — l'API décrite ci-dessous est fausse (2026-07-19)

**Ce plan a été exécuté puis invalidé par sa revue finale.** Son sondage d'API
(2026-07-18) portait sur une seule épreuve ; le moteur bâti dessus ne fonctionne
que sur elle. Un re-sondage sur **9 épreuves et les trois façades** a produit
`docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md`, **qui fait foi** :
en cas de contradiction avec le corps de ce plan, c'est le sondage qui a raison.

Sept corrections, dont chacune casse le moteur actuel sur une partie du parc :

| # | Ce que ce plan affirme | Ce que l'API fait réellement |
| --- | --- | --- |
| 1 | route `/{id}/RRPublish/data/…` | **alias hérité** : 404 sur toute épreuve de la saison en cours. Route réelle `/{id}/results/…` |
| 2 | base `my2/my3/my4.raceresult.com` | **`my.raceresult.com`** (apex) sert les 9 épreuves ; aucune résolution de shard nécessaire |
| 3 | listes sous `config["lists"]`, en arbre | `config["lists"]` vaut `null` ; listes dans **`TabConfig.Lists`**, tableau plat, **contest explicite** |
| 4 | le contest se résout empiriquement | il est **donné** — la découverte par essais répond à un problème propre à l'alias |
| 5 | `DataFields` sous `payload["list"]` | à la **racine** du payload. *L'algorithme d'indexation, lui, reste correct* |
| 6 | `data` = 2 niveaux, niveau 2 = statut | profondeur **variable** (parfois dans la même épreuve) ; certains groupes sont des **sexes**, pas des statuts |
| 7 | `Live` sépare les listes d'affichage | c'est **`Mode == "hidden"`** ; le filtre `Live` vide entièrement certaines épreuves |

S'y ajoutent : `chronoconsult.fr` sert l'`eventId` **entre guillemets** (aucune
épreuve résolvable sans cela), et le vocabulaire d'expressions reconnu est trop
étroit — sur une épreuve du panel, 506 lignes sur 507 ressortent sans nom ni
temps. Détail et mesures : §6 et §8 du sondage.

**Ne pas ré-exécuter ce plan tel quel.** Les Tasks 1 à 5 restent globalement
valides ; les Tasks 3, 4, 6 et 7 sont à refonder sur le sondage.

---

## Global Constraints

- Design de référence : `docs/superpowers/specs/2026-07-19-raceresult-scraper-design.md`. En cas de doute, il fait foi.
- **Vérité d'API : `docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md`** — prime sur ce plan *et* sur le design (cf. errata ci-dessus).
- Commandes lancées **depuis `backend/`**, toujours via `uv run` (aucun venv à activer).
- Tests unitaires **sans réseau**. Tout appel réel va derrière `@pytest.mark.integration`.
- Nom du provider : exactement `raceresult` (chaîne utilisée par la CLI, le Sheet et l'API).
- Surface publique du module : `scrape_event_all(url) -> list[ScrapedResult]` **uniquement**. Pas de `scrape()` athlète-unique — la voie a été supprimée du projet et `ScraperProtocol` ne l'expose plus.
- Aucun Playwright, y compris en repli.
- Commentaires, docstrings et messages d'erreur en **français avec accents**.
- Commits en Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`).
- Les temps restent des **strings** normalisées par `utils.normalize_time`.
- `event_type` est délégué à `classify.classify_event_type` — zéro logique de classification locale.
- Lint : `uv run ruff check .` doit passer avant chaque commit.

---

## Structure des fichiers

| Fichier | Responsabilité |
|---|---|
| `backend/app/scrapers/utils.py` *(modifié)* | `split_athlete_name` gère `Prénom NOM` ; nouveau `qualify_event_name` partagé |
| `backend/app/scrapers/wiclax.py` *(modifié)* | `_qualify_event_name` délègue à `utils.qualify_event_name` |
| `backend/app/scrapers/raceresult.py` *(créé)* | tout le moteur : résolution d'URL, API, mapping, fusion |
| `backend/app/scrapers/registry.py` *(modifié)* | `RaceResultProvider` + entrée dans `PROVIDERS` |
| `backend/tests/test_raceresult.py` *(créé)* | tests unitaires du moteur (sans réseau) |
| `backend/tests/test_scrapers_utils.py` *(modifié)* | non-régression `split_athlete_name` |
| `backend/tests/test_integration_scrapers.py` *(modifié)* | entrée `raceresult` dans `LIVE_URLS` |
| `backend/tests/fixtures/raceresult_config_rumilly.json` *(créé)* | config API réduite |
| `backend/tests/fixtures/raceresult_list_rumilly_m.json` *(créé)* | payload liste : finisher + DNF + DNS |
| `backend/tests/fixtures/raceresult_page_meta.html` *(créé)* | page `/results` réduite au JSON-LD |
| `backend/tests/fixtures/chronoconsult_result_page.html` *(créé)* | page façade pour la résolution d'`eventId` |
| `AGENTS.md` *(modifié)* | documentation du fournisseur |

---

### Task 1 : `split_athlete_name` gère la convention `Prénom NOM`

RaceResult sort `Alexis ROUX`, l'inverse de la convention `NOM Prénom` de Wiclax/TimePulse. Le repli actuel prend le **dernier token** comme nom, donc `"Jean DE LA TOUR"` donne nom = `"TOUR"`. On ajoute : si les derniers tokens sont en majuscules, on les prend tous.

**Files:**
- Modify: `backend/app/scrapers/utils.py:96-115`
- Test: `backend/tests/test_scrapers_utils.py`

**Interfaces:**
- Consumes: rien.
- Produces: `split_athlete_name(full: str) -> tuple[str, str]` — signature inchangée, renvoie `(nom, prénom)`.

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter à la fin de `backend/tests/test_scrapers_utils.py` :

```python
from app.scrapers.utils import split_athlete_name


@pytest.mark.parametrize("brut,attendu", [
    # Convention RaceResult « Prénom NOM » — le nom est le bloc majuscule final.
    ("Alexis ROUX", ("ROUX", "Alexis")),
    ("Jean DE LA TOUR", ("DE LA TOUR", "Jean")),
    ("Marie-Claire LE GALL", ("LE GALL", "Marie-Claire")),
    # Convention Wiclax/TimePulse « NOM Prénom » — comportement inchangé.
    ("ROUX Alexis", ("ROUX", "Alexis")),
    ("LE GALL Marie-Claire", ("LE GALL", "Marie-Claire")),
    # Aucun bloc majuscule : repli sur le dernier token (comportement inchangé).
    ("Jean Dupont", ("Dupont", "Jean")),
    # Cas dégénérés.
    ("", ("", "")),
    ("MARTIN", ("MARTIN", "")),
])
def test_split_athlete_name(brut, attendu):
    assert split_athlete_name(brut) == attendu
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

```bash
uv run pytest tests/test_scrapers_utils.py::test_split_athlete_name -v
```

Attendu : ÉCHEC sur `"Jean DE LA TOUR"` — obtenu `("TOUR", "Jean DE LA")`, attendu `("DE LA TOUR", "Jean")`.

- [ ] **Step 3 : Implémenter**

Remplacer intégralement le corps de `split_athlete_name` dans `backend/app/scrapers/utils.py` :

```python
def split_athlete_name(full: str) -> tuple[str, str]:
    """Scinde un nom complet en (nom, prénom), quelle que soit la convention.

    Deux conventions coexistent chez les fournisseurs :
      - « NOM Prénom » (Wiclax, TimePulse) : bloc majuscule **en tête** ;
      - « Prénom NOM » (RaceResult) : bloc majuscule **en queue**.

    Le bloc majuscule est pris dans son intégralité des deux côtés, sinon un nom
    à particule (« Jean DE LA TOUR ») se réduirait à son dernier token. Sans
    aucun bloc majuscule, on retombe sur la convention « prénom(s) puis nom ».
    """
    parts = full.strip().split("\n")[0].strip().split()
    if not parts:
        return "", ""
    if parts[0].isupper():
        # « NOM Prénom » : le nom est le préfixe majuscule.
        i = 0
        while i < len(parts) and parts[i].isupper():
            i += 1
        return " ".join(parts[:i]), " ".join(parts[i:])
    if parts[-1].isupper():
        # « Prénom NOM » : le nom est le suffixe majuscule, particules incluses.
        i = len(parts)
        while i > 0 and parts[i - 1].isupper():
            i -= 1
        return " ".join(parts[i:]), " ".join(parts[:i])
    return parts[-1], " ".join(parts[:-1])
```

- [ ] **Step 4 : Lancer les tests**

```bash
uv run pytest tests/test_scrapers_utils.py -v
uv run pytest -m "not integration" -q
```

Attendu : tout passe. La suite complète est le vrai garde-fou ici — `split_athlete_name` est appelé par wiclax, timepulse et prolivesport.

- [ ] **Step 5 : Lint et commit**

```bash
uv run ruff check .
git add app/scrapers/utils.py tests/test_scrapers_utils.py
git commit -m "fix(scrapers): split_athlete_name gère la convention Prénom NOM"
```

---

### Task 2 : Routage des trois hosts et résolution de l'`eventId`

Le moteur commence par savoir *quelles* URLs il prend et *quel* `eventId` RaceResult elles désignent. Un host `my*.raceresult.com` porte l'id dans son path (zéro requête) ; les façades `espace-competition.com` et `chronoconsult.fr` exigent un GET pour lire l'appel `new RRPublish(el, <eventId>, …)`.

`comp_uid` est **ignoré** : ce n'est pas la clé de données.

**Files:**
- Create: `backend/app/scrapers/raceresult.py`
- Create: `backend/tests/fixtures/chronoconsult_result_page.html`
- Create: `backend/tests/test_raceresult.py`
- Modify: `backend/app/scrapers/registry.py`

**Interfaces:**
- Consumes: `ScrapedResult` (`app.scrapers.base`), `ScraperProtocol` (`app.scrapers.registry`).
- Produces:
  - `raceresult.HEADERS: dict[str, str]`
  - `raceresult._api_base(url: str) -> str` — racine HTTPS de l'API pour cette URL
  - `raceresult._resolve_event_id(url: str, client: httpx.Client) -> str`
  - `raceresult.scrape_event_all(url: str) -> list[ScrapedResult]` (stub à ce stade)
  - `registry.RaceResultProvider` avec `name = "raceresult"` et `_HOSTS`

- [ ] **Step 1 : Créer la fixture de page façade**

Créer `backend/tests/fixtures/chronoconsult_result_page.html` :

```html
<!--
  Fixture réduite à la main d'une page façade ChronoConsult.
  Provenance : https://www.chronoconsult.fr/result/triathlon-de-roanne-villerest/
  Récupérée le 2026-07-18. Seuls le <script> RRPublish et le lien logo sont
  conservés ; l'`eventId` RaceResult est 399938, `comp_uid` est un identifiant
  interne au WordPress et n'a rien à voir avec l'API.
-->
<html>
<head><title>Résultats — Triathlon de Roanne Villerest</title></head>
<body>
  <div id="divRRPublish"></div>
  <script type="text/javascript">
    var rrp = new RRPublish(document.getElementById("divRRPublish"),  399938 , 'results');
    rrp.ShowTitle = false;
  </script>
  <a href="/index.php?page=resultats&amp;comp_uid=3178">Retour</a>
  <img src="https://my.raceresult.com/399938/api/logo" alt="logo">
</body>
</html>
```

- [ ] **Step 2 : Écrire les tests qui échouent**

Créer `backend/tests/test_raceresult.py` :

```python
"""
Tests unitaires pour scrapers/raceresult.py (sans réseau).

Fixtures réduites à la main, provenance et date en tête de chaque fichier.
Les appels HTTP passent par un faux client httpx (pattern test_sportinnovation.py)
ou par monkeypatch des helpers `_fetch_*` (pattern test_wiclax.py).
"""
import json
from pathlib import Path

import httpx
import pytest

from app.scrapers import raceresult, registry

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(nom: str) -> str:
    return (FIXTURES / nom).read_text(encoding="utf-8")


class _FauxClient:
    """Client httpx minimal : sert des réponses par sous-chaîne d'URL.

    `routes` mappe un fragment d'URL vers (status_code, texte). Une URL sans
    route déclarée lève, pour qu'un appel réseau inattendu casse le test au lieu
    de passer silencieusement.
    """

    def __init__(self, routes: dict[str, tuple[int, str]]):
        self.routes = routes
        self.appels: list[str] = []

    def get(self, url: str, **kwargs) -> httpx.Response:
        self.appels.append(url)
        for fragment, (status, texte) in self.routes.items():
            if fragment in url:
                return httpx.Response(
                    status, text=texte, request=httpx.Request("GET", url)
                )
        raise AssertionError(f"URL non routée dans le faux client : {url}")


# ── Routage ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    "https://my.raceresult.com/399938/results",
    "https://my3.raceresult.com/393893/",
    "https://www.espace-competition.com/index.php?page=resultats&comp_uid=3178",
    "https://www.chronoconsult.fr/result/triathlon-de-roanne-villerest/",
])
def test_routage_vers_raceresult(url):
    assert registry.detect_provider(url) == "raceresult"


@pytest.mark.parametrize("url", [
    "https://evilraceresult.com/399938/results",
    "https://raceresult.com.attaquant.net/399938/",
    "https://www.klikego.com/resultats/x/1",
])
def test_hosts_sosies_non_captes(url):
    assert registry.detect_provider(url) != "raceresult"


# ── Résolution de l'eventId ──────────────────────────────────────────────────

def test_event_id_depuis_le_path_sans_requete():
    client = _FauxClient({})
    assert raceresult._resolve_event_id(
        "https://my.raceresult.com/399938/results", client
    ) == "399938"
    assert client.appels == [], "aucune requête ne doit partir pour un host RaceResult"


def test_event_id_depuis_la_facade_chronoconsult():
    """L'id vient de `new RRPublish(el, 399938, …)`, pas de `comp_uid`."""
    client = _FauxClient({
        "chronoconsult.fr": (200, _fixture("chronoconsult_result_page.html")),
    })
    url = "https://www.chronoconsult.fr/result/triathlon-de-roanne-villerest/"

    assert raceresult._resolve_event_id(url, client) == "399938"


def test_event_id_repli_sur_le_logo():
    """Sans appel RRPublish lisible, le lien `/api/logo` porte le même id."""
    html = '<html><body><img src="https://my.raceresult.com/406844/api/logo"></body></html>'
    client = _FauxClient({"espace-competition.com": (200, html)})
    url = "https://www.espace-competition.com/index.php?page=resultats&comp_uid=3178"

    assert raceresult._resolve_event_id(url, client) == "406844"


def test_event_id_introuvable_leve_value_error():
    client = _FauxClient({"espace-competition.com": (200, "<html><body>rien</body></html>")})
    url = "https://www.espace-competition.com/index.php?comp_uid=3178"

    with pytest.raises(ValueError, match="espace-competition.com"):
        raceresult._resolve_event_id(url, client)


def test_api_base_suit_le_host_raceresult():
    assert raceresult._api_base("https://my3.raceresult.com/393893/") == "https://my3.raceresult.com"
    assert raceresult._api_base("https://www.chronoconsult.fr/result/x/") == "https://my.raceresult.com"
```

- [ ] **Step 3 : Lancer les tests pour vérifier qu'ils échouent**

```bash
uv run pytest tests/test_raceresult.py -v
```

Attendu : ÉCHEC à la collecte — `ImportError: cannot import name 'raceresult' from 'app.scrapers'`.

- [ ] **Step 4 : Créer le module avec la résolution d'URL**

Créer `backend/app/scrapers/raceresult.py` :

```python
"""
Moteur RaceResult générique — issue #50.

Couvre trois façades d'un même produit, toutes alimentées par la même API JSON
publique (aucun Playwright, la page RRPublish est un SPA qui n'apporte rien de
plus) :

  - `my*.raceresult.com`      — RaceResult direct, l'eventId est dans le path ;
  - `espace-competition.com`  — front RaceResult, `new RRPublish(el, <id>, …)` ;
  - `chronoconsult.fr`        — façade WordPress au-dessus de RaceResult.

Chaînage d'appels — CORRIGÉ au sondage du 2026-07-19 (cf. errata) :
  1. GET {base}/{eventId}/results/config?page=results
     → base = https://my.raceresult.com (apex, universel).
     → listes dans config["TabConfig"]["Lists"] (tableau plat, contest explicite).
  2. GET {base}/{eventId}/results/list?key=…&listname=…&contest=N&page=results
  3. La date d'épreuve n'est dans aucun des deux : elle vit dans le JSON-LD
     schema.org de la page {base}/{eventId}/results.

  ANCIENNE FORME (fausse, conservée pour mémoire) : /{eventId}/RRPublish/data/…
  est un alias hérité qui répond 404 sur toute épreuve de la saison en cours.
  Le 301 qu'il émettait vers /results/ était l'indice ignoré.
"""
import logging
import re
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json,*/*",
}

# Racine par défaut quand l'URL d'entrée est une façade tierce : toutes les
# façades sondées pointent leurs assets vers my.raceresult.com.
_API_DEFAUT = "https://my.raceresult.com"

# `RRPublish(document.getElementById("divRRPublish"),  399938 , 'results')` — les
# espaces autour de l'argument sont fréquents et doivent être tolérés.
_RE_RRPUBLISH = re.compile(r"RRPublish\s*\([^,]+,\s*(\d+)\s*,")
# Repli : le logo de l'épreuve est servi par l'API et porte le même id.
_RE_LOGO = re.compile(r"raceresult\.com/(\d+)/api/logo")


def _api_base(url: str) -> str:
    """Racine HTTPS de l'API RaceResult à interroger pour cette URL.

    Un host `my*.raceresult.com` est déjà la bonne racine (les épreuves sont
    réparties sur plusieurs serveurs : my, my2, my3…). Toute autre façade est
    servie depuis la racine par défaut.
    """
    host = (urlparse(url).netloc or "").lower()
    if host == "raceresult.com" or host.endswith(".raceresult.com"):
        return f"https://{host}"
    return _API_DEFAUT


def _resolve_event_id(url: str, client: httpx.Client) -> str:
    """Identifiant d'épreuve RaceResult désigné par l'URL.

    Sur un host RaceResult, c'est le premier segment numérique du path — zéro
    requête. Sur une façade, une seule page est téléchargée : l'id se lit dans
    l'appel `new RRPublish(...)`, avec repli sur l'URL du logo. Le `comp_uid` des
    URLs `espace-competition.com` est délibérément ignoré : c'est un identifiant
    interne au front, pas la clé de données.
    """
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    if host == "raceresult.com" or host.endswith(".raceresult.com"):
        for segment in parsed.path.strip("/").split("/"):
            if segment.isdigit():
                return segment
        raise ValueError(f"Aucun identifiant d'épreuve dans l'URL RaceResult : {url}")

    resp = client.get(url, headers=HEADERS)
    resp.raise_for_status()
    for motif in (_RE_RRPUBLISH, _RE_LOGO):
        trouve = motif.search(resp.text)
        if trouve:
            return trouve.group(1)
    raise ValueError(
        f"Identifiant d'épreuve RaceResult introuvable dans la page : {url}"
    )


def scrape_event_all(url: str) -> list:
    """Importe tous les participants d'une épreuve RaceResult."""
    raise NotImplementedError  # complété en Task 6
```

- [ ] **Step 5 : Enregistrer le provider**

Dans `backend/app/scrapers/registry.py`, ajouter `raceresult` à l'import du haut de fichier :

```python
from app.scrapers import (
    breizhchrono,
    klikego,
    prolivesport,
    raceresult,
    sportinnovation,
    timepulse,
    wiclax,
)
```

Puis insérer la classe juste avant `class PlaywrightProvider:` :

```python
class RaceResultProvider:
    name = "raceresult"

    # Trois façades d'un même produit RaceResult (issue #50). Allowlist
    # **explicite**, comme Wiclax : détecter du RaceResult par le contenu
    # obligerait à télécharger la page de toute URL inconnue avant de savoir la
    # traiter. Un nouveau front RaceResult = une ligne ici.
    _HOSTS = ("raceresult.com", "espace-competition.com", "chronoconsult.fr")

    def matches(self, url: str) -> bool:
        host = (urlparse(url).netloc or "").lower()
        # Domaine exact ou vrai sous-domaine : un suffixe brut suivrait aussi un
        # host sosie du type `evilraceresult.com`.
        return any(host == h or host.endswith(f".{h}") for h in self._HOSTS)

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return raceresult.scrape_event_all(url)
```

Enfin ajouter l'instance à la liste `PROVIDERS` :

```python
PROVIDERS: list[ScraperProtocol] = [
    BreizhChronoProvider(),
    WiclaxProvider(),
    KlikegoProvider(),
    TimePulseProvider(),
    ProLiveSportProvider(),
    SportInnovationProvider(),
    RaceResultProvider(),
]
```

- [ ] **Step 6 : Lancer les tests**

```bash
uv run pytest tests/test_raceresult.py tests/test_registry.py -v
```

Attendu : PASS sur les 9 tests de `test_raceresult.py` et sur `test_registry.py`.

- [ ] **Step 7 : Lint et commit**

```bash
uv run ruff check .
git add app/scrapers/raceresult.py app/scrapers/registry.py \
        tests/test_raceresult.py tests/fixtures/chronoconsult_result_page.html
git commit -m "feat(scrapers): routage RaceResult et résolution de l'eventId"
```

---

### Task 3 : Métadonnées (JSON-LD) et config de l'épreuve

> ⚠️ **Partiellement invalidée (errata).** Le volet JSON-LD reste exact et vérifié
> sur 9 épreuves. Le volet config est faux sur deux points : la route
> (`/results/config`, pas `/RRPublish/data/config`) et la forme des listes
> (`config["TabConfig"]["Lists"]`, tableau plat à contest explicite —
> `config["lists"]` vaut `null`). La fixture `raceresult_config_rumilly.json` et
> `_iter_list_specs` sont donc à refaire depuis une capture de la bonne route.


Ni `config` ni `list` ne portent de date : la seule source est le JSON-LD schema.org de la page `/{eventId}/results`, qui donne aussi le nom et la ville. `config` livre la `key` d'accès, les contests, les listes et les splits.

**Files:**
- Modify: `backend/app/scrapers/raceresult.py`
- Create: `backend/tests/fixtures/raceresult_page_meta.html`
- Create: `backend/tests/fixtures/raceresult_config_rumilly.json`
- Modify: `backend/tests/test_raceresult.py`

**Interfaces:**
- Consumes: `_api_base` (Task 2).
- Produces:
  - `_fetch_meta(event_id: str, base: str, client: httpx.Client) -> tuple[str, date | None, str]` → `(nom, date, ville)`
  - `_fetch_config(event_id: str, base: str, client: httpx.Client) -> dict`
  - `_iter_list_specs(config: dict) -> list[tuple[str, str]]` → `(listname, contest_indice)`

- [ ] **Step 1 : Créer les fixtures**

Créer `backend/tests/fixtures/raceresult_page_meta.html` :

```html
<!--
  Fixture réduite à la main : page /399938/results de RaceResult, ramenée au
  seul bloc JSON-LD schema.org (la seule source de la date d'épreuve dans tout
  le produit — ni `config` ni `list` ne la portent).
  Provenance : https://my.raceresult.com/399938/results — 2026-07-18.
-->
<html>
<head>
  <script type="application/ld+json">
  {"@context":"https://schema.org","@type":"Event",
   "name":"Triathlon de Roanne Villerest","startDate":"2026-06-18",
   "location":{"@type":"Place","address":{"@type":"PostalAddress",
     "addressLocality":"SAINT-HERBLAIN"}}}
  </script>
</head>
<body><div id="divRRPublish"></div></body>
</html>
```

Créer `backend/tests/fixtures/raceresult_config_rumilly.json` :

```json
{
  "_provenance": "GET https://my3.raceresult.com/393893/RRPublish/data/config?page=results — 2026-07-18, réduite à la main (Triathlon de Rumilly).",
  "key": "0123456789abcdef",
  "eventname": "Triathlon de Rumilly",
  "server": "my3.raceresult.com",
  "contests": {
    "1": "Distance XS",
    "4": "Distance M"
  },
  "splits": {
    "1": {"Label": "Natation"},
    "2": {"Label": "Transition 1"},
    "3": {"Label": "Vélo"},
    "4": {"Label": "Transition 2"},
    "5": {"Label": "Course à pied"}
  },
  "lists": {
    "En ligne": {
      "Final": {"Contest": 0, "Name": "En ligne|Final"},
      "Relais": {"Contest": 3, "Name": "En ligne|Relais"}
    }
  }
}
```

- [ ] **Step 2 : Écrire les tests qui échouent**

Ajouter à `backend/tests/test_raceresult.py` :

```python
from datetime import date


def test_fetch_meta_lit_le_json_ld():
    client = _FauxClient({"/results": (200, _fixture("raceresult_page_meta.html"))})

    nom, jour, ville = raceresult._fetch_meta("399938", "https://my.raceresult.com", client)

    assert nom == "Triathlon de Roanne Villerest"
    assert jour == date(2026, 6, 18)
    assert ville == "SAINT-HERBLAIN"


def test_fetch_meta_sans_json_ld_ne_leve_pas():
    """Une page sans JSON-LD dégrade proprement : l'épreuve reste importable."""
    client = _FauxClient({"/results": (200, "<html><body>vide</body></html>")})

    assert raceresult._fetch_meta("1", "https://my.raceresult.com", client) == ("", None, "")


def test_fetch_config_interroge_la_bonne_route():
    client = _FauxClient({
        "/RRPublish/data/config": (200, _fixture("raceresult_config_rumilly.json")),
    })

    config = raceresult._fetch_config("393893", "https://my3.raceresult.com", client)

    assert config["key"] == "0123456789abcdef"
    assert config["contests"] == {"1": "Distance XS", "4": "Distance M"}
    assert "page=results" in client.appels[0]


def test_iter_list_specs_aplatit_les_listes_imbriquees():
    """Les listes RaceResult sont un arbre ; le `listname` est le chemin en `|`."""
    config = json.loads(_fixture("raceresult_config_rumilly.json"))

    assert raceresult._iter_list_specs(config) == [
        ("En ligne|Final", "0"),
        ("En ligne|Relais", "3"),
    ]


def test_iter_list_specs_accepte_une_liste_plate():
    config = {"lists": {"Résultats": {"Contest": 2}}}

    assert raceresult._iter_list_specs(config) == [("Résultats", "2")]
```

- [ ] **Step 3 : Lancer les tests pour vérifier qu'ils échouent**

```bash
uv run pytest tests/test_raceresult.py -k "meta or config or list_specs" -v
```

Attendu : ÉCHEC avec `AttributeError: module 'app.scrapers.raceresult' has no attribute '_fetch_meta'`.

- [ ] **Step 4 : Implémenter**

Dans `backend/app/scrapers/raceresult.py`, ajouter aux imports du haut :

```python
import json
from datetime import date as date_t

from bs4 import BeautifulSoup
```

Puis ajouter, après `_resolve_event_id` :

```python
def _json_ld_event(html: str) -> dict:
    """Premier bloc JSON-LD de type Event de la page, `{}` si aucun.

    Le bloc peut être un objet seul, une liste d'objets, ou un `@graph` — on
    balaie les trois formes plutôt que de parier sur une seule.
    """
    soup = BeautifulSoup(html, "lxml")
    for balise in soup.find_all("script", type="application/ld+json"):
        try:
            charge = json.loads(balise.string or "")
        except (ValueError, TypeError):
            continue
        candidats = charge if isinstance(charge, list) else [charge]
        if isinstance(charge, dict) and isinstance(charge.get("@graph"), list):
            candidats = charge["@graph"]
        for noeud in candidats:
            if isinstance(noeud, dict) and noeud.get("@type") == "Event":
                return noeud
    return {}


def _fetch_meta(
    event_id: str, base: str, client: httpx.Client
) -> tuple[str, "date_t | None", str]:
    """(nom d'épreuve, date, ville) depuis le JSON-LD de la page /results.

    C'est la **seule** source de la date : l'API `config` comme l'API `list` n'en
    portent aucune. Une page sans JSON-LD exploitable renvoie des valeurs vides
    plutôt que de lever : l'épreuve reste importable, le nom retombera sur
    `config["eventname"]` et la date sur `None`.
    """
    try:
        resp = client.get(f"{base}/{event_id}/results", headers=HEADERS)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.debug("RaceResult %s : page /results illisible (%s)", event_id, exc)
        return "", None, ""

    noeud = _json_ld_event(resp.text)
    if not noeud:
        return "", None, ""

    jour = None
    brut = str(noeud.get("startDate") or "")
    if brut:
        try:
            jour = date_t.fromisoformat(brut[:10])
        except ValueError:
            logger.debug("RaceResult %s : startDate illisible (%r)", event_id, brut)

    adresse = (noeud.get("location") or {}).get("address") or {}
    ville = str(adresse.get("addressLocality") or "")
    return str(noeud.get("name") or ""), jour, ville


def _fetch_config(event_id: str, base: str, client: httpx.Client) -> dict:
    """Config publique de l'épreuve : `key`, `contests`, `lists`, `splits`."""
    resp = client.get(
        f"{base}/{event_id}/RRPublish/data/config",
        params={"page": "results"},
        headers=HEADERS,
    )
    resp.raise_for_status()
    return resp.json()


# Clés qui marquent une feuille dans l'arbre `lists` (une liste réelle, pas un
# groupe intermédiaire).
_CLES_FEUILLE = ("Contest", "Name", "ID")


def _iter_list_specs(config: dict) -> list[tuple[str, str]]:
    """Listes exploitables : [(listname, indice de contest), …].

    `config["lists"]` est un arbre dont le chemin, joint par `|`, forme le
    `listname` attendu par l'API. On aplatit récursivement : une feuille est un
    nœud non-dict, ou un dict portant une clé de description (`Contest`,
    `Name`, `ID`). L'indice de contest n'est qu'un **indice** — il est vérifié
    empiriquement à l'appel (cf. `_contest_candidates`).
    """
    specs: list[tuple[str, str]] = []

    def descendre(noeud, chemin: list[str]) -> None:
        if not isinstance(noeud, dict) or any(c in noeud for c in _CLES_FEUILLE):
            indice = noeud.get("Contest") if isinstance(noeud, dict) else None
            specs.append(("|".join(chemin), "" if indice is None else str(indice)))
            return
        for cle, valeur in noeud.items():
            descendre(valeur, [*chemin, str(cle)])

    for cle, valeur in (config.get("lists") or {}).items():
        descendre(valeur, [str(cle)])
    return specs
```

- [ ] **Step 5 : Lancer les tests**

```bash
uv run pytest tests/test_raceresult.py -v
```

Attendu : PASS sur les 14 tests.

- [ ] **Step 6 : Lint et commit**

```bash
uv run ruff check .
git add app/scrapers/raceresult.py tests/test_raceresult.py \
        tests/fixtures/raceresult_page_meta.html \
        tests/fixtures/raceresult_config_rumilly.json
git commit -m "feat(scrapers): métadonnées JSON-LD et config RaceResult"
```

---

### Task 4 : Mapping des colonnes

> ⚠️ **Emplacement faux, algorithme juste (errata).** `DataFields` est à la
> **racine du payload**, pas sous `payload["list"]` (qui le porte à `null`).
> L'algorithme `col = DataFields.index(Field.Expression)` et le préfixe `BIB`/`ID`
> sont confirmés, et restent nécessaires : `DataFields` compte souvent plus
> d'entrées que `Fields` (20 vs 18, 22 vs 19). En revanche le vocabulaire de
> `_role` est trop étroit — voir §6 du sondage : enveloppe `if([STATUS]<>2;[X])`,
> suffixe `.p` minuscule, concaténations `X & iif(…)`, `LFNAME`, `TempsOuStatut`.


Le cœur du moteur. L'algorithme d'index est **autoritatif** (extrait de `RRPublish.js`, pas une heuristique) :

```js
i = {DataFields[e]: e};  Fields[e].DataCol = i[Fields[e].Expression]
```

L'index de colonne d'un champ vaut `DataFields.index(Field.Expression)`. `DataFields` préfixe toujours `BIB` et `ID`, qui n'ont pas d'entrée dans `Fields` — d'où le décalage que la position seule ne verrait pas.

Le rôle sémantique, lui, se lit sur l'expression **pelée** (sans `ucase(…)`, `OuStatut(…)`, `[…]`, `#`). Deux règles de sûreté tirées du terrain : une expression suffixée `.P` est un **rang**, jamais un temps ; et `#[ClassementCatégorie.p][AGEGROUP.NAMESHORT]` colle rang et catégorie dans une seule cellule (`"1.S4M"`).

**Files:**
- Modify: `backend/app/scrapers/raceresult.py`
- Modify: `backend/tests/test_raceresult.py`

**Interfaces:**
- Consumes: rien des tâches précédentes.
- Produces:
  - `_peel(expr: str) -> str` — expression normalisée (minuscule, sans accents ni enrobage)
  - `_clean_cell(brut) -> str`
  - `_split_rank_category(cell: str) -> tuple[int | None, str]`
  - `_map_columns(payload: dict) -> tuple[dict[str, int], list[tuple[str, int]], dict[str, int]]` → `(rôles, segments, extras)`. Rôles possibles : `bib`, `nom`, `club`, `categorie`, `sexe`, `temps`, `rang`, `rang_categorie`.

- [ ] **Step 1 : Créer la fixture de liste**

Créer `backend/tests/fixtures/raceresult_list_rumilly_m.json` :

```json
{
  "_provenance": "GET https://my3.raceresult.com/393893/RRPublish/data/list?key=…&listname=En%20ligne%7CFinal&contest=4&r=all — 2026-07-18. Tronquée à 4 lignes (2 finishers, 1 DNF, 1 DNS) sur 308/6/33.",
  "DataFields": [
    "BIB", "ID", "OuStatut([ClassementGénéral.P])", "DossardBis",
    "AfficherNom", "SexeMF", "#[ClassementCatégorie.p][AGEGROUP.NAMESHORT]",
    "ucase([CLUB])", "[Natation.OVERALL.P]", "[Natation]",
    "[Transition1.OVERALL.P]", "[Transition1]", "[Vélo.OVERALL.P]", "[Vélo]",
    "[Transition2.OVERALL.P]", "[Transition2]", "[Course.OVERALL.P] ", "[Course]",
    "TIME", "Arrivée.OVERALL.GapTop"
  ],
  "Fields": [
    {"Expression": "OuStatut([ClassementGénéral.P])", "Label": "Pl."},
    {"Expression": "DossardBis", "Label": "#"},
    {"Expression": "AfficherNom", "Label": "Nom"},
    {"Expression": "SexeMF", "Label": "M|F"},
    {"Expression": "#[ClassementCatégorie.p][AGEGROUP.NAMESHORT]", "Label": "Cat."},
    {"Expression": "ucase([CLUB])", "Label": "Club"},
    {"Expression": "[Natation.OVERALL.P]", "Label": ""},
    {"Expression": "[Natation]", "Label": "Nat."},
    {"Expression": "[Transition1.OVERALL.P]", "Label": ""},
    {"Expression": "[Transition1]", "Label": "T1"},
    {"Expression": "[Vélo.OVERALL.P]", "Label": ""},
    {"Expression": "[Vélo]", "Label": "Vélo"},
    {"Expression": "[Transition2.OVERALL.P]", "Label": ""},
    {"Expression": "[Transition2]", "Label": "T2"},
    {"Expression": "[Course.OVERALL.P] ", "Label": ""},
    {"Expression": "[Course]", "Label": "CAP"},
    {"Expression": "TIME", "Label": "Temps"},
    {"Expression": "Arrivée.OVERALL.GapTop", "Label": ""}
  ],
  "data": {
    "#1_Distance M": {
      "#1_": [
        ["79", "56", "2.", "79", "Alexis ROUX", "M", "1.S4M",
         "GRESIVAUDAN TRIATHLON", "2.", "20:04", "3.", "00:53", "2.", "1:05:49",
         "45.", "00:56", "3.", "34:14", "2:01:56", "+2:44"],
        ["112", "57", "3.", "112", "Jean DE LA TOUR", "M", "2.S4M",
         "TRIATHLON CLUB NANTAIS", "5.", "21:10", "8.", "01:02", "4.", "1:07:30",
         "12.", "00:51", "9.", "35:40", "2:06:13", "+7:01"]
      ],
      "#2_Abandons": [
        ["205", "58", "DNF", "205", "Sophie MARTIN", "F", "S3F",
         "ANNECY TRIATHLON", "", "22:31", "", "01:04", "", "", "", "", "", "",
         "", ""]
      ],
      "#3_Non Partants": [
        ["310", "59", "DNS", "310", "Paul BERNARD", "M", "V1M",
         "CHAMBERY TRIATHLON", "", "", "", "", "", "", "", "", "", "", "", ""]
      ]
    }
  }
}
```

- [ ] **Step 2 : Écrire les tests qui échouent**

Ajouter à `backend/tests/test_raceresult.py` :

```python
def _payload_rumilly() -> dict:
    return json.loads(_fixture("raceresult_list_rumilly_m.json"))


@pytest.mark.parametrize("expr,attendu", [
    ("OuStatut([ClassementGénéral.P])", "classementgeneral.p"),
    ("ucase([CLUB])", "club"),
    ("AfficherNom", "affichernom"),
    ("[Course.OVERALL.P] ", "course.overall.p"),
    ("TIME", "time"),
    ("#[ClassementCatégorie.p][AGEGROUP.NAMESHORT]", "classementcategorie.pagegroup.nameshort"),
])
def test_peel(expr, attendu):
    assert raceresult._peel(expr) == attendu


@pytest.mark.parametrize("brut,attendu", [
    ("  2.  ", "2."),
    ("[img:https://my.raceresult.com/flag.png]FRA", "FRA"),
    ('#79', "79"),
    (None, ""),
    (42, "42"),
])
def test_clean_cell(brut, attendu):
    assert raceresult._clean_cell(brut) == attendu


@pytest.mark.parametrize("cell,attendu", [
    ("1.S4M", (1, "S4M")),
    ("12.V1M", (12, "V1M")),
    ("S3F", (None, "S3F")),
    ("", (None, "")),
])
def test_split_rank_category(cell, attendu):
    assert raceresult._split_rank_category(cell) == attendu


def test_map_columns_utilise_l_index_de_datafields():
    """Le décalage BIB/ID rend la position dans `Fields` inutilisable telle quelle."""
    roles, segments, extras = raceresult._map_columns(_payload_rumilly())

    assert roles["bib"] == 0          # DataFields[0] est toujours BIB
    assert roles["rang"] == 2         # Fields[0], mais DataFields[2]
    assert roles["nom"] == 4
    assert roles["sexe"] == 5
    assert roles["rang_categorie"] == 6
    assert roles["club"] == 7
    assert roles["temps"] == 18


def test_map_columns_rejette_les_colonnes_de_rang_de_split():
    """`[Natation.OVERALL.P]` vaut "2." — c'est un rang, pas le temps de natation."""
    _roles, segments, _extras = raceresult._map_columns(_payload_rumilly())

    assert segments == [
        ("Nat.", 9), ("T1", 11), ("Vélo", 13), ("T2", 15), ("CAP", 17)
    ]
    indices_de_rang_de_split = {8, 10, 12, 14, 16}
    assert not indices_de_rang_de_split & {col for _label, col in segments}


def test_map_columns_range_les_champs_non_reconnus_en_extras():
    """Un champ inconnu n'est pas perdu : il partira dans `raw_data`."""
    _roles, _segments, extras = raceresult._map_columns(_payload_rumilly())

    assert extras["Arrivée.OVERALL.GapTop"] == 19
    assert extras["DossardBis"] == 3
```

- [ ] **Step 3 : Lancer les tests pour vérifier qu'ils échouent**

```bash
uv run pytest tests/test_raceresult.py -k "peel or clean_cell or rank_category or map_columns" -v
```

Attendu : ÉCHEC avec `AttributeError: module 'app.scrapers.raceresult' has no attribute '_peel'`.

- [ ] **Step 4 : Implémenter**

Dans `backend/app/scrapers/raceresult.py`, ajouter après `_iter_list_specs` :

```python
_ACCENTS = str.maketrans("àâäéèêëîïôöùûüçÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ", "aaaeeeeiioouuucAAAEEEEIIOOUUUC")

# Enrobages d'affichage posés par RaceResult autour de l'expression réelle.
_RE_ENROBAGE = re.compile(r"^(ucase|lcase|OuStatut|Statut|if)\s*\(", re.IGNORECASE)
# Décorations de cellule : `[img:https://…]` en préfixe, `#` de `"#" & [BIB]`.
_RE_IMG = re.compile(r"\[img:[^\]]*\]")


def _peel(expr: str) -> str:
    """Expression RaceResult ramenée à sa forme comparable.

    Pèle les enrobages d'affichage (`ucase(…)`, `OuStatut(…)`, `if(…;X;…)`), les
    crochets et le `#`, puis met en minuscules sans accents. `ucase([CLUB])` et
    `[Club]` convergent ainsi vers `club`, ce qui permet une table de motifs
    courte au lieu d'une énumération de variantes.
    """
    s = (expr or "").strip()
    while True:
        trouve = _RE_ENROBAGE.match(s)
        if not trouve or not s.endswith(")"):
            break
        s = s[trouve.end():-1].strip()
    # Une expression conditionnelle garde son premier terme utile.
    if ";" in s:
        s = max(s.split(";"), key=len).strip()
    s = s.replace("#", "").replace("[", "").replace("]", "")
    return s.translate(_ACCENTS).lower().strip()


def _clean_cell(brut) -> str:
    """Cellule débarrassée de ses décorations d'affichage."""
    if brut is None:
        return ""
    return _RE_IMG.sub("", str(brut)).strip().lstrip("#").strip()


_RE_RANG_CAT = re.compile(r"^(\d+)\.\s*(.*)$")


def _split_rank_category(cell: str) -> tuple[int | None, str]:
    """Sépare `"1.S4M"` en (rang catégorie, catégorie).

    L'expression `#[ClassementCatégorie.p][AGEGROUP.NAMESHORT]` colle les deux
    dans une seule colonne. Une cellule sans préfixe numérique est une catégorie
    nue (cas des non-finishers, qui n'ont pas de rang).
    """
    cell = _clean_cell(cell)
    trouve = _RE_RANG_CAT.match(cell)
    if trouve:
        return int(trouve.group(1)), trouve.group(2).strip()
    return None, cell


def _role(peeled: str) -> str:
    """Rôle sémantique d'une expression pelée, "" si non reconnu.

    Ordre des tests significatif : les rangs sont testés en premier, car une
    expression suffixée `.p` / `.overall.p` est **toujours** un rang, jamais un
    temps. Sans cette règle, `[Natation.OVERALL.P]` (« 2. ») passerait pour le
    temps de natation, qui vit dans la colonne suivante.
    """
    if "classementgeneral" in peeled:
        return "rang"
    if "agegroup" in peeled or "classementcategorie" in peeled:
        return "rang_categorie"
    if peeled.endswith(".p"):
        return "rang_de_split"  # colonne à écarter
    if any(motif in peeled for motif in ("affichernom", "nomrelais", "nomequipe")):
        return "nom"
    if "club" in peeled:
        return "club"
    if peeled in ("sexemf", "sex", "sexe", "gender"):
        return "sexe"
    if peeled in ("time", "tempstotal", "tempscorrige", "finish", "arrivee"):
        return "temps"
    return ""


def _map_columns(
    payload: dict,
) -> tuple[dict[str, int], list[tuple[str, int]], dict[str, int]]:
    """(rôles, segments, extras) — l'index de chaque colonne du payload.

    Étage 1, l'index : `col = DataFields.index(Field.Expression)`, l'algorithme
    exact de `RRPublish.js`. `DataFields` préfixe toujours `BIB` et `ID`, qui
    n'ont pas d'entrée dans `Fields` — la position dans `Fields` est donc
    décalée et inutilisable telle quelle. Le dossard, lui, vient de
    `DataFields.index("BIB")` et ne passe par aucune heuristique.

    Étage 2, le rôle : cf. `_role`. Un champ dont l'expression est un token nu
    entre crochets (`[Natation]`) et sans suffixe de rang est un **segment**,
    étiqueté par son `Label`. Tout le reste part en extras → `raw_data`.
    """
    data_fields = [str(e) for e in payload.get("DataFields") or []]
    index_par_expr = {expr: i for i, expr in enumerate(data_fields)}

    roles: dict[str, int] = {}
    segments: list[tuple[str, int]] = []
    extras: dict[str, int] = {}

    if "BIB" in index_par_expr:
        roles["bib"] = index_par_expr["BIB"]

    for champ in payload.get("Fields") or []:
        expr = str(champ.get("Expression") or "")
        col = index_par_expr.get(expr)
        if col is None:
            logger.debug("RaceResult : champ sans colonne de données (%r)", expr)
            continue
        peeled = _peel(expr)
        role = _role(peeled)
        if role == "rang_de_split":
            continue
        if role:
            roles.setdefault(role, col)
            continue
        label = str(champ.get("Label") or "").strip()
        # Segment : token nu entre crochets, donc sans point de qualification.
        if "[" in expr and "." not in peeled and label:
            segments.append((label, col))
        else:
            extras[expr] = col

    # La catégorie partage la colonne du rang de catégorie (cellule « 1.S4M »).
    if "rang_categorie" in roles:
        roles.setdefault("categorie", roles["rang_categorie"])
    return roles, segments, extras
```

- [ ] **Step 5 : Lancer les tests**

```bash
uv run pytest tests/test_raceresult.py -v
```

Attendu : PASS sur les 27 tests.

- [ ] **Step 6 : Lint et commit**

```bash
uv run ruff check .
git add app/scrapers/raceresult.py tests/test_raceresult.py \
        tests/fixtures/raceresult_list_rumilly_m.json
git commit -m "feat(scrapers): mapping des colonnes RaceResult par DataFields.index"
```

---

### Task 5 : Groupes, statut et construction d'un `ScrapedResult`

> ⚠️ **Prémisse invalidée (errata).** `data` n'a pas deux niveaux fixes : la
> profondeur varie (plat, 1 ou 2 niveaux), parfois **au sein d'une même épreuve**.
> Et le libellé de groupe n'est pas toujours un statut — 406212 groupe par
> `#1_Masculin` / `#1_Féminin`. Deux règles : descendre récursivement jusqu'aux
> feuilles, et n'interpréter le libellé que par **liste blanche** de jetons connus
> (dont `Disqualifiés`, absent du plan) — tout libellé inconnu est un groupement
> neutre, pas un abandon. Voir §7 du sondage.


`data` est un dict imbriqué à deux niveaux : le groupe de niveau 1 identifie le **contest**, celui de niveau 2 le **statut**. Deux signaux concordants alimentent `derive_status_from_label`, le groupe primant sur la cellule.

Une `Course` par contest, via le nom qualifié `"Triathlon de Rumilly - Distance M"` : c'est ce qui évite les collisions de dossards de l'issue #21 (Rumilly porte un `1245` en Distance XS et un `280` en Distance M). On factorise pour cela `_qualify_event_name` de `wiclax.py` dans `utils.py`.

**Files:**
- Modify: `backend/app/scrapers/utils.py`
- Modify: `backend/app/scrapers/wiclax.py:144-154`
- Modify: `backend/app/scrapers/raceresult.py`
- Modify: `backend/tests/test_raceresult.py`
- Modify: `backend/tests/test_scrapers_utils.py`
- Modify: `backend/tests/test_wiclax.py`

**Interfaces:**
- Consumes: `_map_columns`, `_clean_cell`, `_split_rank_category` (Task 4).
- Produces:
  - `utils.qualify_event_name(event_name: str, qualifiant: str) -> str`
  - `raceresult._iter_groups(data: dict) -> list[tuple[str, str, list]]` → `(libellé contest, libellé statut, lignes)`
  - `raceresult._strip_group_prefix(cle: str) -> str`
  - `raceresult._build_result(ligne, roles, segments, extras, *, source_url, event_name, event_date, contest_label, status_label) -> ScrapedResult`
  - `utils._STATUS_TOKENS` enrichi des formes plurielles `abandons` / `nonpartants`

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à `backend/tests/test_raceresult.py` :

```python
from app.scrapers.base import STATUS_DNF, STATUS_DNS


@pytest.mark.parametrize("cle,attendu", [
    ("#1_Distance M", "Distance M"),
    ("#2_Abandons", "Abandons"),
    ("#1_", ""),
    ("Distance M", "Distance M"),
])
def test_strip_group_prefix(cle, attendu):
    assert raceresult._strip_group_prefix(cle) == attendu


def test_iter_groups_expose_contest_et_statut():
    groupes = raceresult._iter_groups(_payload_rumilly()["data"])

    assert [(c, s, len(lignes)) for c, s, lignes in groupes] == [
        ("Distance M", "", 2),
        ("Distance M", "Abandons", 1),
        ("Distance M", "Non Partants", 1),
    ]


def test_iter_groups_supporte_un_seul_niveau():
    """Certains payloads n'ont pas de sous-groupe de statut."""
    data = {"#1_Distance S": [["1", "2", "1.", "1"]]}

    assert raceresult._iter_groups(data) == [("Distance S", "", [["1", "2", "1.", "1"]])]


def _construire(ligne, contest="Distance M", statut=""):
    payload = _payload_rumilly()
    roles, segments, extras = raceresult._map_columns(payload)
    return raceresult._build_result(
        ligne, roles, segments, extras,
        source_url="https://my3.raceresult.com/393893/results",
        event_name="Triathlon de Rumilly",
        event_date=date(2026, 6, 18),
        contest_label=contest,
        status_label=statut,
    )


def test_build_result_finisher():
    ligne = _payload_rumilly()["data"]["#1_Distance M"]["#1_"][0]

    r = _construire(ligne)

    assert r.provider == "raceresult"
    assert r.bib_number == "79"
    assert r.athlete_name == "ROUX"
    assert r.athlete_firstname == "Alexis"
    assert r.gender == "M"
    assert r.club == "GRESIVAUDAN TRIATHLON"
    assert r.category == "S4M"
    assert r.rank_category == 1
    assert r.rank_overall == 2
    assert r.total_time == "02:01:56"
    assert r.status == "finisher"
    assert r.event_name == "Triathlon de Rumilly - Distance M"
    assert r.event_type == "triathlon-m"
    assert r.event_date == date(2026, 6, 18)


def test_build_result_nom_compose_en_prenom_nom():
    """`Jean DE LA TOUR` — le nom est le bloc majuscule entier (cf. Task 1)."""
    ligne = _payload_rumilly()["data"]["#1_Distance M"]["#1_"][1]

    r = _construire(ligne)

    assert (r.athlete_name, r.athlete_firstname) == ("DE LA TOUR", "Jean")


def test_build_result_segments_ordonnes_et_etiquetes():
    """Liste ordonnée, pas les 5 slots positionnels : le plafond de 5 est levé."""
    ligne = _payload_rumilly()["data"]["#1_Distance M"]["#1_"][0]

    r = _construire(ligne)

    assert r.segments == [
        ("Nat.", "00:20:04"),
        ("T1", "00:00:53"),
        ("Vélo", "01:05:49"),
        ("T2", "00:00:56"),
        ("CAP", "00:34:14"),
    ]


def test_build_result_extras_dans_raw_data():
    ligne = _payload_rumilly()["data"]["#1_Distance M"]["#1_"][0]

    r = _construire(ligne)

    assert r.raw_data["Arrivée.OVERALL.GapTop"] == "+2:44"


def test_build_result_dnf_depuis_le_groupe():
    ligne = _payload_rumilly()["data"]["#1_Distance M"]["#2_Abandons"][0]

    r = _construire(ligne, statut="Abandons")

    assert r.status == STATUS_DNF
    assert r.total_time == ""
    assert (r.rank_overall, r.rank_category, r.rank_gender) == (None, None, None)


def test_build_result_dns_depuis_le_groupe():
    ligne = _payload_rumilly()["data"]["#1_Distance M"]["#3_Non Partants"][0]

    r = _construire(ligne, statut="Non Partants")

    assert r.status == STATUS_DNS
    assert r.total_time == ""


def test_build_result_statut_depuis_la_cellule_de_rang():
    """Sans groupe de statut, la cellule de rang vaut littéralement « DNF »."""
    ligne = _payload_rumilly()["data"]["#1_Distance M"]["#2_Abandons"][0]

    r = _construire(ligne, statut="")

    assert r.status == STATUS_DNF


def test_build_result_statut_du_groupe_sans_cellule():
    """Le groupe suffit : une cellule de rang vide ne dégrade pas le statut.

    Sans ce cas, `test_build_result_dnf_depuis_le_groupe` serait un faux vert —
    il passerait par le repli sur la cellule sans jamais exercer le groupe.
    """
    ligne = list(_payload_rumilly()["data"]["#1_Distance M"]["#2_Abandons"][0])
    ligne[2] = ""  # colonne de rang vidée

    assert _construire(ligne, statut="Abandons").status == STATUS_DNF
    assert _construire(ligne, statut="Non Partants").status == STATUS_DNS


def test_build_result_marque_le_relais():
    ligne = _payload_rumilly()["data"]["#1_Distance M"]["#1_"][0]

    r = _construire(ligne, contest="Relais M")

    assert r.is_relay is True
```

Ajouter aussi à `backend/tests/test_wiclax.py` (non-régression de la factorisation) :

```python
def test_qualify_event_name_factorise_dans_utils():
    from app.scrapers.utils import qualify_event_name
    from app.scrapers.wiclax import _qualify_event_name

    assert _qualify_event_name("Triathlon de Vertou 2026", "S-Open Femmes") == (
        "Triathlon de Vertou 2026 - S-Open Femmes"
    )
    # Qualifiant déjà présent : pas de doublon.
    assert _qualify_event_name("Triathlon M", "Triathlon M") == "Triathlon M"
    assert qualify_event_name("Triathlon M", "") == "Triathlon M"
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

```bash
uv run pytest tests/test_raceresult.py tests/test_wiclax.py -k "group or build_result or qualify" -v
```

Attendu : ÉCHEC avec `AttributeError: module 'app.scrapers.raceresult' has no attribute '_strip_group_prefix'` et `ImportError: cannot import name 'qualify_event_name'`.

- [ ] **Step 3 : Reconnaître les libellés de statut au pluriel**

Les clés de groupe RaceResult sont au pluriel (`Abandons`, `Non Partants`) alors
que `_STATUS_TOKENS` ne connaît que le singulier. Ajouter les deux entrées dans
`backend/app/scrapers/utils.py`, dans le dict `_STATUS_TOKENS` :

```python
    # Abandon (Did Not Finish)
    "dnf": STATUS_DNF,
    "abd": STATUS_DNF,
    "abandon": STATUS_DNF,
    # Pluriel : RaceResult nomme ses groupes de statut « Abandons ».
    "abandons": STATUS_DNF,
    "ab": STATUS_DNF,
    # Non-partant (Did Not Start)
    "dns": STATUS_DNS,
    "nonpartant": STATUS_DNS,
    # Pluriel : groupe RaceResult « Non Partants ».
    "nonpartants": STATUS_DNS,
    "np": STATUS_DNS,
```

Ajouter les cas correspondants au test paramétré existant
`test_derive_status_from_label_recognized` dans
`backend/tests/test_scrapers_utils.py` :

```python
    # Formes plurielles des groupes RaceResult
    ("Abandons", "DNF"),
    ("Non Partants", "DNS"),
```

- [ ] **Step 4 : Factoriser `qualify_event_name` dans `utils.py`**

Ajouter à la fin de `backend/app/scrapers/utils.py` :

```python
def qualify_event_name(event_name: str, qualifiant: str) -> str:
    """Qualifie un nom d'épreuve par son parcours / contest.

    « Triathlon de Rumilly » + « Distance M » → « Triathlon de Rumilly - Distance M ».
    Chaque parcours est une épreuve distincte (classement propre, dossards
    réutilisés d'un parcours à l'autre) : sans qualification, plusieurs parcours
    de même type fusionnent en une seule Course et leurs dossards entrent en
    collision (issue #21 : participants manquants, rangs dupliqués). Un
    qualifiant déjà présent dans le nom n'est pas ré-ajouté.
    """
    qualifiant = (qualifiant or "").strip()
    if not qualifiant or qualifiant.lower() in (event_name or "").lower():
        return event_name
    return f"{event_name} - {qualifiant}"
```

Puis, dans `backend/app/scrapers/wiclax.py`, remplacer la fonction `_qualify_event_name` (lignes 144-154) par une délégation :

```python
def _qualify_event_name(event_name: str, parcours: str) -> str:
    """Qualifie le nom d'épreuve par le parcours ChronoSmetron.

    Logique factorisée dans `utils.qualify_event_name`, partagée avec RaceResult
    (qui qualifie par contest). Alias conservé : il est importé par les tests.
    """
    return qualify_event_name(event_name, parcours)
```

Et ajouter `qualify_event_name` à l'import `from .utils import (…)` en tête de `wiclax.py` :

```python
from .utils import (
    derive_status_from_label,
    normalize_rank,
    normalize_time,
    parse_fr_date,
    qualify_event_name,
    split_athlete_name,
)
```

- [ ] **Step 5 : Implémenter les groupes et la construction**

Dans `backend/app/scrapers/raceresult.py`, compléter les imports du haut :

```python
from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, ScrapedResult
from .classify import classify_event_type
from .utils import (
    derive_status_from_label,
    normalize_rank,
    normalize_time,
    qualify_event_name,
    split_athlete_name,
)
```

Puis ajouter après `_map_columns` :

```python
_RE_PREFIXE_GROUPE = re.compile(r"^#\d+_")


def _strip_group_prefix(cle: str) -> str:
    """Retire le préfixe d'ordonnancement d'une clé de groupe (`#1_Distance M`)."""
    return _RE_PREFIXE_GROUPE.sub("", str(cle)).strip()


def _iter_groups(data: dict) -> list[tuple[str, str, list]]:
    """[(libellé contest, libellé statut, lignes), …] depuis le dict `data`.

    `data` est imbriqué à deux niveaux : le groupe de niveau 1 identifie le
    **contest** (`#1_Distance M`), celui de niveau 2 le **statut**
    (`#1_` = finishers, `#2_Abandons` = DNF, `#3_Non Partants` = DNS). Certains
    payloads n'ont qu'un niveau ; les deux formes sont acceptées.
    """
    groupes: list[tuple[str, str, list]] = []
    for cle_contest, contenu in (data or {}).items():
        contest = _strip_group_prefix(cle_contest)
        if isinstance(contenu, dict):
            for cle_statut, lignes in contenu.items():
                if isinstance(lignes, list):
                    groupes.append((contest, _strip_group_prefix(cle_statut), lignes))
        elif isinstance(contenu, list):
            groupes.append((contest, "", contenu))
    return groupes


_NON_FINISHERS = (STATUS_DNF, STATUS_DNS, STATUS_DSQ)


def _build_result(
    ligne: list,
    roles: dict[str, int],
    segments: list[tuple[str, int]],
    extras: dict[str, int],
    *,
    source_url: str,
    event_name: str,
    event_date,
    contest_label: str,
    status_label: str,
) -> ScrapedResult:
    """Construit un `ScrapedResult` depuis une ligne de données RaceResult."""

    def cellule(role: str) -> str:
        col = roles.get(role)
        if col is None or col >= len(ligne):
            return ""
        return _clean_cell(ligne[col])

    nom_qualifie = qualify_event_name(event_name, contest_label)
    r = ScrapedResult(
        source_url=source_url,
        provider="raceresult",
        bib_number=cellule("bib"),
        event_name=nom_qualifie,
        event_date=event_date,
        event_type=classify_event_type(nom_qualifie),
    )

    nom, prenom = split_athlete_name(cellule("nom"))
    r.athlete_name, r.athlete_firstname = nom, prenom
    r.club = cellule("club")
    r.gender = cellule("sexe")
    r.rank_category, r.category = _split_rank_category(cellule("categorie"))
    r.total_time = normalize_time(cellule("temps"))
    r.is_relay = any(
        mot in contest_label.lower() for mot in ("relais", "relay", "equipe", "équipe")
    )

    # La cellule de rang porte le rang **ou** le statut (`OuStatut(…)`).
    cellule_rang = cellule("rang")
    r.rank_overall = normalize_rank(cellule_rang)

    # Deux signaux concordants, le groupe primant sur la cellule : un groupe
    # « Abandons » qualifie toute la tranche, la cellule ne renseigne que les
    # payloads sans sous-groupe de statut.
    r.status = (
        derive_status_from_label(status_label)
        or derive_status_from_label(cellule_rang)
        or ""
    )

    r.segments = [
        (label, normalize_time(_clean_cell(ligne[col])))
        for label, col in segments
        if col < len(ligne) and _clean_cell(ligne[col])
    ] or None

    r.raw_data = {
        expr: _clean_cell(ligne[col]) for expr, col in extras.items() if col < len(ligne)
    }

    # Nettoyage systématique de la maison (cf. wiclax.py) : un non-finisher n'a
    # ni temps total ni rang, quoi qu'annonce le payload.
    if r.status in _NON_FINISHERS:
        r.total_time = ""
        r.rank_overall = r.rank_category = r.rank_gender = None
    elif r.total_time:
        r.status = r.status or "finisher"

    return r
```

- [ ] **Step 6 : Lancer les tests**

```bash
uv run pytest tests/test_raceresult.py tests/test_wiclax.py tests/test_scrapers_utils.py -v
```

Attendu : PASS. En particulier `test_build_result_statut_du_groupe_sans_cellule` (le groupe seul suffit), `test_build_result_dnf_depuis_le_groupe` (`status == "DNF"`, temps vidé, rangs à `None`) et `test_build_result_segments_ordonnes_et_etiquetes` (5 segments étiquetés, aucun rang de split).

- [ ] **Step 7 : Lint et commit**

```bash
uv run ruff check .
git add app/scrapers/raceresult.py app/scrapers/utils.py app/scrapers/wiclax.py \
        tests/test_raceresult.py tests/test_wiclax.py tests/test_scrapers_utils.py
git commit -m "feat(scrapers): statut par groupe et construction des résultats RaceResult"
```

---

### Task 6 : Pipeline complet — contests empiriques, fusion, erreurs

> ⚠️ **Prémisse invalidée (errata).** Sur la route canonique, `TabConfig.Lists`
> donne le contest **explicitement** pour chaque liste : il n'y a rien à résoudre
> empiriquement. Toute cette tâche est à refonder — sélection par
> `Mode != "hidden"`, itération directe sur les couples (liste, contest) annoncés.
> Ce qui **reste nécessaire** : la fusion et l'arbitrage par richesse, car une même
> épreuve peut exposer plusieurs listes sur un même contest (392745 : 6 listes sur
> le contest 1 ; 409130 : 3 listes en `Contest="0"`).

Le couple (liste, contest) doit être résolu **empiriquement** : `contest=0` n'est pas universel (sur Rumilly il renvoie 404 sur toutes les listes, il faut interroger contest par contest), et certaines listes annoncées en config répondent 404 en dur (Roanne n'expose qu'une liste morte). Un 404 est journalisé en `debug` et n'interrompt rien.

Les listes exploitables sont toutes balayées puis **fusionnées** : une liste « Individuel » et une liste « Relais » se complètent au lieu de s'écraser.

**Files:**
- Modify: `backend/app/scrapers/raceresult.py`
- Modify: `backend/tests/test_raceresult.py`

**Interfaces:**
- Consumes: tous les helpers des Tasks 2 à 5.
- Produces:
  - `_contest_candidates(indice: str, contests: dict) -> list[str]`
  - `_fetch_list(event_id, base, key, listname, contest, client) -> dict | None`
  - `_richness(r: ScrapedResult) -> int`
  - `scrape_event_all(url: str) -> list[ScrapedResult]` (implémentation réelle)

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à `backend/tests/test_raceresult.py` :

```python
def test_contest_candidates_essaie_l_indice_puis_zero_puis_chaque_contest():
    assert raceresult._contest_candidates("4", {"1": "XS", "4": "M"}) == ["4", "0", "1"]
    # Indice nul ou absent : `0` en tête, puis chaque contest déclaré.
    assert raceresult._contest_candidates("0", {"1": "XS", "4": "M"}) == ["0", "1", "4"]
    assert raceresult._contest_candidates("", {"1": "XS"}) == ["0", "1"]


def test_fetch_list_renvoie_none_sur_404():
    client = _FauxClient({"/data/list": (404, "")})

    assert raceresult._fetch_list(
        "393893", "https://my3.raceresult.com", "k", "En ligne|Final", "0", client
    ) is None


def test_fetch_list_renvoie_none_sur_payload_sans_data():
    client = _FauxClient({"/data/list": (200, '{"DataFields": [], "data": {}}')})

    assert raceresult._fetch_list(
        "393893", "https://my3.raceresult.com", "k", "L", "0", client
    ) is None


def _brancher(monkeypatch, payloads_par_contest: dict[str, dict | None]):
    """Monkeypatche les helpers réseau ; `_fetch_list` répond selon le contest."""
    monkeypatch.setattr(raceresult, "_resolve_event_id", lambda url, client: "393893")
    monkeypatch.setattr(
        raceresult, "_fetch_meta",
        lambda eid, base, client: ("Triathlon de Rumilly", date(2026, 6, 18), "RUMILLY"),
    )
    monkeypatch.setattr(
        raceresult, "_fetch_config",
        lambda eid, base, client: json.loads(_fixture("raceresult_config_rumilly.json")),
    )
    essais: list[str] = []

    def faux_fetch_list(eid, base, key, listname, contest, client):
        essais.append(contest)
        return payloads_par_contest.get(contest)

    monkeypatch.setattr(raceresult, "_fetch_list", faux_fetch_list)
    return essais


def test_scrape_event_all_resout_le_contest_empiriquement(monkeypatch):
    """404 sur contest=0, succès sur contest=1 : le balayage ne s'arrête pas au premier échec."""
    essais = _brancher(monkeypatch, {"1": _payload_rumilly()})

    resultats = raceresult.scrape_event_all("https://my3.raceresult.com/393893/results")

    assert essais[:2] == ["0", "1"], f"ordre d'essai inattendu : {essais}"
    assert len(resultats) == 4
    assert {r.bib_number for r in resultats} == {"79", "112", "205", "310"}


def test_scrape_event_all_fusionne_sans_doublon(monkeypatch):
    """Deux listes livrant la même tranche : un participant, pas deux."""
    _brancher(monkeypatch, {"0": _payload_rumilly(), "3": _payload_rumilly()})

    resultats = raceresult.scrape_event_all("https://my3.raceresult.com/393893/results")

    assert len(resultats) == 4


def test_scrape_event_all_retient_la_ligne_la_plus_riche(monkeypatch):
    """Sur clé (contest, dossard) identique, la ligne la mieux remplie gagne."""
    pauvre = _payload_rumilly()
    pauvre["data"] = {"#1_Distance M": {"#1_": [
        ["79", "56", "2.", "79", "Alexis ROUX", "", "", "", "", "", "", "", "",
         "", "", "", "", "", "2:01:56", ""]
    ]}}
    riche = _payload_rumilly()
    riche["data"] = {"#1_Distance M": {"#1_": [
        riche["data"]["#1_Distance M"]["#1_"][0]
    ]}}
    # `En ligne|Final` (Contest 0) sert la ligne pauvre, `En ligne|Relais` (3) la riche.
    _brancher(monkeypatch, {"0": pauvre, "3": riche})

    resultats = raceresult.scrape_event_all("https://my3.raceresult.com/393893/results")

    assert len(resultats) == 1
    assert resultats[0].club == "GRESIVAUDAN TRIATHLON"


def test_scrape_event_all_sans_liste_exploitable_leve(monkeypatch):
    """Cas Roanne : config valide, toutes les listes en 404 → erreur messagée."""
    _brancher(monkeypatch, {})

    with pytest.raises(ValueError) as exc:
        raceresult.scrape_event_all("https://my3.raceresult.com/393893/results")

    assert "393893" in str(exc.value)
    assert "En ligne|Final" in str(exc.value)


def test_scrape_event_all_qualifie_par_contest(monkeypatch):
    """Une Course par contest : le nom qualifié évite les collisions de dossards (#21)."""
    _brancher(monkeypatch, {"0": _payload_rumilly()})

    resultats = raceresult.scrape_event_all("https://my3.raceresult.com/393893/results")

    assert {r.event_name for r in resultats} == {"Triathlon de Rumilly - Distance M"}
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

```bash
uv run pytest tests/test_raceresult.py -k "contest_candidates or fetch_list or scrape_event_all" -v
```

Attendu : ÉCHEC — `AttributeError: … has no attribute '_contest_candidates'`, puis `NotImplementedError` sur les tests `scrape_event_all`.

- [ ] **Step 3 : Implémenter le pipeline**

Dans `backend/app/scrapers/raceresult.py`, remplacer le stub `scrape_event_all` par :

```python
def _contest_candidates(indice: str, contests: dict) -> list[str]:
    """Contests à essayer pour une liste, dans l'ordre le plus probable.

    `contest=0` (« tous ») n'est pas universel : sur certaines épreuves il
    répond 404 sur toutes les listes et il faut interroger contest par contest,
    chacun livrant son propre payload. On essaie donc l'indice annoncé par la
    config s'il est significatif, puis `0`, puis chaque contest déclaré.
    """
    candidats: list[str] = []
    if indice and indice != "0":
        candidats.append(indice)
    candidats.append("0")
    candidats.extend(str(c) for c in (contests or {}))
    vus: set[str] = set()
    return [c for c in candidats if not (c in vus or vus.add(c))]


def _fetch_list(
    event_id: str,
    base: str,
    key: str,
    listname: str,
    contest: str,
    client: httpx.Client,
) -> dict | None:
    """Payload d'une liste pour un contest donné, `None` si indisponible.

    La route répond **301** vers `/{eventId}/results/list` : le client doit être
    ouvert avec `follow_redirects=True`, sinon la réponse est vide. Un 404 (liste
    non servie pour ce contest, ou liste morte) est journalisé en `debug` et
    renvoie `None` — le balayage continue.
    """
    resp = client.get(
        f"{base}/{event_id}/RRPublish/data/list",
        params={
            "key": key,
            "listname": listname,
            "page": "results",
            "contest": contest,
            "r": "all",
        },
        headers=HEADERS,
    )
    if resp.status_code == 404:
        logger.debug(
            "RaceResult %s : liste %r absente pour contest=%s", event_id, listname, contest
        )
        return None
    resp.raise_for_status()
    try:
        payload = resp.json()
    except ValueError:
        logger.debug("RaceResult %s : liste %r non JSON", event_id, listname)
        return None
    if not isinstance(payload, dict) or not payload.get("data"):
        return None
    return payload


def _richness(r: ScrapedResult) -> int:
    """Nombre de champs renseignés — arbitre les doublons entre listes."""
    champs = (
        r.athlete_name, r.athlete_firstname, r.club, r.category, r.gender, r.total_time
    )
    return sum(1 for c in champs if c) + len(r.segments or []) + len(r.raw_data)


def scrape_event_all(url: str) -> list[ScrapedResult]:
    """Importe tous les participants d'une épreuve RaceResult.

    Balaie **toutes** les listes exploitables et fusionne : une liste
    « Individuel » et une liste « Relais » se complètent au lieu de s'écraser.
    Borne réseau : `len(lists) + len(contests)` requêtes au pire, ~5 en pratique.
    """
    base = _api_base(url)
    with httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS) as client:
        event_id = _resolve_event_id(url, client)
        config = _fetch_config(event_id, base, client)
        key = str(config.get("key") or "")
        contests = config.get("contests") or {}
        nom_meta, jour, _ville = _fetch_meta(event_id, base, client)
        event_name = nom_meta or str(config.get("eventname") or "")

        specs = _iter_list_specs(config)
        # Clé de fusion (contest, dossard) : deux contests peuvent porter le même
        # dossard, c'est précisément le cas que la qualification par contest règle.
        fusion: dict[tuple[str, str], ScrapedResult] = {}
        for listname, indice in specs:
            for contest in _contest_candidates(indice, contests):
                payload = _fetch_list(event_id, base, key, listname, contest, client)
                if payload is None:
                    continue
                roles, segments, extras = _map_columns(payload)
                for contest_label, status_label, lignes in _iter_groups(payload["data"]):
                    # Le nom de contest vient de la clé de groupe, avec repli sur
                    # la table `contests` de la config.
                    libelle = contest_label or str(contests.get(contest) or "")
                    for ligne in lignes:
                        r = _build_result(
                            ligne, roles, segments, extras,
                            source_url=url,
                            event_name=event_name,
                            event_date=jour,
                            contest_label=libelle,
                            status_label=status_label,
                        )
                        if not r.bib_number:
                            continue
                        cle = (libelle, r.bib_number)
                        ancien = fusion.get(cle)
                        if ancien is None or _richness(r) > _richness(ancien):
                            fusion[cle] = r
                break  # une liste servie : on ne tente pas ses autres contests

    if not fusion:
        essayees = ", ".join(nom for nom, _ in specs) or "aucune liste déclarée"
        raise ValueError(
            f"Épreuve RaceResult {event_id} : aucune liste exploitable "
            f"(listes essayées : {essayees})."
        )
    return list(fusion.values())
```

- [ ] **Step 4 : Lancer les tests**

```bash
uv run pytest tests/test_raceresult.py -v
```

Attendu : PASS sur les 40 tests.

- [ ] **Step 5 : Lancer la suite unitaire complète**

```bash
uv run pytest -m "not integration" -q
```

Attendu : tous les tests passent, aucun échec ni erreur.

- [ ] **Step 6 : Lint et commit**

```bash
uv run ruff check .
git add app/scrapers/raceresult.py tests/test_raceresult.py
git commit -m "feat(scrapers): pipeline RaceResult — contests empiriques et fusion des listes"
```

---

### Task 7 : Test d'intégration réel et documentation

> ⚠️ **Couverture insuffisante (errata).** Une seule épreuve, sur une route non
> générale : aucun des cinq défauts bloquants de la revue finale ne pouvait être
> attrapé. Le panel de re-sondage (9 épreuves, 3 façades) est listé en tête du
> sondage ; `LIVE_URLS` doit inclure au minimum une épreuve espace-competition et
> une chronoconsult. La fixture `chronoconsult_result_page.html` teste la
> mauvaise syntaxe (identifiant nu au lieu de quoté) — voir §8.


Les tests paramétrés de `test_integration_scrapers.py` prennent automatiquement toute entrée ajoutée à `LIVE_URLS`. C'est le seul endroit où le moteur touche le réseau réel, et le seul qui valide que les fixtures réduites n'ont pas dérivé de la vraie API.

**Files:**
- Modify: `backend/tests/test_integration_scrapers.py:22-34`
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: `registry.detect_provider`, `registry.scrape_event_all` (Task 2 et 6).
- Produces: rien de consommé par une tâche ultérieure.

- [ ] **Step 1 : Ajouter l'URL live**

Dans `backend/tests/test_integration_scrapers.py`, ajouter l'entrée au dict `LIVE_URLS` :

```python
LIVE_URLS = {
    "klikego": "https://www.klikego.com/resultats/triathlon-de-vierzon-2026/1674523163798-4",
    "breizhchrono": (
        "https://resultats.breizhchrono.com/resultats-courses/"
        "triathlon-de-la-cote-de-granit-rose-tregastel-2026-1295405190290-19/triathlon-m"
    ),
    "wiclax": "https://chronosmetron.wiclax-results.com/Triathlon%20de%20la%20Roche%202026/",
    "timepulse": "https://www.timepulse.fr/epreuves/resultats/live/3232",
    "prolivesport": "https://www.prolivesport.fr/result/1082/6",
    "sportinnovation": "https://sportinnovation.fr/Evenements/Resultats/7031",
    # Triathlon de Rumilly 2026 : 4 contests, dossards en collision d'un contest
    # à l'autre — l'épreuve qui a servi au sondage d'API du 2026-07-18.
    "raceresult": "https://my3.raceresult.com/393893/results",
}
```

- [ ] **Step 2 : Ajouter un test d'intégration ciblé sur les DNF/DNS**

Ajouter à la fin de `backend/tests/test_integration_scrapers.py` :

```python
@pytest.mark.integration
def test_raceresult_contests_et_non_finishers():
    """RaceResult : une Course par contest, non-finishers statués et purgés."""
    results = registry.scrape_event_all(LIVE_URLS["raceresult"])
    assert results, "raceresult : aucun participant renvoyé"

    # Plusieurs contests → plusieurs noms d'épreuve qualifiés.
    assert len({r.event_name for r in results}) >= 2, (
        f"raceresult : un seul contest vu ({ {r.event_name for r in results} })"
    )
    statuses = {r.status for r in results}
    assert "finisher" in statuses, f"raceresult : aucun finisher (vus : {statuses})"
    for r in results:
        if r.status not in ("", "finisher"):
            assert not r.total_time, f"{r.status} avec un temps total : {r.total_time}"
            assert r.rank_overall is None, f"{r.status} avec un rang : {r.rank_overall}"
    # Segments étiquetés plutôt que les 5 slots positionnels.
    assert any(r.segments for r in results), "raceresult : aucun segment"
```

- [ ] **Step 3 : Lancer les tests d'intégration**

```bash
uv run pytest -m integration -k raceresult -v
```

Attendu : PASS sur `test_detection[raceresult-…]`, `test_scrape_event_all_live[raceresult-…]` et `test_raceresult_contests_et_non_finishers`.

En cas d'échec, la cause la plus probable est un écart entre les fixtures réduites et le payload réel (forme de `lists`, clés de groupe). Utiliser `superpowers:systematic-debugging`, corriger le module **et** réaligner la fixture concernée sur le payload observé — une fixture qui ment est pire qu'une absence de test.

- [ ] **Step 4 : Documenter le fournisseur**

Dans `AGENTS.md`, section « Fournisseurs supportés », remplacer le paragraphe existant par :

```markdown
## Fournisseurs supportés

Klikego, Breizh Chrono, TimePulse, Wiclax/G-Live (individuel + épreuve complète),
ProLiveSport, Sportinnovation, RaceResult.
Wiclax/G-Live couvre plusieurs déploiements : `wiclax-results.com`,
`chronosmetron.com` et `chronowest.fr` (WordPress + iframe G-Live). Un nouveau
déploiement tiers = un host dans `WiclaxProvider._HOSTS`.
RaceResult couvre de même trois façades d'un même produit (`raceresult.com`,
`espace-competition.com`, `chronoconsult.fr`, cf. `RaceResultProvider._HOSTS`),
toutes servies par la même API JSON publique — sans Playwright, et toutes
joignables via l'apex `my.raceresult.com` (aucune résolution de shard).
Particularités du moteur : les listes publiées sont celles dont `Mode` n'est pas
`"hidden"` dans `config["TabConfig"]["Lists"]` (qui porte le contest
explicitement), plusieurs listes peuvent couvrir un même contest et doivent être
fusionnées, et la date d'épreuve n'existe que dans le JSON-LD schema.org de la
page `/{eventId}/results`.
Vérité d'API : `docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md`.
Design : `docs/superpowers/specs/2026-07-19-raceresult-scraper-design.md`.
Types : Triathlon XS/S/M/L/XL, Duathlon XS/S/M/L, SwimRun S/M/L, Aquathlon,
Aquarun, Bike & Run.
```

Dans la section « Modèle normalisé », remplacer la phrase de *Limite* par :

```markdown
  *Limite levée pour les scrapers qui renseignent `segments`* (RaceResult) : la
  liste ordonnée de segments étiquetés prime sur les 5 slots et n'a pas de
  plafond — un swimrun multi-legs y garde toutes ses étapes. Les scrapers qui
  remplissent encore les 5 slots restent plafonnés à 5 segments.
```

- [ ] **Step 5 : Vérifier la suite complète et commiter**

```bash
uv run pytest -m "not integration" -q
uv run ruff check .
git add tests/test_integration_scrapers.py ../AGENTS.md
git commit -m "test(scrapers): intégration RaceResult + documentation du fournisseur"
```

---

## Vérification finale

- [ ] `cd backend && uv run pytest -m "not integration" -q` — tout vert
- [ ] `cd backend && uv run pytest -m integration -k raceresult -v` — tout vert
- [ ] `cd backend && uv run ruff check .` — aucune violation
- [ ] `cd backend && uv run python -m app.cli rescrape-db --only-provider raceresult --dry-run` — le provider est accepté par `cli/validators` (il dérive de `provider_names()`, donc du simple fait de son entrée dans `PROVIDERS`)
