"""
Tests unitaires pour scrapers/raceresult.py (sans réseau).

Fixtures réduites à la main, provenance et date en tête de chaque fichier.
Les appels HTTP passent par un faux client httpx (pattern test_sportinnovation.py)
ou par monkeypatch des helpers `_fetch_*` (pattern test_wiclax.py).
"""
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
