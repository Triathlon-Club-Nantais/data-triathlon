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
    _competitor_status,
    _detect_event_type,
    _fill_er_splits,
    _get_competitor_bib,
    _get_competitor_fullname,
    _parse_competitor,
    scrape_event_all,
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


# --- Statut explicite + hygiène non-finisher ---------------------------------


def test_parse_competitor_explicit_status_dnf():
    """Attribut Status="Abandon" → DNF + hygiène (temps/rangs purgés)."""
    comp = _el(
        '<Competitor Bib="5" Name="DUPONT" FirstName="Jean" '
        'Status="Abandon" Time="01:00:00" Rank="3"/>'
    )
    r = _parse_competitor(comp, "http://x", "Triathlon", "triathlon-s")
    assert r.status == "DNF"
    assert r.total_time == ""
    assert r.rank_overall is None


def test_parse_competitor_no_status_is_empty():
    """Sans marqueur → status="" et temps conservé (heuristique infra)."""
    comp = _el(
        '<Competitor Bib="5" Name="DUPONT" FirstName="Jean" Time="01:00:00" Rank="3"/>'
    )
    r = _parse_competitor(comp, "http://x", "Triathlon", "triathlon-s")
    assert r.status == ""
    assert r.total_time == "01:00:00"
    assert r.rank_overall == 3


def test_competitor_status_real_np_flag_is_dns():
    """Vrai signal Wiclax : flag binaire np="1" sur le <E> → DNS."""
    assert _competitor_status(_el('<E d="7" np="1"/>')) == "DNS"
    assert _competitor_status(_el('<E d="7" np="0"/>')) == ""
    assert _competitor_status(_el('<E d="7"/>')) == ""


def test_parse_competitor_np_flag_dns_hygiene():
    """np="1" sur un <E> → DNS + hygiène (temps/rangs purgés)."""
    comp = _el('<E d="7" v="12" x="M" ca="S3H" Time="01:00:00" np="1"/>')
    r = _parse_competitor(comp, "http://x", "Triathlon", "triathlon-s")
    assert r.status == "DNS"
    assert r.total_time == ""
    assert r.rank_overall is None
    assert r.rank_category is None
    assert r.rank_gender is None


def _event_xml(competitors: str, results: str) -> str:
    """Construit un .clax minimal au format ChronoSmetron E/R."""
    return (
        '<Root><Event Name="Triathlon Test" dt1="2026-06-08"/>'
        f"<Competitors>{competitors}</Competitors>"
        f"<Results>{results}</Results></Root>"
    )


def test_scrape_event_all_er_status_label_in_time_dnf(monkeypatch):
    """Un <R t="Abandon"> (libellé logé dans l'attribut temps) → DNF + hygiène."""
    xml = _event_xml(
        competitors='<E d="11" n="Jean DUPONT" x="M" ca="S3H" v="2"/>',
        results='<R d="11" t="Abandon"/>',
    )
    root = ET.fromstring(xml)
    monkeypatch.setattr(
        "app.scrapers.wiclax._fetch_clax",
        lambda _url: (root, "http://x", "Triathlon Test", "triathlon-s", None),
    )
    results = scrape_event_all("http://x")
    by_bib = {r.bib_number: r for r in results}
    assert by_bib["11"].status == "DNF"
    assert by_bib["11"].total_time == ""
    assert by_bib["11"].rank_overall is None


def test_scrape_event_all_er_status_label_in_time_dsq(monkeypatch):
    """Un <R t="Disqualifié"> → DSQ + hygiène."""
    xml = _event_xml(
        competitors='<E d="12" n="Marie BETA" x="F" ca="S2F" v="4"/>',
        results='<R d="12" t="Disqualifié"/>',
    )
    root = ET.fromstring(xml)
    monkeypatch.setattr(
        "app.scrapers.wiclax._fetch_clax",
        lambda _url: (root, "http://x", "Triathlon Test", "triathlon-s", None),
    )
    results = scrape_event_all("http://x")
    by_bib = {r.bib_number: r for r in results}
    assert by_bib["12"].status == "DSQ"
    assert by_bib["12"].total_time == ""
    assert by_bib["12"].rank_overall is None


def test_scrape_event_all_er_np_flag_dns(monkeypatch):
    """np="1" sur l'<E> dans le flux épreuve → DNS, même sans <R>."""
    xml = _event_xml(
        competitors='<E d="13" n="Paul GAMMA" x="M" ca="V1H" v="9" np="1"/>',
        results="",
    )
    root = ET.fromstring(xml)
    monkeypatch.setattr(
        "app.scrapers.wiclax._fetch_clax",
        lambda _url: (root, "http://x", "Triathlon Test", "triathlon-s", None),
    )
    results = scrape_event_all("http://x")
    by_bib = {r.bib_number: r for r in results}
    assert by_bib["13"].status == "DNS"
    assert by_bib["13"].total_time == ""
    assert by_bib["13"].rank_overall is None


def test_scrape_event_all_er_finisher_unaffected(monkeypatch):
    """Un finisher normal (R t=temps) conserve temps/rang, status vide."""
    xml = _event_xml(
        competitors='<E d="14" n="Luc DELTA" x="M" ca="S3H" v="1"/>',
        results='<R d="14" t="01:02:03"/>',
    )
    root = ET.fromstring(xml)
    monkeypatch.setattr(
        "app.scrapers.wiclax._fetch_clax",
        lambda _url: (root, "http://x", "Triathlon Test", "triathlon-s", None),
    )
    results = scrape_event_all("http://x")
    by_bib = {r.bib_number: r for r in results}
    assert by_bib["14"].status == ""
    assert by_bib["14"].total_time == "01:02:03"
    assert by_bib["14"].rank_overall == 1
