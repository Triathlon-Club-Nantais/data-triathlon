"""
Tests unitaires pour scrapers/wiclax.py (sans réseau).

Couvre les helpers purs de parsing XML : extraction bib/nom, parsing d'un
compétiteur (formats Competitor et ChronoSmetron E/R), mapping des segments
(<Segments>) vers les index sN, et remplissage des splits depuis un <R>.
"""
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
import pytest

from app.scrapers import registry
from app.scrapers.base import ScrapedResult
from app.scrapers.wiclax import (
    _competitor_status,
    _detect_event_type,
    _fill_er_splits,
    _find_glive_url,
    _find_wiclax_link,
    _get_competitor_bib,
    _get_competitor_fullname,
    _parcours_split_map,
    _parse_competitor,
    _resolve_to_wiclax_url,
    _segment_chain,
    scrape_event_all,
)
from app.services.mapping import build_splits

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(nom: str) -> str:
    return (FIXTURES / nom).read_text(encoding="utf-8")


def _el(xml: str) -> ET.Element:
    return ET.fromstring(xml)


def _segments(s_elems: str) -> list[ET.Element]:
    """Liste des <S> d'un bloc <Segments> construit à la volée."""
    return list(ET.fromstring(f"<Segments>{s_elems}</Segments>"))


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
    """Format ChronoSmetron E : p= donne la discipline (prioritaire).

    Le dossard affiché est `v` (dossard réel) et non `d` (id interne/numéroté par
    vague). Le rang n'est PAS porté par `v` : ChronoSmetron ne stocke pas le rang
    dans le fichier (il est calculé au tri par scrape_event_all)."""
    comp = _el('<E d="6159" c="TCN" ca="S3H" x="M" v="3" p="Triathlon L"/>')
    r = _parse_competitor(comp, "http://x", "Event générique", "triathlon")
    assert r.bib_number == "3"             # v = dossard réel (pas d=6159)
    assert r.club == "TCN"
    assert r.category == "S3H"
    assert r.gender == "M"
    assert r.rank_overall is None          # rang absent du <E> → calculé au tri
    assert r.event_type == "triathlon-l"   # détecté depuis p="Triathlon L"
    assert r.is_relay is False


def test_parse_competitor_relay_detected():
    comp = _el('<E d="10" p="Relais S"/>')
    r = _parse_competitor(comp, "http://x", "Event", "triathlon")
    assert r.is_relay is True


def test_parse_competitor_event_name_qualified_by_parcours():
    """Issue #21 : le nom de course est qualifié par le parcours `p`.

    Deux parcours de même type (S-Open / S-Open Femmes → triathlon-s) doivent
    produire des noms de course distincts, sinon ils fusionnent en une seule
    Course (collisions de dossards → participants manquants, rangs dupliqués)."""
    comp = _el('<E d="5001" x="F" ca="S2F" v="12" p="S-Open Femmes"/>')
    r = _parse_competitor(comp, "http://x", "Triathlon de Vertou 2026", "triathlon")
    assert r.event_type == "triathlon-s"
    assert r.event_name == "Triathlon de Vertou 2026 - S-Open Femmes"


def test_parse_competitor_no_parcours_keeps_root_name():
    """Sans parcours `p`, le nom de course reste le nom racine de l'épreuve."""
    comp = _el('<E d="9999" n="ASPTT NANTES TRI"/>')
    r = _parse_competitor(comp, "http://x", "Triathlon de Vertou 2026", "triathlon")
    assert r.event_name == "Triathlon de Vertou 2026"


def test_scrape_event_all_same_type_parcours_distinct_courses(monkeypatch):
    """Issue #21 : deux parcours de même type avec dossards en collision restent
    des épreuves distinctes (noms de course différents) au lieu de fusionner."""
    xml = _event_xml(
        competitors=(
            '<E d="5001" n="Alice WIN" x="F" ca="S2F" v="1" p="S-Open Femmes"/>'
            '<E d="6001" n="Bob RUN" x="M" ca="S3M" v="1" p="S-Open"/>'
        ),
        results=(
            '<R d="5001" t="01:05:00"/>'
            '<R d="6001" t="00:58:00"/>'
        ),
    )
    root = ET.fromstring(xml)
    monkeypatch.setattr(
        "app.scrapers.wiclax._fetch_clax",
        lambda _url: (root, "http://x", "Triathlon de Vertou 2026", "triathlon", None),
    )
    results = scrape_event_all("http://x")
    by_name = {r.event_name for r in results}
    # Même dossard v="1" dans deux parcours → deux noms de course distincts,
    # sinon la déduplication (course_id, bib) fait disparaître un participant.
    assert by_name == {
        "Triathlon de Vertou 2026 - S-Open Femmes",
        "Triathlon de Vertou 2026 - S-Open",
    }
    # Chaque parcours a son propre 1er (rang calculé au tri par parcours).
    assert all(r.rank_overall == 1 for r in results)


# --- Chaîne de segments par parcours (détection via les disc) ----------------


def test_segment_chain_triathlon_skips_laps():
    """Le chemin le plus court (par arête) écarte les tours, garde les totaux."""
    segs = _segments(
        '<S disc="5" ptg1="-999" ptg2="9" pcs="Tri M"/>'   # 0 nat tour 1
        '<S disc="5" ptg1="9" ptg2="0" pcs="Tri M"/>'      # 1 nat tour 2
        '<S disc="5" ptg1="-999" ptg2="0" pcs="Tri M"/>'   # 2 natation TOTAL
        '<S trans="1" ptg1="0" ptg2="1" pcs="Tri M"/>'     # 3 T1
        '<S disc="0" ptg1="1" ptg2="2" pcs="Tri M"/>'      # 4 vélo
        '<S trans="1" ptg1="2" ptg2="3" pcs="Tri M"/>'     # 5 T2
        '<S disc="6" ptg1="3" ptg2="4" pcs="Tri M"/>'      # 6 cap tour 1
        '<S disc="6" ptg1="4" ptg2="999" pcs="Tri M"/>'    # 7 cap tour 2
        '<S disc="6" ptg1="3" ptg2="999" pcs="Tri M"/>'    # 8 course à pied TOTAL
    )
    assert _segment_chain(segs, "Tri M") == [
        (2, "swim"), (3, "transition"), (4, "bike"), (5, "transition"), (8, "run"),
    ]


def test_segment_chain_youth_run_bike_run():
    """Course jeune (sans transition) : course à pied → vélo → course à pied."""
    segs = _segments(
        '<S disc="6" ptg1="-999" ptg2="1" pcs="10-13 Ans"/>'  # 0 CaP1
        '<S disc="0" ptg1="1" ptg2="3" pcs="10-13 Ans"/>'     # 1 Velo
        '<S disc="6" ptg1="3" ptg2="999" pcs="10-13 Ans"/>'   # 2 CaP2
    )
    assert _segment_chain(segs, "10-13 Ans") == [
        (0, "run"), (1, "bike"), (2, "run"),
    ]


def test_segment_chain_filters_by_parcours():
    """Un segment non rattaché au parcours (pcs) est ignoré."""
    segs = _segments(
        '<S disc="6" ptg1="-999" ptg2="1" pcs="10-13 Ans"/>'  # 0 CaP1 jeune
        '<S disc="0" ptg1="1" ptg2="3" pcs="10-13 Ans"/>'     # 1 Velo jeune
        '<S disc="6" ptg1="3" ptg2="999" pcs="10-13 Ans"/>'   # 2 CaP2 jeune
        '<S disc="5" ptg1="-999" ptg2="999" pcs="Triathlon M"/>'  # 3 autre parcours
    )
    assert _segment_chain(segs, "10-13 Ans") == [
        (0, "run"), (1, "bike"), (2, "run"),
    ]


def test_parcours_split_map_triathlon():
    """swim/bike/run → mapping triathlon, pas de surcharge d'event_type."""
    segs = _segments(
        '<S disc="5" ptg1="-999" ptg2="0" pcs="Tri M"/>'   # 0 natation
        '<S trans="1" ptg1="0" ptg2="1" pcs="Tri M"/>'     # 1 T1
        '<S disc="0" ptg1="1" ptg2="2" pcs="Tri M"/>'      # 2 vélo
        '<S trans="1" ptg1="2" ptg2="3" pcs="Tri M"/>'     # 3 T2
        '<S disc="6" ptg1="3" ptg2="999" pcs="Tri M"/>'    # 4 course à pied
    )
    split_map, override = _parcours_split_map(segs, "Tri M")
    assert split_map == {"swim": 0, "t1": 1, "bike": 2, "t2": 3, "run": 4}
    assert override is None


def test_parcours_split_map_youth_is_duathlon():
    """course à pied → vélo → course à pied : run1→slot swim, run2→slot run,
    surcharge event_type=duathlon (→ splits course1/bike/course2)."""
    segs = _segments(
        '<S disc="6" ptg1="-999" ptg2="1" pcs="10-13 Ans"/>'  # 0 CaP1
        '<S disc="0" ptg1="1" ptg2="3" pcs="10-13 Ans"/>'     # 1 Velo
        '<S disc="6" ptg1="3" ptg2="999" pcs="10-13 Ans"/>'   # 2 CaP2
    )
    split_map, override = _parcours_split_map(segs, "10-13 Ans")
    assert split_map == {"swim": 0, "bike": 1, "run": 2}
    assert override == "duathlon"

    r = ScrapedResult(source_url="http://x", provider="wiclax")
    result_elem = _el('<R s0="00:03:06" s1="00:07:33" s2="00:02:42"/>')
    _fill_er_splits(result_elem, r, split_map)
    assert r.swim_time == "00:03:06"  # CaP1
    assert r.bike_time == "00:07:33"  # Velo
    assert r.run_time == "00:02:42"   # CaP2


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
    by_bib = {r.bib_number: r for r in results}  # bib affiché = v (dossard réel)
    assert by_bib["2"].status == "DNF"
    assert by_bib["2"].total_time == ""
    assert by_bib["2"].rank_overall is None


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
    by_bib = {r.bib_number: r for r in results}  # bib affiché = v (dossard réel)
    assert by_bib["4"].status == "DSQ"
    assert by_bib["4"].total_time == ""
    assert by_bib["4"].rank_overall is None


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
    by_bib = {r.bib_number: r for r in results}  # bib affiché = v (dossard réel)
    assert by_bib["9"].status == "DNS"
    assert by_bib["9"].total_time == ""
    assert by_bib["9"].rank_overall is None


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
    by_bib = {r.bib_number: r for r in results}  # bib affiché = v (dossard réel)
    assert by_bib["1"].status == ""
    assert by_bib["1"].total_time == "01:02:03"
    assert by_bib["1"].rank_overall == 1  # seul finisher du parcours → 1er au tri


def test_scrape_event_all_youth_run_bike_run_splits(monkeypatch):
    """Régression (Triathlon de la Roche) : course jeune run-bike-run dans le même
    .clax que le triathlon. Les segments sont scopés par parcours (pcs) → le jeune
    lit ses propres sN (s5/s6/s7), est reclassé duathlon, et ses splits sortent en
    course1/bike/course2. Le triathlon adulte reste inchangé."""
    segments = (
        '<S disc="5" ptg1="-999" ptg2="0" pcs="Triathlon M"/>'   # s0 natation
        '<S trans="1" ptg1="0" ptg2="1" pcs="Triathlon M"/>'     # s1 T1
        '<S disc="0" ptg1="1" ptg2="2" pcs="Triathlon M"/>'      # s2 vélo
        '<S trans="1" ptg1="2" ptg2="3" pcs="Triathlon M"/>'     # s3 T2
        '<S disc="6" ptg1="3" ptg2="999" pcs="Triathlon M"/>'    # s4 course à pied
        '<S disc="6" ptg1="-999" ptg2="1" pcs="10-13 Ans"/>'     # s5 CaP1
        '<S disc="0" ptg1="1" ptg2="3" pcs="10-13 Ans"/>'        # s6 Velo
        '<S disc="6" ptg1="3" ptg2="999" pcs="10-13 Ans"/>'      # s7 CaP2
    )
    competitors = (
        '<E d="1" n="Jean ADULTE" x="M" ca="S3M" v="10" p="Triathlon M"/>'
        '<E d="2" n="Paul JOUBERT" x="M" ca="PuM" v="95" p="10-13 Ans"/>'
    )
    results = (
        '<R d="1" t="02:00:00" s0="00:25:00" s1="00:02:00" '
        's2="01:00:00" s3="00:01:00" s4="00:32:00"/>'
        '<R d="2" t="00:13:23" s5="00:03:06" s6="00:07:33" s7="00:02:42"/>'
    )
    xml = (
        '<Root><Event Name="Triathlon de la Roche" dt1="2026-05-24"/>'
        f"<Segments>{segments}</Segments>"
        f"<Competitors>{competitors}</Competitors>"
        f"<Results>{results}</Results></Root>"
    )
    root = ET.fromstring(xml)
    monkeypatch.setattr(
        "app.scrapers.wiclax._fetch_clax",
        lambda _url: (root, "http://x", "Triathlon de la Roche", "triathlon", None),
    )
    by_bib = {r.bib_number: r for r in scrape_event_all("http://x")}

    adulte = by_bib["10"]
    assert adulte.event_type == "triathlon-m"
    assert adulte.swim_time == "00:25:00"
    assert adulte.bike_time == "01:00:00"
    assert adulte.run_time == "00:32:00"
    assert build_splits(adulte) == {
        "swim": "00:25:00", "t1": "00:02:00", "bike": "01:00:00",
        "t2": "00:01:00", "run": "00:32:00",
    }

    paul = by_bib["95"]
    assert paul.total_time == "00:13:23"
    assert paul.event_type == "duathlon"
    assert paul.swim_time == "00:03:06"  # CaP1
    assert paul.bike_time == "00:07:33"  # Velo
    assert paul.run_time == "00:02:42"   # CaP2
    # Étiquetage final via le gabarit duathlon : course1 / bike / course2
    assert build_splits(paul) == {
        "course1": "00:03:06", "bike": "00:07:33", "course2": "00:02:42",
    }


def test_scrape_event_all_er_ranks_computed_by_time(monkeypatch):
    """Régression : le rang général est calculé au TRI par temps, pas lu dans `v`.

    Reproduit le cas réel (Triathlon de la Roche) : `v` = dossard réel, `d` = id
    interne préfixé par vague. Avant correctif, le front affichait `v` comme rang
    (ex. 176 au lieu de 209) et `d` comme dossard (5176 au lieu de 176)."""
    xml = _event_xml(
        competitors=(
            '<E d="5150" n="Alice WIN" x="F" ca="S2F" v="150" p="Triathlon S"/>'
            '<E d="5099" n="Bob MID" x="M" ca="S3M" v="99" p="Triathlon S"/>'
            '<E d="5176" n="Thomas JARRIER" x="M" ca="S2M" v="176" p="Triathlon S"/>'
        ),
        results=(
            '<R d="5150" t="01:05:07"/>'
            '<R d="5099" t="01:20:00"/>'
            '<R d="5176" t="01:40:20"/>'
        ),
    )
    root = ET.fromstring(xml)
    monkeypatch.setattr(
        "app.scrapers.wiclax._fetch_clax",
        lambda _url: (root, "http://x", "Triathlon de la Roche", "triathlon-s", None),
    )
    by_bib = {r.bib_number: r for r in scrape_event_all("http://x")}
    # Dossard affiché = v (dossard réel), pas d (id interne 5xxx)
    assert set(by_bib) == {"150", "99", "176"}
    # Rangs au temps : WIN 1re, MID 2e, JARRIER 3e — indépendant de l'ordre des v
    assert by_bib["150"].rank_overall == 1
    assert by_bib["99"].rank_overall == 2
    assert by_bib["176"].rank_overall == 3
    # JARRIER : 2e homme (MID devant), seul S2M de son sexe → 1er catégorie
    assert by_bib["176"].rank_gender == 2
    assert by_bib["176"].rank_category == 1


# ---------------------------------------------------------------------------
# Date d'épreuve — le .clax ancien ne porte pas de date ISO
# ---------------------------------------------------------------------------


def test_clax_event_date_iso():
    """Fichier récent : `dt1` porte la date ISO (cas Roche-sur-Yon 2025)."""
    from datetime import date

    from app.scrapers.wiclax import _clax_event_date

    elem = _el(
        '<Epreuve nom="Triathlon de la Roche 2025" dt1="2025-05-18" '
        'dates="dimanche 18 mai 2025" date="45795"/>'
    )
    assert _clax_event_date(elem) == date(2025, 5, 18)


def test_clax_event_date_french_label_when_no_iso():
    """Fichier ancien : pas de `dt1`, mais `dates` en toutes lettres.

    Cas réels « Triathlon de Montreuil Juigné » (2025) et « Sud Vendée (Sam) »
    (2024), tous deux importés sans date faute de lire ce libellé.
    """
    from datetime import date

    from app.scrapers.wiclax import _clax_event_date

    elem = _el(
        '<Epreuve nom="Triathlon de Montreuil Juigné" '
        'dates="dimanche 1 juin 2025" date="45809"/>'
    )
    assert _clax_event_date(elem) == date(2025, 6, 1)


def test_clax_event_date_ignores_serial_number():
    """Le numéro de série `date` n'est pas une source de vérité.

    Il vaut la date saisie dans le logiciel, parfois fausse (Couëron : sérial
    au 2024-10-01, épreuve réellement courue le 2024-10-06). Sans date lisible,
    on préfère aucune date à une date inventée.
    """
    from app.scrapers.wiclax import _clax_event_date

    assert _clax_event_date(_el('<Epreuve nom="COUËRON DUATHLON" dates="" date="45566"/>')) is None


def test_clax_event_date_absent():
    from app.scrapers.wiclax import _clax_event_date

    assert _clax_event_date(_el('<Epreuve nom="X"/>')) is None


# ---------------------------------------------------------------------------
# Détection de provider (registre)
# ---------------------------------------------------------------------------


def test_registry_detecte_chronowest():
    """chronowest.fr est un déploiement Wiclax/G-Live, pas un moteur inconnu."""
    assert registry.detect_provider(
        "https://chronowest.fr/resultats/trail-des-2-ponts-2026/"
    ) == "wiclax"
    assert registry.detect_provider("https://chronowest.fr/trail-des-2-ponts-2026/") == "wiclax"


def test_registry_hosts_wiclax_existants_inchanges():
    """Non-régression : les hosts déjà supportés restent routés vers wiclax."""
    for url in (
        "https://chronosmetron.wiclax-results.com/Triathlon%20de%20la%20Roche%202026/",
        "https://www.chronosmetron.com/resultats/",
        "https://x.wiclax.com/G-Live/g-live.html?f=../E/e.clax",
    ):
        assert registry.detect_provider(url) == "wiclax", url


def test_registry_host_inconnu_reste_playwright():
    """L'allowlist reste explicite : pas de sniffing de contenu."""
    assert registry.detect_provider("https://exemple-inconnu.fr/resultats/") == "playwright"


# ---------------------------------------------------------------------------
# Résolution d'URL : page → iframe G-Live
# ---------------------------------------------------------------------------


def test_find_glive_url_apostrophe_non_tronquee():
    """Bug #35 : la regex `[^"\\']*` coupait le src à l'apostrophe de LOC'orrida."""
    src = _find_glive_url(
        _fixture("chronowest_shell_locorrida.html"),
        "https://chronowest.fr/resultats/locorrida-2026/",
    )
    assert src == (
        "https://chronowest.fr/wp-content/glive/g-live.html"
        "?f=/wp-content/glive-results/locorrida-2026/LOC'orrida%202026.clax"
        "&t=0203054427&wp=1"
    )


def test_find_glive_url_src_racine_absolu():
    """ChronoSmetron : src racine-absolu → résolu contre l'host de la page."""
    src = _find_glive_url(
        _fixture("wiclax_directory_chronosmetron.html"),
        "https://chronosmetron.wiclax-results.com/Triathlon%20de%20la%20Roche%202026/",
    )
    assert src.startswith("https://chronosmetron.wiclax-results.com/G-Live/g-live.html?f=")


def test_find_glive_url_absente():
    """Une page sans iframe G-Live renvoie None (et non une exception)."""
    assert _find_glive_url(_fixture("chronowest_event_page.html"), "https://chronowest.fr/x/") is None


# ---------------------------------------------------------------------------
# Résolution d'URL : page épreuve → coquille de résultats
# ---------------------------------------------------------------------------


def test_find_wiclax_link_page_wordpress():
    """La page épreuve WordPress pointe vers la coquille /resultats/<slug>/.

    Le lien de nav /resultats-des-courses-et-classement/ ne doit pas matcher.
    """
    lien = _find_wiclax_link(
        _fixture("chronowest_event_page.html"),
        "https://chronowest.fr/trail-des-2-ponts-2026/",
    )
    assert lien == "https://chronowest.fr/resultats/trail-des-2-ponts-2026/"


def test_find_wiclax_link_absent():
    """Une coquille à iframe n'a pas de lien sortant Wiclax → None."""
    assert _find_wiclax_link(
        _fixture("chronowest_shell_locorrida.html"),
        "https://chronowest.fr/resultats/locorrida-2026/",
    ) is None


class _FakeClient:
    """Client httpx factice : sert des fixtures depuis une table url → html."""

    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.appels: list[str] = []

    def get(self, url: str, headers=None):  # noqa: ARG002 — signature httpx
        self.appels.append(url)
        if url not in self.pages:
            raise AssertionError(f"URL non prévue par le test : {url}")
        return httpx.Response(200, text=self.pages[url], request=httpx.Request("GET", url))


def test_resolve_saute_de_la_page_epreuve_a_la_coquille():
    """Page épreuve WP (sans iframe) → lien /resultats/ → iframe G-Live."""
    client = _FakeClient({
        "https://chronowest.fr/trail-des-2-ponts-2026/": _fixture("chronowest_event_page.html"),
        "https://chronowest.fr/resultats/trail-des-2-ponts-2026/": _fixture(
            "chronowest_shell_locorrida.html"
        ),
    })
    url = _resolve_to_wiclax_url("https://chronowest.fr/trail-des-2-ponts-2026/", client)
    assert url.startswith("https://chronowest.fr/wp-content/glive/g-live.html?f=")
    assert len(client.appels) == 2


def test_resolve_boucle_infinie_gardee():
    """Une page qui se pointe elle-même s'arrête sur ValueError, pas sur RecursionError."""
    piege = (
        '<html><body><a href="https://chronowest.fr/resultats/boucle/">ici</a></body></html>'
    )
    client = _FakeClient({"https://chronowest.fr/resultats/boucle/": piege})
    with pytest.raises(ValueError, match="G-Live"):
        _resolve_to_wiclax_url("https://chronowest.fr/resultats/boucle/", client)


def test_resolve_sans_iframe_ni_lien_leve_valueerror():
    client = _FakeClient({"https://chronowest.fr/vide/": "<html><body>rien</body></html>"})
    with pytest.raises(ValueError, match="G-Live"):
        _resolve_to_wiclax_url("https://chronowest.fr/vide/", client)
