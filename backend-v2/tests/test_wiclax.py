"""
Tests unitaires pour scrapers/wiclax.py (sans réseau).

Couvre les helpers purs de parsing XML : extraction bib/nom, parsing d'un
compétiteur (formats Competitor et ChronoSmetron E/R), mapping des segments
(<Segments>) vers les index sN, et remplissage des splits depuis un <R>.
"""
import xml.etree.ElementTree as ET

from app.scrapers.base import ScrapedResult
from app.scrapers.wiclax import (
    _build_split_indices,
    _detect_event_type,
    _fill_er_splits,
    _get_competitor_bib,
    _get_competitor_fullname,
    _parse_competitor,
)


def _el(xml: str) -> ET.Element:
    return ET.fromstring(xml)


def test_detect_event_type():
    assert _detect_event_type("Triathlon L") == "triathlon-l"
    assert _detect_event_type("Triathlon M") == "triathlon-m"
    assert _detect_event_type("Sprint de la Roche") == "triathlon-s"
    assert _detect_event_type("Ironman France") == "triathlon-xl"
    assert _detect_event_type("Duathlon") == "duathlon"


def test_get_competitor_bib():
    assert _get_competitor_bib(_el('<Competitor Bib="42"/>')) == "42"
    assert _get_competitor_bib(_el('<E d="6159"/>')) == "6159"
    assert _get_competitor_bib(_el("<E/>")) == ""


def test_get_competitor_fullname_competitor_format():
    comp = _el('<Competitor Name="DUPONT" FirstName="Jean"/>')
    assert _get_competitor_fullname(comp) == "Jean DUPONT"


def test_get_competitor_fullname_e_format_nbsp():
    """Format E : nom dans n=, espace insécable normalisé."""
    comp = _el('<E n="Jean DUPONT"/>')
    assert _get_competitor_fullname(comp) == "Jean DUPONT"


def test_parse_competitor_standard_format():
    comp = _el(
        '<Competitor Bib="42" Name="DUPONT" FirstName="Jean" Club="TCN" '
        'Category="S3H" Gender="M" Rank="5" Time="01:59:00"/>'
    )
    r = _parse_competitor(comp, "http://x", "Triathlon de la Roche", "triathlon-m")
    assert r.bib_number == "42"
    assert r.athlete_name == "DUPONT"
    assert r.athlete_firstname == "Jean"
    assert r.club == "TCN"
    assert r.category == "S3H"
    assert r.gender == "M"
    assert r.rank_overall == 5
    assert r.total_time == "01:59:00"
    assert r.event_type == "triathlon-m"
    assert r.is_relay is False


def test_parse_competitor_e_format_with_parcours():
    """Format ChronoSmetron E : p= donne la discipline (prioritaire)."""
    comp = _el('<E d="6159" c="TCN" ca="S3H" x="M" v="3" p="Triathlon L"/>')
    r = _parse_competitor(comp, "http://x", "Event générique", "triathlon")
    assert r.bib_number == "6159"
    assert r.club == "TCN"
    assert r.category == "S3H"
    assert r.gender == "M"
    assert r.rank_overall == 3
    assert r.event_type == "triathlon-l"   # détecté depuis p="Triathlon L"
    assert r.is_relay is False


def test_parse_competitor_relay_detected():
    comp = _el('<E d="10" p="Relais S"/>')
    r = _parse_competitor(comp, "http://x", "Event", "triathlon")
    assert r.is_relay is True


def test_build_split_indices_and_fill():
    """<Segments> → index sN, puis remplissage d'un <R> via ces index."""
    root = _el(
        "<Root><Segments>"
        '<S disc="5" ptg1="-999" ptg2="100"/>'   # 0 swim (finit où T1 commence)
        '<S trans="1" ptg1="100" ptg2="110"/>'   # 1 T1
        '<S disc="0" ptg1="110" ptg2="200"/>'    # 2 bike (T1_end → T2_start)
        '<S trans="1" ptg1="200" ptg2="210"/>'   # 3 T2
        '<S disc="6" ptg1="210" ptg2="999"/>'    # 4 run (T2_end → arrivée)
        "</Segments></Root>"
    )
    idx = _build_split_indices(root)
    assert idx == {"t1": 1, "t2": 3, "swim": 0, "bike": 2, "run": 4}

    r = ScrapedResult(source_url="http://x", provider="wiclax")
    result_elem = _el(
        '<R s0="00:11:00" s1="00:01:00" s2="01:05:00" s3="00:00:50" s4="00:41:10"/>'
    )
    _fill_er_splits(result_elem, r, idx)
    assert r.swim_time == "00:11:00"
    assert r.t1_time == "00:01:00"
    assert r.bike_time == "01:05:00"
    assert r.t2_time == "00:00:50"
    assert r.run_time == "00:41:10"


def test_fill_er_splits_fallback_no_segments():
    """Sans <Segments>, fallback sur s2/s3/s4/s5/s10."""
    r = ScrapedResult(source_url="http://x", provider="wiclax")
    result_elem = _el(
        '<R s2="00:11:00" s3="00:01:00" s4="01:05:00" s5="00:00:50" s10="00:41:10"/>'
    )
    _fill_er_splits(result_elem, r, {})
    assert r.swim_time == "00:11:00"
    assert r.t1_time == "00:01:00"
    assert r.bike_time == "01:05:00"
    assert r.t2_time == "00:00:50"
    assert r.run_time == "00:41:10"
