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
from app.scrapers.base import STATUS_DNF, STATUS_DNS

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


# ── Groupes (contest / statut) ──────────────────────────────────────────────

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


# ── Construction d'un ScrapedResult ─────────────────────────────────────────

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
