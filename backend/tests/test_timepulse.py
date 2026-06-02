"""
Tests unitaires pour scrapers/timepulse.py.

Cas couverts :
- GOUBAUD\xa0Manon : espace insécable dans le XML → trouvé par recherche avec espace normal
- Homonymie GOUBAUD : deux athlètes → liste de désambiguïsation
- Mapping des séries S0-S4 → swim/t1/bike/t2/run
- Calcul des classements général / genre / catégorie
- Détection du type d'épreuve depuis le nom de l'épreuve
"""
import pytest

from scrapers.timepulse import (
    _attrs,
    _compute_ranks,
    _detect_event_type,
    _find_tag,
    _normalize_name,
    _parse_series,
    _search_athletes,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_xml(
    athletes: list[tuple[str, str, str, str, str]],
    results: list[tuple[str, str, dict[str, str]]] | None = None,
    series: list[tuple[str, str]] | None = None,
    event_name: str = "Triathlon Test 2025",
    parcours: str = "p1",
) -> str:
    """
    Construit un XML minimal au format TimePulse/Wiclax.

    athletes : [(bib, name, category, gender, parcours), …]
    results  : [(bib, total_time, {s0: time, s1: time, …}), …]
    series   : [(id, nom), …]  — par défaut S0-S4 triathlon complet
    """
    if series is None:
        series = [
            ("0", "Natation"),
            ("1", "T1"),
            ("2", "Vélo"),
            ("3", "T2"),
            ("4", "Course à pied"),
        ]

    series_xml = "\n".join(
        f'<S id="{sid}" nom="{nom}"/>' for sid, nom in series
    )

    athletes_xml = "\n".join(
        f'<E d="{bib}" n="{name}" c="Club" x="{gender}" ca="{cat}" p="{prc}"/>'
        for bib, name, cat, gender, prc in athletes
    )

    results_xml = ""
    if results:
        for bib, total, splits in results:
            splits_attrs = " ".join(f'{k}="{v}"' for k, v in splits.items())
            results_xml += f'<R d="{bib}" t="{total}" {splits_attrs}/>\n'

    return f"""<?xml version="1.0"?>
<Triathlon>
  <Epreuve nom="{event_name}" dates="2025-06-01"/>
  {series_xml}
  {athletes_xml}
  {results_xml}
</Triathlon>"""


# ---------------------------------------------------------------------------
# _normalize_name
# ---------------------------------------------------------------------------

def test_normalize_name_regular_space():
    assert _normalize_name("dupont jean") == "DUPONT JEAN"


def test_normalize_name_nbsp():
    """L'espace insécable (\\xa0) doit être normalisé comme un espace ordinaire."""
    assert _normalize_name("GOUBAUD\xa0Manon") == "GOUBAUD MANON"


def test_normalize_name_multiple_spaces():
    assert _normalize_name("GOUBAUD  Manon") == "GOUBAUD MANON"


# ---------------------------------------------------------------------------
# _search_athletes
# ---------------------------------------------------------------------------

def test_search_athletes_no_match():
    xml = make_xml(athletes=[("10", "DUPONT Jean", "SEH", "M", "p1")])
    assert _search_athletes(xml, "MARTIN") == []


def test_search_athletes_one_match():
    xml = make_xml(athletes=[
        ("10", "DUPONT Jean", "SEH", "M", "p1"),
        ("20", "MARTIN Sophie", "SEF", "F", "p1"),
    ])
    matches = _search_athletes(xml, "MARTIN")
    assert len(matches) == 1
    assert matches[0][0] == "20"
    assert "MARTIN" in matches[0][1]


def test_search_athletes_multiple_goubaud():
    """Cas réel : GOUBAUD Céline (127) et GOUBAUD Manon (41) sur id_event=3090."""
    xml = make_xml(athletes=[
        ("127", "GOUBAUD Celine", "V1F", "F", "p1"),
        ("41",  "GOUBAUD Manon",  "SEF", "F", "p1"),
        ("99",  "DUPONT Jean",    "SEH", "M", "p1"),
    ])
    matches = _search_athletes(xml, "GOUBAUD")
    assert len(matches) == 2
    bibs = {m[0] for m in matches}
    assert bibs == {"41", "127"}


def test_search_athletes_nbsp_in_xml():
    """
    Cas GOUBAUD Manon : le XML TimePulse stocke le nom avec un espace insécable
    (\\xa0). La recherche avec un espace ordinaire doit quand même trouver l'athlète.
    """
    xml = make_xml(athletes=[("41", "GOUBAUD\xa0Manon", "SEF", "F", "p1")])
    matches = _search_athletes(xml, "GOUBAUD Manon")
    assert len(matches) == 1
    assert matches[0][0] == "41"


def test_search_case_insensitive():
    xml = make_xml(athletes=[("5", "LECLERC Paul", "SEH", "M", "p1")])
    assert len(_search_athletes(xml, "leclerc")) == 1


# ---------------------------------------------------------------------------
# _parse_series
# ---------------------------------------------------------------------------

def test_parse_series_standard():
    """Mapping S0→swim, S1→t1, S2→bike, S3→t2, S4→run."""
    xml = make_xml(athletes=[])
    mapping = _parse_series(xml)
    assert mapping == {"s0": "swim", "s1": "t1", "s2": "bike", "s3": "t2", "s4": "run"}


def test_parse_series_chg_nat():
    """Certains événements utilisent 'Chg Nat' pour T1."""
    xml = make_xml(
        athletes=[],
        series=[
            ("0", "Natation"),
            ("1", "Chg Nat"),
            ("2", "Vélo"),
            ("3", "Chg V"),
            ("4", "Course à pied"),
        ],
    )
    mapping = _parse_series(xml)
    assert mapping["s1"] == "t1"
    assert mapping["s3"] == "t2"


# ---------------------------------------------------------------------------
# _compute_ranks
# ---------------------------------------------------------------------------

def test_compute_ranks():
    """
    5 athlètes, même parcours p1 :
      bib=10 : M, SEH, 01:00:00  → 1er général, 1er H, 1er SEH
      bib=20 : F, SEF, 01:10:00  → 2e général, 1re F, 1re SEF
      bib=30 : M, V1H, 01:20:00  → 3e général, 2e H, 1er V1H  ← cible
      bib=40 : F, SEF, 01:30:00
      bib=50 : M, V1H, 01:40:00
    """
    athletes = [
        ("10", "ALPHA Jean",  "SEH", "M", "p1"),
        ("20", "BETA Sophie", "SEF", "F", "p1"),
        ("30", "GAMMA Pierre","V1H", "M", "p1"),
        ("40", "DELTA Marie", "SEF", "F", "p1"),
        ("50", "EPSILON Luc", "V1H", "M", "p1"),
    ]
    results = [
        ("10", "01:00:00", {"s0": "00:20:00"}),
        ("20", "01:10:00", {"s0": "00:22:00"}),
        ("30", "01:20:00", {"s0": "00:24:00"}),
        ("40", "01:30:00", {"s0": "00:26:00"}),
        ("50", "01:40:00", {"s0": "00:28:00"}),
    ]
    xml = make_xml(athletes=athletes, results=results)

    ro, rg, rc = _compute_ranks(xml, bib="30", parcours="p1", gender="M", category="V1H")

    assert ro == 3   # 3e au général
    assert rg == 2   # 2e homme (derrière bib=10)
    assert rc == 1   # 1er V1H


def test_compute_ranks_no_result_for_bib():
    """Athlète sans ligne <R> → tous classements à None."""
    xml = make_xml(
        athletes=[("99", "TEST Athlète", "SEH", "M", "p1")],
        results=[],
    )
    ro, rg, rc = _compute_ranks(xml, bib="99", parcours="p1", gender="M", category="SEH")
    assert ro is None
    assert rg is None
    assert rc is None


# ---------------------------------------------------------------------------
# _detect_event_type
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("Triathlon de Noirmoutier Sprint 2025", "triathlon-s"),
    ("Triathlon Olympique de Paris 2025",    "triathlon-m"),
    ("Triathlon L de Bordeaux",              "triathlon-l"),
    ("Ironman France 2025",                  "triathlon-xl"),
    ("Triathlon XXL Embrunman",              "triathlon-xl"),
    ("Triathlon 70.3 Aix-en-Provence",      "triathlon-l"),
    ("Duathlon de Rennes",                   "duathlon"),
    ("SwimRun des Îles",                     "swimrun"),
    ("Triathlon de Lacanau 2025",            "triathlon"),   # pas de mot-clé → défaut
])
def test_detect_event_type_timepulse(name, expected):
    from scrapers.timepulse import _detect_event_type
    assert _detect_event_type(name) == expected


# ---------------------------------------------------------------------------
# _attrs et _find_tag
# ---------------------------------------------------------------------------

def test_attrs_extracts_all():
    tag = '<E d="41" n="GOUBAUD Manon" c="Club" x="F" ca="SEF" p="p1"/>'
    a = _attrs(tag)
    assert a["d"] == "41"
    assert a["n"] == "GOUBAUD Manon"
    assert a["x"] == "F"
    assert a["ca"] == "SEF"


def test_find_tag_found():
    xml = make_xml(athletes=[("42", "MARTIN Paul", "SEH", "M", "p1")])
    tag = _find_tag(xml, "E", "d", "42")
    assert tag is not None
    assert 'n="MARTIN Paul"' in tag


def test_find_tag_not_found():
    xml = make_xml(athletes=[("10", "DUPONT Jean", "SEH", "M", "p1")])
    assert _find_tag(xml, "E", "d", "999") is None
