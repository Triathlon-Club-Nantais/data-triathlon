"""
Tests unitaires pour scrapers/sportinnovation.py (sans réseau).

Couvre les helpers purs : parsing de la cellule nom ("NOM PrénomG-CatG"),
mapping des colonnes depuis l'en-tête, construction d'un résultat depuis une
ligne HTML, et détection du type d'épreuve.
"""
import pytest

from app.scrapers.sportinnovation import (
    _classify_results_url,
    _col_indices,
    _detect_event_type,
    _parse_api_athlete,
    _parse_html_row,
    _parse_name_cell,
)


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
# _classify_results_url — distingue la forme 2026 /race/{slug} de /{codeUrl}
# ---------------------------------------------------------------------------

def test_classify_results_url_race_form():
    kind, ident = _classify_results_url("https://results.sportinnovation.fr/race/zmhc-triathlon-m")
    assert (kind, ident) == ("race", "zmhc-triathlon-m")


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
