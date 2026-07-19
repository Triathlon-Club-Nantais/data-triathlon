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
from app.scrapers.base import STATUS_DNF, STATUS_DNS, ScrapedResult

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


# ── Richesse (arbitrage des doublons) ───────────────────────────────────────

def test_richness_ignore_les_extras_vides():
    """I1 : `raw_data` n'est pas filtré des cellules vides — une ligne quasi
    vide (dossard seul, deux extras vides) ne doit pas peser autant qu'une
    ligne réellement renseignée."""
    pauvre = ScrapedResult(
        source_url="x", provider="raceresult", bib_number="1",
        raw_data={"Extra1": "", "Extra2": ""},
    )
    riche = ScrapedResult(
        source_url="x", provider="raceresult", bib_number="1",
        club="GRESIVAUDAN TRIATHLON",
    )

    assert raceresult._richness(pauvre) == 0
    assert raceresult._richness(riche) == 1
    assert raceresult._richness(riche) > raceresult._richness(pauvre)


# ── Pipeline complet : contests empiriques, fusion, erreurs ────────────────

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
    """404 sur contest=0, succès sur contest=1 : le balayage ne s'arrête pas au premier échec.

    L'ordre complet est vérifié (pas un `essais[:2]` tronqué, qui masquerait un
    `break` prématuré sur un contest non-"0" — cf. C1) : les deux specs de la
    config Rumilly (indices "0" et "3") retentent chacune "0", "1" puis "4",
    car aucun des contests essayés ne vaut jamais "0" avec succès.
    """
    essais = _brancher(monkeypatch, {"1": _payload_rumilly()})

    resultats = raceresult.scrape_event_all("https://my3.raceresult.com/393893/results")

    assert essais == ["0", "1", "4", "3", "0", "1", "4"], f"ordre d'essai inattendu : {essais}"
    assert len(resultats) == 4
    assert {r.bib_number for r in resultats} == {"79", "112", "205", "310"}


def test_scrape_event_all_ne_s_arrete_pas_au_premier_contest_qui_repond(monkeypatch):
    """Non-régression C1 : 404 sur contest=0, contest 1 ET contest 4 tous deux
    porteurs de données. Le `break` ne doit couper le balayage que lorsque
    c'est contest=0 (« tous ») qui répond — sinon chaque contest suivant est
    silencieusement perdu (cas réel Rumilly : Distance M disparaissait, 1
    participant importé au lieu de 5)."""
    config = {
        "key": "k",
        "contests": {"1": "Distance XS", "4": "Distance M"},
        "lists": {"Résultats": {"Contest": "0"}},
    }
    monkeypatch.setattr(raceresult, "_resolve_event_id", lambda url, client: "393893")
    monkeypatch.setattr(
        raceresult, "_fetch_meta",
        lambda eid, base, client: ("Triathlon de Rumilly", date(2026, 6, 18), "RUMILLY"),
    )
    monkeypatch.setattr(raceresult, "_fetch_config", lambda eid, base, client: config)

    payload_xs = _payload_rumilly()
    payload_xs["data"] = {"#1_Distance XS": {"#1_": [
        ["1", "10", "1.", "1", "Jean DUPONT", "M", "1.S1M", "CLUB A", "", "",
         "", "", "", "", "", "", "", "", "01:00:00", ""],
    ]}}
    payload_m = _payload_rumilly()

    essais: list[str] = []

    def faux_fetch_list(eid, base, key, listname, contest, client):
        essais.append(contest)
        return {"1": payload_xs, "4": payload_m}.get(contest)

    monkeypatch.setattr(raceresult, "_fetch_list", faux_fetch_list)

    resultats = raceresult.scrape_event_all("https://my3.raceresult.com/393893/results")

    assert essais == ["0", "1", "4"]
    assert {r.bib_number for r in resultats} == {"1", "79", "112", "205", "310"}
    assert {r.event_name for r in resultats} == {
        "Triathlon de Rumilly - Distance XS",
        "Triathlon de Rumilly - Distance M",
    }


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


def test_scrape_event_all_liste_inscrits_vide_n_ecrase_pas_le_classement(monkeypatch):
    """I1, niveau pipeline : une liste "Inscrits" plus large en colonnes mais
    vide sur ce dossard ne doit pas l'emporter sur une liste "Classement" qui,
    elle, renseigne le club — critère d'attribution TCN. Avant le correctif,
    `_richness` comptait `len(raw_data)` (la largeur de la liste source, pas
    ses données) : 10 extras vides battaient les 4 champs réellement remplis
    du classement."""
    classement = {
        "DataFields": ["BIB", "AfficherNom", "ucase([CLUB])", "TIME"],
        "Fields": [
            {"Expression": "AfficherNom", "Label": "Nom"},
            {"Expression": "ucase([CLUB])", "Label": "Club"},
            {"Expression": "TIME", "Label": "Temps"},
        ],
        "data": {"#1_Distance M": {"#1_": [
            ["79", "Alexis ROUX", "GRESIVAUDAN TRIATHLON", "02:01:56"]
        ]}},
    }
    inscrits = {
        "DataFields": ["BIB"] + [f"Extra{i}" for i in range(10)],
        "Fields": [{"Expression": f"Extra{i}", "Label": f"E{i}"} for i in range(10)],
        "data": {"#1_Distance M": {"#1_": [["79"] + [""] * 10]}},
    }
    _brancher(monkeypatch, {"0": classement, "3": inscrits})

    resultats = raceresult.scrape_event_all("https://my3.raceresult.com/393893/results")

    cible = [r for r in resultats if r.bib_number == "79"][0]
    assert cible.club == "GRESIVAUDAN TRIATHLON"


def test_scrape_event_all_preserve_le_statut_non_finisher_moins_riche(monkeypatch):
    """I2 : un DNF (groupe « Abandons ») ne doit pas être écrasé par une ligne
    plus riche en colonnes mais sans sous-groupe de statut pour le même
    (contest, dossard) — sinon le statut non-finisher se perd silencieusement.

    La ligne concurrente reste riche en colonnes (club, catégorie…) mais
    n'annonce elle-même aucun temps réel (cas d'une liste "Inscrits" plus
    large) : c'est ce qui doit trancher, pas la seule richesse (cf. N1 — une
    ligne concurrente qui, elle, porterait un vrai temps d'arrivée doit au
    contraire l'emporter, cf. test_scrape_event_all_un_dns_n_ecrase_pas_un_finisher_reel)."""
    dnf = _payload_rumilly()
    dnf["data"] = {"#1_Distance M": {"#2_Abandons": [
        dnf["data"]["#1_Distance M"]["#2_Abandons"][0]
    ]}}
    riche_sans_statut = _payload_rumilly()
    ligne_riche = list(riche_sans_statut["data"]["#1_Distance M"]["#1_"][0])
    ligne_riche[0] = "205"  # même dossard que le DNF, ligne sans groupe de statut
    ligne_riche[3] = "205"
    ligne_riche[18] = ""  # aucun temps réel : ne doit pas primer sur le statut
    riche_sans_statut["data"] = {"#1_Distance M": {"#1_": [ligne_riche]}}

    _brancher(monkeypatch, {"0": dnf, "3": riche_sans_statut})

    resultats = raceresult.scrape_event_all("https://my3.raceresult.com/393893/results")

    cible = [r for r in resultats if r.bib_number == "205"]
    assert len(cible) == 1
    assert cible[0].status == STATUS_DNF
    assert cible[0].total_time == ""


def test_scrape_event_all_un_dns_n_ecrase_pas_un_finisher_reel(monkeypatch):
    """N1 (régression critique du correctif I2) : un DNS/DNF ne doit jamais
    écraser un finisher réel, même si la règle de statut était inconditionnelle
    dans le correctif précédent — un chrono d'arrivée est un signal plus fort
    qu'un statut annoncé.

    Reproduction du relecteur : liste A / contest 0 porte un finisher riche
    (dossard 79, temps réel, rang, club) ; liste B / contest 3 reporte ce même
    dossard dans le groupe « Non Partants » (liste figée à la veille, dossard
    réattribué). Avant correctif : `_prefer(DNS_vide, finisher_riche)` valait
    True inconditionnellement (statut non-finisher toujours prioritaire) et le
    temps, le rang et le club réels étaient détruits."""
    finisher = _payload_rumilly()  # contest "0" : bib 79 finisher réel, intact
    dns = _payload_rumilly()
    ligne_dns = list(dns["data"]["#1_Distance M"]["#3_Non Partants"][0])
    ligne_dns[0] = "79"  # même dossard que le finisher, réattribué côté DNS
    ligne_dns[3] = "79"
    dns["data"] = {"#1_Distance M": {"#3_Non Partants": [ligne_dns]}}

    _brancher(monkeypatch, {"0": finisher, "3": dns})

    resultats = raceresult.scrape_event_all("https://my3.raceresult.com/393893/results")

    cible = [r for r in resultats if r.bib_number == "79"][0]
    assert cible.status == "finisher"
    assert cible.total_time == "02:01:56"
    assert cible.rank_overall == 2
    assert cible.club == "GRESIVAUDAN TRIATHLON"


def test_prefer_refuse_qu_un_statut_non_finisher_ecrase_un_temps_reel():
    """N1, niveau unitaire : un DNS sans aucune donnée ne doit jamais écraser
    un finisher réel — même si la règle de statut, seule, l'y autoriserait."""
    finisher = ScrapedResult(
        source_url="x", provider="raceresult", bib_number="79",
        total_time="02:01:56", rank_overall=2, club="GRESIVAUDAN TRIATHLON",
        status="finisher",
    )
    dns_vide = ScrapedResult(
        source_url="x", provider="raceresult", bib_number="79",
        club="CHAMBERY TRIATHLON", status=STATUS_DNS,
    )

    assert raceresult._prefer(dns_vide, finisher) is False


def test_prefer_autorise_un_statut_non_finisher_sans_temps_concurrent():
    """N1, garde-fou symétrique : le correctif ne doit pas réintroduire I2 —
    un DNF continue de l'emporter sur une ligne concurrente qui n'a elle-même
    aucun temps réel."""
    vide_sans_statut = ScrapedResult(
        source_url="x", provider="raceresult", bib_number="205", club="X",
    )
    dnf = ScrapedResult(
        source_url="x", provider="raceresult", bib_number="205", status=STATUS_DNF,
    )

    assert raceresult._prefer(dnf, vide_sans_statut) is True


def test_scrape_event_all_desambiguise_les_groupes_non_nommes(monkeypatch):
    """I3 : sans libellé de contest dans la clé de groupe ni entrée dans
    `contests` pour le contest interrogé, la clé de fusion doit rester
    injective — repli sur le `listname` pour ne pas fusionner deux contests
    distincts sous la même clé vide (issue #21).

    Contrairement à `contest="0"` (repli désormais géré à part, cf. N2
    ci-dessous), un contest explicite non déclaré dans `contests` (ici "5")
    ne bénéficie d'aucun autre signal : le repli sur `listname` reste alors la
    seule désambiguïsation possible."""
    config = {
        "key": "k",
        "contests": {"1": "Distance XS", "4": "Distance M"},
        "lists": {"Groupe2": {"Contest": 5}},
    }
    monkeypatch.setattr(raceresult, "_resolve_event_id", lambda url, client: "393893")
    monkeypatch.setattr(
        raceresult, "_fetch_meta",
        lambda eid, base, client: ("Triathlon de Rumilly", date(2026, 6, 18), "RUMILLY"),
    )
    monkeypatch.setattr(raceresult, "_fetch_config", lambda eid, base, client: config)

    def _ligne(bib):
        return [bib, "1", "1.", bib, "Jean DUPONT", "M", "1.S1M", "CLUB",
                "", "", "", "", "", "", "", "", "", "", "01:00:00", ""]

    payload_b = _payload_rumilly()
    payload_b["data"] = {"#1_": [_ligne("79")]}

    def faux_fetch_list(eid, base, key, listname, contest, client):
        if listname == "Groupe2" and contest == "5":
            return payload_b
        return None

    monkeypatch.setattr(raceresult, "_fetch_list", faux_fetch_list)

    resultats = raceresult.scrape_event_all("https://my3.raceresult.com/393893/results")

    assert len(resultats) == 1
    assert resultats[0].event_name == "Triathlon de Rumilly - Groupe2"


def test_scrape_event_all_desambiguise_par_contest_sans_dupliquer_entre_listes(monkeypatch):
    """N2, effet de bord du repli `listname` (I3) : deux listes exposent,
    chacune sous un groupe non nommé sans `contest="0"` déclaré dans
    `contests`, la **même** tranche réelle (contest 1), une des deux listes
    exposant en plus un second contest (4) exclusif. Le repli I3 distinguait
    bien les deux listes par leur `listname` — mais en fabriquait deux
    « Courses » pour le même athlète recopié dans les deux (constaté en revue :
    4 participations pour 3 athlètes). Le contest réel, seule information
    fiable une fois `contest="0"` écarté (cf. `scrape_event_all`), doit à la
    fois désambiguïser *et* faire converger les deux accès vers la même clé de
    fusion — peu importe le chemin de liste par lequel on y arrive."""
    config = {
        "key": "k",
        "contests": {"1": "Distance XS", "4": "Distance M"},
        "lists": {"Groupe1": {"Contest": 0}, "Groupe2": {"Contest": 0}},
    }
    monkeypatch.setattr(raceresult, "_resolve_event_id", lambda url, client: "393893")
    monkeypatch.setattr(
        raceresult, "_fetch_meta",
        lambda eid, base, client: ("Triathlon de Rumilly", date(2026, 6, 18), "RUMILLY"),
    )
    monkeypatch.setattr(raceresult, "_fetch_config", lambda eid, base, client: config)

    def _ligne(bib, nom):
        return [bib, "1", "1.", bib, nom, "M", "1.S1M", "CLUB",
                "", "", "", "", "", "", "", "", "", "", "01:00:00", ""]

    champs = {k: _payload_rumilly()[k] for k in ("DataFields", "Fields")}

    def _payload(lignes):
        return {**champs, "data": {"#1_": lignes}}

    # `contest=0` : payload plat, différent selon la liste interrogée — deux
    # vues d'un même serveur qui n'a pas de sous-découpage par contest.
    ambigu_groupe1 = _payload([_ligne("79", "Jean DUPONT"), _ligne("100", "Un TROISIEME")])
    ambigu_groupe2 = _payload([_ligne("79", "Jean DUPONT")])  # même athlète, même tranche
    # Contest explicite : la même donnée réelle, quelle que soit la liste —
    # c'est elle qui doit trancher, pas le chemin de liste emprunté.
    reel_xs = _payload([_ligne("79", "Jean DUPONT")])
    reel_m = _payload([_ligne("100", "Un TROISIEME")])

    def faux_fetch_list(eid, base, key, listname, contest, client):
        if contest == "0":
            return {"Groupe1": ambigu_groupe1, "Groupe2": ambigu_groupe2}.get(listname)
        return {"1": reel_xs, "4": reel_m}.get(contest)

    monkeypatch.setattr(raceresult, "_fetch_list", faux_fetch_list)

    resultats = raceresult.scrape_event_all("https://my3.raceresult.com/393893/results")

    assert len(resultats) == 2  # DUPONT (Distance XS) + TROISIEME (Distance M) — pas 3
    assert {r.athlete_name for r in resultats} == {"DUPONT", "TROISIEME"}
    assert {r.event_name for r in resultats} == {
        "Triathlon de Rumilly - Distance XS", "Triathlon de Rumilly - Distance M",
    }


def test_scrape_event_all_desambiguise_la_collision_intra_payload(monkeypatch):
    """N2 : I3 ne réglait la collision qu'entre listes distinctes — au sein
    d'un même payload non nommé (`data = {"#1_": [...]}`), `listname` est
    **constant sur tout le payload** et ne distingue donc pas deux lignes du
    même dossard servies par deux contests réels différents (cas RaceResult où
    `contest=0` renvoie tout mélangé, sans sous-groupe par contest).

    Reproduction : le payload `contest=0` porte trois lignes, dont deux sous
    le dossard 79 (une par contest réel). Avant correctif : `listname`
    collisionne les deux lignes du dossard 79 (une est perdue) et le `break`
    inconditionnel sur `contest="0"` empêche même d'aller consulter les
    payloads `contest=1`/`contest=2`, seuls capables de lever l'ambiguïté —
    3 lignes en entrée, 2 résultats en sortie, un coureur toujours perdu."""

    def _ligne(bib, nom):
        return [bib, "1", "1.", bib, nom, "M", "1.S1M", "CLUB",
                "", "", "", "", "", "", "", "", "", "", "01:00:00", ""]

    config = {
        "key": "k",
        "contests": {"1": "Distance XS", "2": "Distance M"},
        "lists": {"Résultats": {"Contest": 0}},
    }
    monkeypatch.setattr(raceresult, "_resolve_event_id", lambda url, client: "393893")
    monkeypatch.setattr(
        raceresult, "_fetch_meta",
        lambda eid, base, client: ("Triathlon de Rumilly", date(2026, 6, 18), "RUMILLY"),
    )
    monkeypatch.setattr(raceresult, "_fetch_config", lambda eid, base, client: config)

    champs = {k: _payload_rumilly()[k] for k in ("DataFields", "Fields")}

    def _payload(lignes):
        return {**champs, "data": {"#1_": lignes}}

    payload_ambigu = _payload([
        _ligne("79", "Jean DUPONT"),
        _ligne("79", "Autre COUREUR"),
        _ligne("100", "Un TROISIEME"),
    ])
    payload_xs = _payload([_ligne("79", "Jean DUPONT"), _ligne("100", "Un TROISIEME")])
    payload_m = _payload([_ligne("79", "Autre COUREUR")])

    def faux_fetch_list(eid, base, key, listname, contest, client):
        return {"0": payload_ambigu, "1": payload_xs, "2": payload_m}.get(contest)

    monkeypatch.setattr(raceresult, "_fetch_list", faux_fetch_list)

    resultats = raceresult.scrape_event_all("https://my3.raceresult.com/393893/results")

    assert len(resultats) == 3
    assert {r.athlete_name for r in resultats} == {"DUPONT", "COUREUR", "TROISIEME"}
    assert {r.event_name for r in resultats} == {
        "Triathlon de Rumilly - Distance XS", "Triathlon de Rumilly - Distance M",
    }


def test_scrape_event_all_ouvre_le_client_avec_follow_redirects(monkeypatch):
    """L'API `list` répond 301 : sans `follow_redirects=True`, toutes les
    listes reviennent vides. Verrouille le kwarg pour éviter une régression
    silencieuse."""
    captes: dict = {}
    VraiClient = httpx.Client

    class ClientObserve(VraiClient):
        def __init__(self, *args, **kwargs):
            captes.update(kwargs)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", ClientObserve)
    _brancher(monkeypatch, {})

    with pytest.raises(ValueError):
        raceresult.scrape_event_all("https://my3.raceresult.com/393893/results")

    assert captes.get("follow_redirects") is True


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
