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
from urllib.parse import urlparse

import httpx

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
