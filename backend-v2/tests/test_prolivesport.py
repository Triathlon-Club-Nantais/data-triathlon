"""
Tests unitaires pour scrapers/prolivesport.py (sans réseau).

Couvre les helpers purs : mapping des splits (champ→rôle), parsing d'un athlète
depuis le dict JSON de l'API, et détection du type d'épreuve.
"""
from app.scrapers.prolivesport import (
    _build_split_map,
    _detect_event_type,
    _parse_athlete,
)


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
