"""
Tests unitaires pour scrapers/raceresult.py (sans réseau).

Fixtures réduites à la main, provenance et date en tête de chaque fichier.
Les appels HTTP passent par un faux client httpx (pattern test_sportinnovation.py)
ou par monkeypatch des helpers `_fetch_*` (pattern test_wiclax.py).
"""
import json
from datetime import date
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

    `appels` enregistre l'URL **effective**, `params=` fusionné dans la query :
    le code de production reste libre de passer ses paramètres comme httpx
    l'attend, sans devoir les concaténer à la main pour être observable.
    """

    def __init__(self, routes: dict[str, tuple[int, str]]):
        self.routes = routes
        self.appels: list[str] = []

    def get(self, url: str, **kwargs) -> httpx.Response:
        params = kwargs.get("params")
        self.appels.append(str(httpx.URL(url, params=params)) if params else url)
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


# ── Métadonnées (JSON-LD) et configuration ──────────────────────────────────

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


# ── Mapping des colonnes ─────────────────────────────────────────────────────

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
