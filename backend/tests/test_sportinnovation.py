"""
Tests unitaires pour scrapers/sportinnovation.py (sans réseau).

Couvre les helpers purs : parsing de la cellule nom ("NOM PrénomG-CatG"),
mapping des colonnes depuis l'en-tête, construction d'un résultat depuis une
ligne HTML, détection du type d'épreuve, et extraction des métadonnées
(nom d'événement + date) depuis la page de détail d'un participant.
"""
from datetime import date
from pathlib import Path

import pytest

from app.scrapers.sportinnovation import (
    _classify_results_url,
    _col_indices,
    _compose_course_name,
    _detect_event_type,
    _parse_api_athlete,
    _parse_html_row,
    _parse_name_cell,
    _parse_race_meta,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_name_cell_standard():
    """'GUEGANO JordanH-S3H' → (GUEGANO, Jordan, H, S3H)."""
    lastname, firstname, gender, cat = _parse_name_cell("GUEGANO JordanH-S3H")
    assert lastname == "GUEGANO"
    assert firstname == "Jordan"
    assert gender == "H"
    assert cat == "S3H"


def test_parse_name_cell_composed_lastname_known_limitation():
    """
    Limite connue : pour un nom de famille composé ("LE GALL"), `_NAME_RE` rattache
    le second mot au prénom (la classe prénom accepte les majuscules). Le genre et la
    catégorie restent corrects. Test verrouillant le comportement actuel — à mettre à
    jour si le regex est amélioré.
    """
    lastname, firstname, gender, cat = _parse_name_cell("LE GALL MarieF-V1F")
    assert lastname == "LE"
    assert firstname == "GALL Marie"
    assert gender == "F"
    assert cat == "V1F"


def test_detect_event_type():
    assert _detect_event_type("Triathlon M") == "triathlon-m"
    assert _detect_event_type("Triathlon S") == "triathlon-s"
    assert _detect_event_type("Aquathlon du RC Doué") == "aquathlon"
    assert _detect_event_type("Bike & Run d'Halloween") == "bike-run"
    assert _detect_event_type("SwimRun des Îles") == "swimrun"
    assert _detect_event_type("Duathlon Sprint") == "duathlon-s"


HEADERS = ["Place", "Dossard", "Nom", "Club", "Tps Off.", "Nat", "T1", "Vélo", "T2", "CAP"]


def test_col_indices():
    col = _col_indices(HEADERS)
    assert col["rank_overall"] == 0
    assert col["bib"] == 1
    assert col["name"] == 2
    assert col["club"] == 3
    assert col["total_time"] == 4
    assert col["swim_time"] == 5
    assert col["t1_time"] == 6
    assert col["bike_time"] == 7
    assert col["t2_time"] == 8
    assert col["run_time"] == 9


def test_parse_html_row():
    col = _col_indices(HEADERS)
    tds = [
        "1", "42", "DUPONT JeanH-S3H", "TCN",
        "01:59:00", "00:11:00", "00:01:00", "01:05:00", "00:00:50", "00:41:10",
    ]
    r = _parse_html_row(tds, col, "http://x", "Triathlon M")
    assert r.event_type == "triathlon-m"
    assert r.athlete_name == "DUPONT"
    assert r.athlete_firstname == "Jean"
    assert r.gender == "H"
    assert r.category == "S3H"
    assert r.bib_number == "42"
    assert r.club == "TCN"
    assert r.rank_overall == 1
    assert r.total_time == "01:59:00"
    assert r.swim_time == "00:11:00"
    assert r.t1_time == "00:01:00"
    assert r.bike_time == "01:05:00"
    assert r.t2_time == "00:00:50"
    assert r.run_time == "00:41:10"


# ---------------------------------------------------------------------------
# _parse_race_meta — nom d'événement + date, depuis la page de détail legacy
#
# La page liste `/Evenements/Resultats/{id}` n'expose ni le nom de l'événement
# ni sa date (le bandeau est rempli en JS). La page du modal de détail,
# `/Evenements/Resultats/Detail/{id}/1`, porte les deux : un <h6> « Course
# (jj/mm/aaaa) » et un lien de partage « Résultats - Course - Événement ».
# ---------------------------------------------------------------------------

def test_parse_race_meta_extrait_course_evenement_et_date():
    html = (FIXTURES / "sportinnovation_detail_7031.html").read_text(encoding="utf-8")
    race_name, event_name, event_date = _parse_race_meta(html)
    assert race_name == "Triathlon M"
    assert event_name == "Triathlon de Carnac 2025"
    assert event_date == date(2025, 10, 5)


def test_parse_race_meta_course_contenant_un_tiret():
    """Le nom de course peut contenir « - » : le découpage part du <h6>, pas du dernier tiret."""
    html = (
        '<h6 class="col-12">Bike &amp; Run - Kids (04/10/2025)</h6>'
        '<a href="https://www.facebook.com/sharer/sharer.php?u=https://x'
        '&t=Résultats - Bike &amp; Run - Kids - Triathlon de Carnac 2025"></a>'
    )
    race_name, event_name, event_date = _parse_race_meta(html)
    assert race_name == "Bike & Run - Kids"
    assert event_name == "Triathlon de Carnac 2025"
    assert event_date == date(2025, 10, 4)


def test_parse_race_meta_sans_lien_de_partage():
    """Sans lien de partage, on garde la course et la date ; l'événement reste vide."""
    race_name, event_name, event_date = _parse_race_meta("<h6>Aquathlon Pupilles (04/10/2025)</h6>")
    assert race_name == "Aquathlon Pupilles"
    assert event_name == ""
    assert event_date == date(2025, 10, 4)


def test_parse_race_meta_page_vide():
    assert _parse_race_meta("<div>rien</div>") == ("", "", None)


def test_parse_race_meta_date_invalide_ignoree():
    race_name, event_name, event_date = _parse_race_meta("<h6>Triathlon M (32/13/2025)</h6>")
    assert race_name == "Triathlon M"
    assert event_date is None


# ---------------------------------------------------------------------------
# _compose_course_name — « Événement - Course », clé d'unicité de la Course
#
# `uq_course_identity` = (name, event_date, event_type, is_relay). Les quatre
# aquathlons de Carnac partagent date + event_type : sans le nom de course dans
# le nom, ils fusionneraient en une seule Course.
# ---------------------------------------------------------------------------

def test_compose_course_name_concatene():
    assert _compose_course_name("Triathlon de Carnac 2025", "Triathlon M") == (
        "Triathlon de Carnac 2025 - Triathlon M"
    )


def test_compose_course_name_aquathlons_restent_distincts():
    noms = {
        _compose_course_name("Triathlon de Carnac 2025", r)
        for r in ("Aquathlon Pupilles", "Aquathlon Benjamins", "Aquathlon Minimes")
    }
    assert len(noms) == 3


def test_compose_course_name_evenement_manquant():
    assert _compose_course_name("", "Triathlon M") == "Triathlon M"


def test_compose_course_name_course_manquante():
    assert _compose_course_name("Triathlon de Carnac 2025", "") == "Triathlon de Carnac 2025"


def test_compose_course_name_identiques_pas_de_doublon():
    """Événement mono-course : « Swimrun Cote Beaute 2025 », pas « X - X »."""
    assert _compose_course_name("Swimrun Cote Beaute 2025", "Swimrun Cote Beaute 2025") == (
        "Swimrun Cote Beaute 2025"
    )


# ---------------------------------------------------------------------------
# _parse_html_row — porte désormais le nom composé et la date
# ---------------------------------------------------------------------------

def test_parse_html_row_porte_nom_composé_et_date():
    col = {"name": 0, "bib": 1, "total_time": 2}
    tds = ["DUPONT JeanH-S3H", "42", "01:23:45"]
    r = _parse_html_row(
        tds, col, "http://x", "Aquathlon Pupilles",
        course_name="Triathlon de Carnac 2025 - Aquathlon Pupilles",
        event_date=date(2025, 10, 4),
    )
    assert r.event_name == "Triathlon de Carnac 2025 - Aquathlon Pupilles"
    assert r.event_date == date(2025, 10, 4)
    # Le type reste classifié sur le titre de course, jamais sur le nom composé.
    assert r.event_type == "aquathlon"


# ---------------------------------------------------------------------------
# _classify_results_url — distingue la forme 2026 /race/{slug} de /{codeUrl}
# ---------------------------------------------------------------------------

def test_classify_results_url_race_form():
    kind, ident = _classify_results_url("https://results.sportinnovation.fr/race/zmhc-triathlon-m")
    assert (kind, ident) == ("race", "zmhc-triathlon-m")


def test_classify_results_url_detail_form():
    kind, ident = _classify_results_url("https://results.sportinnovation.fr/detail/51636b-18-c1066a43c01880e8")
    assert (kind, ident) == ("detail", "51636b-18-c1066a43c01880e8")


def test_classify_results_url_event_form():
    kind, ident = _classify_results_url("https://results.sportinnovation.fr/bayman_triathlon")
    assert (kind, ident) == ("event", "bayman_triathlon")


def test_classify_results_url_empty_raises():
    with pytest.raises(ValueError):
        _classify_results_url("https://results.sportinnovation.fr/")


# ---------------------------------------------------------------------------
# _parse_api_athlete — mapping d'un athlète JSON (API results.sportinnovation.fr)
# ---------------------------------------------------------------------------

def test_parse_api_athlete():
    a = {
        "lastName": "SAMSON", "firstName": "Fabian", "bib": "213",
        "clubName": None, "sex": "M", "category": "M SENIOR",
        "generalRanking": 1, "sexRanking": 1, "categoryRanking": 1,
        "officialTime": "01:53:37", "realTime": "01:53:37",
    }
    r = _parse_api_athlete(a, "http://x", "Bayman", "triathlon-m", None)
    assert r.event_name == "Bayman"
    assert r.event_type == "triathlon-m"
    assert r.athlete_name == "SAMSON"
    assert r.athlete_firstname == "Fabian"
    assert r.bib_number == "213"
    assert r.club == ""            # None → chaîne vide
    assert r.gender == "M"
    assert r.category == "M SENIOR"
    assert r.rank_overall == 1
    assert r.rank_gender == 1
    assert r.rank_category == 1
    assert r.total_time == "01:53:37"


def test_parse_api_athlete_falls_back_to_real_time():
    a = {"lastName": "X", "bib": "1", "officialTime": "", "realTime": "00:59:00"}
    r = _parse_api_athlete(a, "http://x", "E", "triathlon", None)
    assert r.total_time == "00:59:00"


# ---------------------------------------------------------------------------
# Statut non-finisher — HTML (colonne temps) + API (champ status/state)
# ---------------------------------------------------------------------------

def test_parse_html_row_explicit_status():
    """Colonne temps = 'Abandon' → status DNF + temps purgé."""
    col = {"name": 0, "bib": 1, "total_time": 2}
    tds = ["DUPONT JeanH-S3H", "42", "Abandon"]
    r = _parse_html_row(tds, col, "http://x", "Triathlon S")
    assert r.status == "DNF"
    assert r.total_time == ""


def test_parse_html_row_finisher_no_status():
    col = {"name": 0, "bib": 1, "total_time": 2}
    tds = ["DUPONT JeanH-S3H", "42", "01:23:45"]
    r = _parse_html_row(tds, col, "http://x", "Triathlon S")
    assert r.status == ""
    assert r.total_time == "01:23:45"


def test_parse_api_athlete_explicit_status():
    """Champ JSON status='DNS' → DNS + hygiène."""
    a = {
        "lastName": "Dupont", "firstName": "Jean", "bib": 42,
        "status": "DNS", "generalRanking": "5", "officialTime": "",
    }
    r = _parse_api_athlete(a, "http://x", "Triathlon", "triathlon-s", None)
    assert r.status == "DNS"
    assert r.total_time == ""
    assert r.rank_overall is None


# ---------------------------------------------------------------------------
# _scrape_results_race — chemin API : même convention de nommage que le legacy
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeClient:
    """Client httpx minimal : sert des payloads indexés par suffixe d'URL."""

    def __init__(self, routes):
        self.routes = routes

    def get(self, url, **_kwargs):
        for suffix, payload in self.routes.items():
            if url.endswith(suffix):
                return _FakeResponse(payload)
        raise AssertionError(f"URL non routée : {url}")


def test_scrape_results_race_compose_le_nom_et_porte_la_date(monkeypatch):
    from app.scrapers import sportinnovation as si

    monkeypatch.setattr(si, "_fetch_splits_parallel", lambda athletes, **kw: {})
    client = _FakeClient({
        "/races/zmhc-aquathlon-pupilles": {
            "slug": "zmhc-aquathlon-pupilles",
            "title": "Aquathlon Pupilles",
            "eventSlug": "gqjk02-triathlon-de-carnac-2025",
        },
        "/events/gqjk02-triathlon-de-carnac-2025": {
            "title": "Triathlon de Carnac 2025",
            "eventDate": "2025-10-04",
        },
        "/races/zmhc-aquathlon-pupilles/results": [
            {"lastName": "DUPONT", "firstName": "Jean", "bib": "7", "officialTime": "00:20:00"},
        ],
    })

    results = si._scrape_results_race("zmhc-aquathlon-pupilles", "http://x", client)

    assert len(results) == 1
    assert results[0].event_name == "Triathlon de Carnac 2025 - Aquathlon Pupilles"
    assert results[0].event_type == "aquathlon"
    assert results[0].event_date == date(2025, 10, 4)
