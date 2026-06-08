"""
Tests unitaires pour scrapers/prolivesport.py (sans réseau).

Couvre les helpers purs : mapping des splits (champ→rôle), parsing d'un athlète
depuis le dict JSON de l'API, et détection du type d'épreuve.
"""
import pytest

from app.scrapers.prolivesport import (
    _build_split_map,
    _derive_status,
    _detect_event_type,
    _parse_athlete,
    _parse_url,
    _resolve_race,
)

# Liste de courses telle que renvoyée par result/raceList/{eventId}/
RACES = [
    {"race": "PO-PU"}, {"race": "BE-MI"}, {"race": "S_Light"}, {"race": "Challenge"},
    {"race": "TREP"}, {"race": "TRGP"}, {"race": "S"}, {"race": "M"},
]


def test_build_split_map_filters_by_race():
    splits = [
        {"race": "S", "field": "Nat", "label": "Natation"},
        {"race": "S", "field": "Tr1", "label": "T1"},
        {"race": "S", "field": "Velo", "label": "Vélo"},
        {"race": "S", "field": "Tr2", "label": "T2"},
        {"race": "S", "field": "Cap", "label": "Course à pied"},
        {"race": "M", "field": "AutreNat", "label": "Natation"},  # autre course → ignoré
    ]
    mapping = _build_split_map(splits, race="S")
    assert mapping == {
        "Nat": "swim",
        "Tr1": "t1",
        "Velo": "bike",
        "Tr2": "t2",
        "Cap": "run",
    }


def test_parse_athlete_fields_and_splits():
    athlete = {
        "lastname": "Dupont",
        "firstname": "Jean",
        "number": "42",
        "club": "TCN",
        "categoryRef": "S3H",
        "sex": "H",
        "rank": "5",
        "rankSex": "4",
        "rankCat": "1",
        "time": "01:59:00",
        "timeNat": "00:11:00",
        "timeTr1": "00:01:00",
        "timeVelo": "01:05:00",
        "timeTr2": "00:00:50",
        "timeCap": "00:41:10",
    }
    split_map = {"Nat": "swim", "Tr1": "t1", "Velo": "bike", "Tr2": "t2", "Cap": "run"}
    r = _parse_athlete(athlete, split_map, "http://x", "Triathlon Test", "triathlon-s", None)

    assert r.athlete_name == "DUPONT"          # lastname en majuscules
    assert r.athlete_firstname == "Jean"
    assert r.bib_number == "42"
    assert r.club == "TCN"
    assert r.category == "S3H"
    assert r.gender == "H"
    assert r.rank_overall == 5
    assert r.rank_gender == 4
    assert r.rank_category == 1
    assert r.total_time == "01:59:00"
    assert r.swim_time == "00:11:00"
    assert r.t1_time == "00:01:00"
    assert r.bike_time == "01:05:00"
    assert r.t2_time == "00:00:50"
    assert r.run_time == "00:41:10"


def test_parse_athlete_skips_zero_splits():
    """Un split à 00:00:00 ne doit pas être enregistré."""
    athlete = {"lastname": "Test", "number": "1", "time": "01:00:00", "timeNat": "00:00:00"}
    r = _parse_athlete(athlete, {"Nat": "swim"}, "http://x", "E", "triathlon-s", None)
    assert r.swim_time == ""


def test_detect_event_type():
    assert _detect_event_type("Triathlon M") == "triathlon-m"
    assert _detect_event_type("Triathlon S") == "triathlon-s"
    assert _detect_event_type("Duathlon Sprint") == "duathlon-s"
    assert _detect_event_type("Aquathlon") == "aquathlon"
    assert _detect_event_type("Triathlon") == "triathlon"


# ---------------------------------------------------------------------------
# _parse_url — supporte la forme query ET la forme front /result/{id}/{index}
# ---------------------------------------------------------------------------

def test_parse_url_query_form():
    assert _parse_url("https://www.prolivesport.fr/index.php?eventId=1082&race=S") == ("1082", "S")


def test_parse_url_query_form_no_race():
    assert _parse_url("https://www.prolivesport.fr/index.php?eventId=1082") == ("1082", "")


def test_parse_url_path_form():
    """Forme front : /result/{eventId}/{raceIndex}."""
    assert _parse_url("https://www.prolivesport.fr/result/1082/6") == ("1082", "6")


def test_parse_url_path_form_no_race():
    assert _parse_url("https://www.prolivesport.fr/result/1082") == ("1082", "")


def test_parse_url_missing_event_id_raises():
    with pytest.raises(ValueError):
        _parse_url("https://www.prolivesport.fr/")


# ---------------------------------------------------------------------------
# _resolve_race — un token numérique est un index positionnel dans raceList
# ---------------------------------------------------------------------------

def test_resolve_race_by_positional_index():
    assert _resolve_race("6", RACES) == "S"   # index 6 (0-based) = "S"


def test_resolve_race_by_code():
    assert _resolve_race("S", RACES) == "S"


def test_resolve_race_empty_uses_first():
    assert _resolve_race("", RACES) == "PO-PU"


def test_resolve_race_index_out_of_range_raises():
    with pytest.raises(ValueError):
        _resolve_race("99", RACES)


# ---------------------------------------------------------------------------
# _derive_status — lit dsq / dnf / time (le champ dns de l'API n'est pas fiable)
# ---------------------------------------------------------------------------

def test_derive_status_dsq():
    assert _derive_status({"dsq": "O", "time": "01:59:00"}) == "DSQ"


def test_derive_status_dnf():
    assert _derive_status({"dnf": "O", "time": ""}) == "DNF"


def test_derive_status_finisher_with_time():
    # Cas réel : dns="O" alors que l'athlète a fini → finisher (pas DNS).
    assert _derive_status({"time": "01:59:00", "dns": "O"}) == "finisher"


def test_derive_status_dns_no_time():
    assert _derive_status({"time": "", "dns": "O"}) == "DNS"


def test_derive_status_dns_zero_time():
    assert _derive_status({"time": "00:00:00"}) == "DNS"


def test_derive_status_dsq_takes_precedence_over_dnf():
    assert _derive_status({"dsq": "O", "dnf": "O", "time": ""}) == "DSQ"


# ---------------------------------------------------------------------------
# Constantes de statut + champ ScrapedResult.status
# ---------------------------------------------------------------------------

def test_status_constants_values():
    from app.scrapers.base import (
        STATUS_DNF,
        STATUS_DNS,
        STATUS_DSQ,
        STATUS_FINISHER,
    )
    assert STATUS_FINISHER == "finisher"
    assert STATUS_DNF == "DNF"
    assert STATUS_DNS == "DNS"
    assert STATUS_DSQ == "DSQ"


def test_scraped_result_status_defaults_empty():
    from app.scrapers.base import ScrapedResult
    r = ScrapedResult(source_url="http://x", provider="prolivesport")
    assert r.status == ""
