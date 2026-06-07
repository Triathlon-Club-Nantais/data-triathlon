"""
Tests unitaires pour scrapers/prolivesport.py.

Cas couverts :
- _parse_url : tous les formats d'URL supportés + erreur sur page de liste
- _detect_event_type : codes courts, wildcard, fallback par distance
- _parse_athlete : normalisation prénom ".", détection relais, athlète individuel
- scrape_event_all : filtre DNS sentinel, relais détectés
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import date

from scrapers.prolivesport import (
    _parse_url,
    _detect_event_type,
    _parse_athlete,
)
from scrapers.base import ScrapedResult


# ---------------------------------------------------------------------------
# _parse_url
# ---------------------------------------------------------------------------

def test_parse_url_legacy_with_race():
    eid, race, search = _parse_url(
        "https://www.prolivesport.fr/index.php?chap=event&sub=liveV3&eventId=1079&race=M*"
    )
    assert eid == "1079"
    assert race == "M*"
    assert search == ""


def test_parse_url_legacy_no_race():
    eid, race, _ = _parse_url(
        "https://www.prolivesport.fr/index.php?chap=event&sub=liveV3&eventId=1082"
    )
    assert eid == "1082"
    assert race == ""


def test_parse_url_modern_id_only():
    eid, race, _ = _parse_url("https://www.prolivesport.fr/result/1079")
    assert eid == "1079"
    assert race == ""


def test_parse_url_modern_with_race():
    eid, race, _ = _parse_url("https://www.prolivesport.fr/result/1079/M")
    assert eid == "1079"
    assert race == "M"


def test_parse_url_chrono_path():
    """Autre format de chemin contenant l'ID numérique."""
    eid, _, _ = _parse_url("https://www.prolivesport.fr/chrono/1082")
    assert eid == "1082"


def test_parse_url_id_query_param():
    """Paramètre id= au lieu de eventId=."""
    eid, _, _ = _parse_url("https://www.prolivesport.fr/event?id=999")
    assert eid == "999"


def test_parse_url_listing_page_raises():
    """Page de liste sans ID numérique → ValueError explicite."""
    with pytest.raises(ValueError, match="page de liste"):
        _parse_url("https://www.prolivesport.fr/fftri/grand-prix-duathlon")


def test_parse_url_with_search():
    eid, race, search = _parse_url(
        "https://www.prolivesport.fr/index.php?eventId=1079&race=M&search=DUPONT"
    )
    assert eid == "1079"
    assert search == "DUPONT"


# ---------------------------------------------------------------------------
# _detect_event_type
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("race,expected", [
    ("S",    "triathlon-s"),
    ("XS",   "triathlon-s"),
    ("M",    "triathlon-m"),
    ("M*",   "triathlon-m"),   # wildcard stripped
    ("L",    "triathlon-l"),
    ("XL",   "triathlon-l"),
    ("XXL",  "triathlon-l"),
    ("Triathlon M", "triathlon-m"),
    ("Triathlon S", "triathlon-s"),
    ("Duathlon S",  "duathlon-s"),
])
def test_detect_event_type_known(race, expected):
    assert _detect_event_type(race) == expected


@pytest.mark.parametrize("race,distance,expected", [
    ("TRGP",      "25.5",  "triathlon-s"),   # Grand Prix relay, sprint distance
    ("Challenge", "49.5",  "triathlon-m"),   # Olympic
    ("TREP",      "90.0",  "triathlon-l"),   # Half
    ("SUPP",      "999",   "triathlon-xl"),  # Very long
    ("UNKNOWN",   "12.0",  "triathlon-s"),   # Youth/XS
    ("UNKNOWN",   "",      "triathlon"),     # No distance → fallback
])
def test_detect_event_type_distance_fallback(race, distance, expected):
    assert _detect_event_type(race, distance) == expected


# ---------------------------------------------------------------------------
# _parse_athlete
# ---------------------------------------------------------------------------

def _make_athlete(**kwargs) -> dict:
    base = {
        "lastname": "DUPONT",
        "firstname": "Jean",
        "number": "42",
        "club": "TRI CLUB NANTAIS",
        "categoryRef": "SE",
        "category": "Senior",
        "sex": "M",
        "rank": "5",
        "rankSex": "4",
        "rankCat": "3",
        "time": "01:30:00",
        "dns": "O",
        "dnf": "N",
    }
    base.update(kwargs)
    return base


def test_parse_athlete_standard():
    r = _parse_athlete(_make_athlete(), {}, "http://x", "Test 2025", "triathlon-s", date(2025, 6, 1))
    assert r.athlete_name == "DUPONT"
    assert r.athlete_firstname == "Jean"
    assert r.club == "TRI CLUB NANTAIS"
    assert r.is_relay is False
    assert r.total_time == "01:30:00"
    assert r.rank_overall == 5


def test_parse_athlete_firstname_dot_normalized():
    """ProLiveSport utilise '.' comme prénom factice pour les relais → doit être vide."""
    r = _parse_athlete(_make_athlete(firstname="."), {}, "http://x", "Test", "triathlon-s", None)
    assert r.athlete_firstname == ""


def test_parse_athlete_firstname_dash_normalized():
    r = _parse_athlete(_make_athlete(firstname="-"), {}, "http://x", "Test", "triathlon-s", None)
    assert r.athlete_firstname == ""


def test_parse_athlete_relay_from_category_ref():
    """categoryRef='R' → is_relay=True."""
    r = _parse_athlete(_make_athlete(categoryRef="R", category="Relay"), {}, "http://x", "Test", "triathlon-s", None)
    assert r.is_relay is True


def test_parse_athlete_relay_from_category_label():
    """category='Relay' (majuscules différentes) → is_relay=True."""
    r = _parse_athlete(_make_athlete(categoryRef="REL", category="relay"), {}, "http://x", "Test", "triathlon-s", None)
    assert r.is_relay is True


def test_parse_athlete_individual_not_relay():
    r = _parse_athlete(_make_athlete(categoryRef="SE", category="Senior"), {}, "http://x", "Test", "triathlon-s", None)
    assert r.is_relay is False


# ---------------------------------------------------------------------------
# scrape_event_all — filtre DNS sentinel (avec mock HTTP)
# ---------------------------------------------------------------------------

def _mock_pls_client(athletes: list[dict], event_name="Test 2025",
                     event_date="2025-06-01", races=None):
    """Retourne un mock httpx.Client pour scrape_event_all."""
    if races is None:
        races = [{"race": "S", "distance": "25.5"}]

    def mock_get(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if "/event/detail/" in url:
            resp.json.return_value = {"result": [{"eventName": event_name, "eventDateStart": event_date}]}
        elif "/result/raceList/" in url:
            resp.json.return_value = {"result": races}
        elif "/result/indiv/" in url:
            resp.json.return_value = {"success": True, "result": athletes}
        elif "/result/splitDetail/" in url:
            resp.json.return_value = {"result": []}
        return resp

    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.get = mock_get
    return client


def test_scrape_event_all_excludes_dns_sentinel():
    """Athlètes avec rank=99992 (non-partant sentinel) exclus de l'import."""
    athletes = [
        _make_athlete(number="1", rank="1",   dns="O"),   # finisher
        _make_athlete(number="2", rank="2",   dns="O"),   # finisher
        _make_athlete(number="3", rank="99992", dns="N", time="00:00:00"),  # DNS
    ]
    with patch("scrapers.prolivesport.httpx.Client", return_value=_mock_pls_client(athletes)):
        from scrapers.prolivesport import scrape_event_all
        results = scrape_event_all("https://www.prolivesport.fr/result/1000")

    assert len(results) == 2
    bibs = {r.bib_number for r in results}
    assert "3" not in bibs


def test_scrape_event_all_relay_detected():
    """Athlètes avec categoryRef='R' → is_relay=True dans les résultats."""
    athletes = [
        _make_athlete(number="10", categoryRef="SE", category="Senior"),
        _make_athlete(number="20", categoryRef="R",  category="Relay", firstname="."),
    ]
    with patch("scrapers.prolivesport.httpx.Client", return_value=_mock_pls_client(athletes)):
        from scrapers.prolivesport import scrape_event_all
        results = scrape_event_all("https://www.prolivesport.fr/result/1000")

    by_bib = {r.bib_number: r for r in results}
    assert by_bib["10"].is_relay is False
    assert by_bib["20"].is_relay is True
    assert by_bib["20"].athlete_firstname == ""


def test_scrape_event_all_imports_all_races_when_no_race():
    """Sans race dans l'URL, toutes les races sont importées."""
    athletes_s  = [_make_athlete(number=str(i), rank=str(i)) for i in range(1, 4)]
    athletes_m  = [_make_athlete(number=str(i), rank=str(i)) for i in range(10, 13)]
    races = [{"race": "S", "distance": "25.5"}, {"race": "M", "distance": "51.5"}]

    call_count = {"n": 0}
    def mock_get(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if "/event/detail/" in url:
            resp.json.return_value = {"result": [{"eventName": "Test", "eventDateStart": "2025-06-01"}]}
        elif "/result/raceList/" in url:
            resp.json.return_value = {"result": races}
        elif "/result/indiv/" in url:
            call_count["n"] += 1
            batch = athletes_s if "/S/" in url else athletes_m
            resp.json.return_value = {"success": True, "result": batch}
        elif "/result/splitDetail/" in url:
            resp.json.return_value = {"result": []}
        return resp

    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.get = mock_get

    with patch("scrapers.prolivesport.httpx.Client", return_value=client):
        from scrapers.prolivesport import scrape_event_all
        results = scrape_event_all("https://www.prolivesport.fr/result/1000")

    assert call_count["n"] == 2          # deux appels indiv (S + M)
    assert len(results) == 6             # 3 + 3
