"""
Tests unitaires pour scrapers/wiclax.py.

Cas couverts :
- _assign_ranks_by_time : classement par temps net dans chaque discipline
- Disciplines séparées : Triathlon S et Triathlon XS classés indépendamment
- DNF/DNS : athlètes sans temps → rank_overall = None
- Relais : exclus du classement individuel
- Attribut v= : dossard visible, PAS le rang (bug corrigé)
- scrape_event_all format ChronoSmetron E/R : rang calculé par temps, pas par v=
"""
import xml.etree.ElementTree as ET
from datetime import date
from unittest.mock import patch

import pytest

from scrapers.base import ScrapedResult
from scrapers.wiclax import _assign_ranks_by_time, _build_split_indices, scrape_event_all


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_result(total_time: str, event_type: str = "triathlon-s", is_relay: bool = False) -> ScrapedResult:
    r = ScrapedResult(source_url="http://x", provider="wiclax")
    r.event_type = event_type
    r.total_time = total_time
    r.is_relay = is_relay
    return r


def make_chronosmetron_xml(athletes: list[dict], results: list[dict], event_name: str = "Test 2025") -> ET.Element:
    """
    Construit un arbre XML minimal au format ChronoSmetron (E/R).

    athletes : [{"d": "1001", "n": "NOM Prenom", "c": "Club", "x": "M",
                 "ca": "S1M", "p": "Triathlon S", "v": "1"}, ...]
    results  : [{"d": "1001", "t": "01h00'00"}, ...]
    """
    e_elems = "".join(
        "<E " + " ".join(f'{k}="{v}"' for k, v in a.items()) + "/>"
        for a in athletes
    )
    r_elems = "".join(
        "<R " + " ".join(f'{k}="{v}"' for k, v in r.items()) + "/>"
        for r in results
    )
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<Epreuve nom="{event_name}" dt1="2025-06-01">
  {e_elems}
  {r_elems}
</Epreuve>"""
    return ET.fromstring(xml)


# ---------------------------------------------------------------------------
# _assign_ranks_by_time — tests directs (pas de réseau)
# ---------------------------------------------------------------------------

def test_assign_ranks_basic():
    """Trois athlètes dans la même discipline : classés par temps ascendant."""
    a = make_result("01:00:00")
    b = make_result("01:05:00")
    c = make_result("01:10:00")
    _assign_ranks_by_time([a, b, c])
    assert a.rank_overall == 1
    assert b.rank_overall == 2
    assert c.rank_overall == 3


def test_assign_ranks_dnf_gets_no_rank():
    """Athlète sans temps (DNF/DNS) → rank_overall reste None."""
    a = make_result("01:00:00")
    dnf = make_result("")
    dns = make_result("Abandon")
    _assign_ranks_by_time([a, dnf, dns])
    assert a.rank_overall == 1
    assert dnf.rank_overall is None
    assert dns.rank_overall is None


def test_assign_ranks_separate_disciplines():
    """
    Triathlon S et Triathlon XS partagent event_type='triathlon-s' mais sont
    deux disciplines distinctes → chaque groupe classé indépendamment.
    Bug original : sans disc_tags, les deux groupes étaient mélangés.
    """
    s1 = make_result("01:30:00")
    s2 = make_result("01:35:00")
    xs1 = make_result("01:00:00")
    xs2 = make_result("01:05:00")
    disc_tags = ["Triathlon S", "Triathlon S", "Triathlon XS", "Triathlon XS"]
    _assign_ranks_by_time([s1, s2, xs1, xs2], disc_tags)
    # Triathlon S
    assert s1.rank_overall == 1
    assert s2.rank_overall == 2
    # Triathlon XS — classement propre, pas 3 et 4
    assert xs1.rank_overall == 1
    assert xs2.rank_overall == 2


def test_assign_ranks_without_disc_tags_mixes_by_event_type():
    """Sans disc_tags, le regroupement se fait par event_type (Format 1)."""
    a = make_result("01:00:00", event_type="triathlon-s")
    b = make_result("01:05:00", event_type="triathlon-s")
    c = make_result("00:50:00", event_type="triathlon-m")
    _assign_ranks_by_time([a, b, c])
    assert a.rank_overall == 1
    assert b.rank_overall == 2
    assert c.rank_overall == 1  # seul dans triathlon-m


def test_assign_ranks_relays_excluded():
    """Les relais (is_relay=True) ne doivent pas être classés."""
    indiv = make_result("01:00:00")
    relay = make_result("01:05:00", is_relay=True)
    _assign_ranks_by_time([indiv, relay])
    assert indiv.rank_overall == 1
    assert relay.rank_overall is None


# ---------------------------------------------------------------------------
# scrape_event_all — format ChronoSmetron E/R (avec mock)
# ---------------------------------------------------------------------------

def _mock_fetch_clax(athletes, results, event_name="Test 2025"):
    """Retourne un patch de _fetch_clax avec un XML minimal."""
    root = make_chronosmetron_xml(athletes, results, event_name)
    return patch(
        "scrapers.wiclax._fetch_clax",
        return_value=(root, "http://x/test.clax", event_name, "triathlon", date(2025, 6, 1)),
    )


def test_scrape_event_all_v_is_bib_not_rank():
    """
    Bug original : l'attribut v= (dossard visible) était stocké comme rank_overall.
    Après correction, v= doit être le bib_number et rank_overall calculé par temps.
    """
    athletes = [
        {"d": "5187", "n": "DUDOUYT Clement", "c": "TRI CLUB NANTAIS",
         "x": "M", "ca": "S4M", "p": "Triathlon S", "v": "187"},
        {"d": "5001", "n": "MARTIN Sophie", "c": "Club B",
         "x": "F", "ca": "S1F", "p": "Triathlon S", "v": "1"},
    ]
    results = [
        {"d": "5187", "t": "01h33'44"},
        {"d": "5001", "t": "01h10'00"},  # plus rapide → 1er
    ]
    with _mock_fetch_clax(athletes, results):
        scraped = scrape_event_all("http://x/")

    dudouyt = next(r for r in scraped if "DUDOUYT" in r.athlete_name)
    martin = next(r for r in scraped if "MARTIN" in r.athlete_name)

    # v= est le dossard visible, pas le rang
    assert dudouyt.bib_number == "187"
    assert dudouyt.rank_overall != 187  # l'ancien bug

    # Martin (01:10) est plus rapide → rang 1 ; Dudouyt → rang 2
    assert martin.rank_overall == 1
    assert dudouyt.rank_overall == 2


def test_scrape_event_all_rank_correct_by_time():
    """
    5 athlètes en Triathlon S avec des temps dans le désordre.
    Le rang doit correspondre à l'ordre croissant des temps.
    """
    athletes = [
        {"d": f"100{i}", "n": f"ATHLETE{i} Prenom", "c": "Club",
         "x": "M", "ca": "S1M", "p": "Triathlon S", "v": str(i)}
        for i in range(1, 6)
    ]
    # temps dans un ordre quelconque
    times = {"1001": "01:30:00", "1002": "01:10:00", "1003": "01:50:00",
             "1004": "01:20:00", "1005": "01:40:00"}
    results = [{"d": d, "t": t.replace(":", "h", 1).replace(":", "'")} for d, t in times.items()]

    with _mock_fetch_clax(athletes, results):
        scraped = scrape_event_all("http://x/")

    by_bib = {r.bib_number: r for r in scraped}
    # 1002 (01:10) → 1er, 1004 (01:20) → 2e, 1001 (01:30) → 3e, ...
    assert by_bib["1"].rank_overall == 3   # ATHLETE1 → 01:30 → 3e
    assert by_bib["2"].rank_overall == 1   # ATHLETE2 → 01:10 → 1er
    assert by_bib["3"].rank_overall == 5   # ATHLETE3 → 01:50 → 5e
    assert by_bib["4"].rank_overall == 2   # ATHLETE4 → 01:20 → 2e
    assert by_bib["5"].rank_overall == 4   # ATHLETE5 → 01:40 → 4e


def test_scrape_event_all_xs_and_s_ranked_independently():
    """
    Triathlon S et Triathlon XS → même event_type mais disciplines séparées.
    Leurs classements doivent être indépendants.
    """
    athletes = [
        {"d": "5001", "n": "MARTIN Sophie", "c": "Club", "x": "F", "ca": "S1F",
         "p": "Triathlon S", "v": "1"},
        {"d": "5002", "n": "DUPONT Jean", "c": "Club", "x": "M", "ca": "S1M",
         "p": "Triathlon S", "v": "2"},
        {"d": "3001", "n": "DURAND Paul", "c": "Club", "x": "M", "ca": "S1M",
         "p": "Triathlon XS", "v": "1"},
        {"d": "3002", "n": "LEROY Anne", "c": "Club", "x": "F", "ca": "S1F",
         "p": "Triathlon XS", "v": "2"},
    ]
    results = [
        {"d": "5001", "t": "01h30'00"},  # Tri S : 1er
        {"d": "5002", "t": "01h35'00"},  # Tri S : 2e
        {"d": "3001", "t": "00h45'00"},  # Tri XS : 1er
        {"d": "3002", "t": "00h50'00"},  # Tri XS : 2e
    ]
    with _mock_fetch_clax(athletes, results):
        scraped = scrape_event_all("http://x/")

    by_name = {r.athlete_name: r for r in scraped}
    # Tri S
    assert by_name["MARTIN"].rank_overall == 1
    assert by_name["DUPONT"].rank_overall == 2
    # Tri XS — pas 3 et 4 mais bien 1 et 2
    assert by_name["DURAND"].rank_overall == 1
    assert by_name["LEROY"].rank_overall == 2


def test_build_split_indices_multilap_run():
    """
    Régression Montreuil 2026 : la CAP est découpée en tours (disc=6 ptg 3→5 et 5→999)
    et le total CAP a disc=-1 (ptg1=t2_ptg2, ptg2=999).
    _build_split_indices doit trouver le total CAP (index 8) via le fallback disc!=-1.
    """
    xml = """<?xml version="1.0" encoding="utf-8"?>
<Epreuve nom="Montreuil 2026">
  <Segments>
    <S id="7" nom="CaP1"         ptg1="-999" ptg2="1"   disc="6"  />
    <S id="0" nom="Natation"     ptg1="-999" ptg2="0"   disc="5"  />
    <S id="1" nom="T1"           ptg1="0"    ptg2="1"   disc="-1" trans="1" />
    <S id="8" nom="Velo(enf)"    ptg1="1"    ptg2="2"   disc="-1" />
    <S id="2" nom="Velo"         ptg1="1"    ptg2="2"   disc="0"  />
    <S id="3" nom="T2"           ptg1="2"    ptg2="3"   disc="-1" trans="1" />
    <S id="5" nom="1er Tour"     ptg1="3"    ptg2="5"   disc="6"  />
    <S id="6" nom="2eme tour"    ptg1="5"    ptg2="999" disc="6"  />
    <S id="4" nom="Course pied"  ptg1="3"    ptg2="999" disc="-1" />
    <S id="9" nom="CaP2"         ptg1="2"    ptg2="999" disc="-1" />
  </Segments>
</Epreuve>"""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml)
    idx = _build_split_indices(root)
    # T2 ptg2=3, total CAP est S[8] (disc=-1, ptg1=3, ptg2=999) → index 8
    assert idx.get("swim") == 1    # Natation, disc=5
    assert idx.get("t1") == 2      # T1, trans=1
    assert idx.get("bike") == 4    # Velo, disc=0
    assert idx.get("t2") == 5      # T2, trans=1
    assert idx.get("run") == 8     # Course à pied total (disc=-1, fallback)


def test_scrape_event_all_dnf_has_no_rank():
    """Athlète sans temps dans le R element → rank_overall = None."""
    athletes = [
        {"d": "1001", "n": "DUPONT Jean", "c": "Club", "x": "M", "ca": "S1M",
         "p": "Triathlon S", "v": "1"},
        {"d": "1002", "n": "MARTIN Paul", "c": "Club", "x": "M", "ca": "S1M",
         "p": "Triathlon S", "v": "2"},
    ]
    results = [
        {"d": "1001", "t": "01h00'00"},
        # 1002 n'a pas de R element (abandon avant la ligne d'arrivée)
    ]
    with _mock_fetch_clax(athletes, results):
        scraped = scrape_event_all("http://x/")

    dupont = next(r for r in scraped if "DUPONT" in r.athlete_name)
    martin = next(r for r in scraped if "MARTIN" in r.athlete_name)
    assert dupont.rank_overall == 1
    assert martin.rank_overall is None
