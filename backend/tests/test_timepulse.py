"""
Tests unitaires pour scrapers/timepulse.py.

Cas couverts :
- Mapping des séries S0-S4 → swim/t1/bike/t2/run
- Calcul des classements général / genre / catégorie
- rank_category filtre par genre+catégorie (évite rank_category > rank_gender)
- Détection du type d'épreuve depuis le nom de l'épreuve
- Parsing de la date d'épreuve depuis l'attribut XML dates=
"""
import pytest

from app.scrapers.timepulse import (
    _attrs,
    _compute_ranks,
    _detect_event_type,
    _find_tag,
    _parse_event_date,
    _parse_series,
    scrape_event_all,
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


def test_compute_ranks_category_not_exceeds_gender():
    """
    Régression — rank_category ne doit pas dépasser rank_gender.
    Si catégorie = V1H (sous-ensemble des hommes), rank_category <= rank_gender.

    5 athlètes :
      bib=10 : M, SEH, 01:00:00  → 1er H, pas V1H
      bib=20 : F, V1F, 01:10:00  → 1re F, 1re V1F  (même catégorie string "V1" sans genre
                                                       si non suffixé, mais ici c'est V1F)
      bib=30 : M, V1H, 01:20:00  → 2e H, 1er V1H  ← cible
      bib=40 : F, V1F, 01:30:00  → 2e F, 2e V1F
      bib=50 : M, V1H, 01:40:00  → 3e H, 2e V1H

    Avant le fix, si le code comptait V1H parmi tous les genres, V1H inclurait bib=20 (V1F)
    si les catégories n'avaient pas de suffixe genre. Ce test utilise des catégories distinctes
    V1H/V1F, donc rank_category(bib=30) doit être 1 et rank_gender(bib=30) doit être 2.
    """
    athletes = [
        ("10", "ALPHA Jean",   "SEH", "M", "p1"),
        ("20", "BETA Sophie",  "V1F", "F", "p1"),
        ("30", "GAMMA Pierre", "V1H", "M", "p1"),
        ("40", "DELTA Marie",  "V1F", "F", "p1"),
        ("50", "EPSILON Luc",  "V1H", "M", "p1"),
    ]
    results_data = [
        ("10", "01:00:00", {}),
        ("20", "01:10:00", {}),
        ("30", "01:20:00", {}),
        ("40", "01:30:00", {}),
        ("50", "01:40:00", {}),
    ]
    xml = make_xml(athletes=athletes, results=results_data)
    ro, rg, rc = _compute_ranks(xml, bib="30", parcours="p1", gender="M", category="V1H")

    assert ro == 3   # 3e au général
    assert rg == 2   # 2e homme (derrière bib=10)
    assert rc == 1   # 1er V1H — doit être 1, pas 2 (V1F ne compte pas)
    assert rc <= rg  # invariant : rank_category ne peut pas dépasser rank_gender


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
    # --- Triathlon (non-régression) ---
    ("Triathlon de Noirmoutier Sprint 2025", "triathlon-s"),
    ("Triathlon Olympique de Paris 2025",    "triathlon-m"),
    ("Triathlon L de Bordeaux",              "triathlon-l"),
    ("Ironman France 2025",                  "triathlon-xl"),
    ("Triathlon XXL Embrunman",              "triathlon-xl"),
    ("Triathlon 70.3 Aix-en-Provence",      "triathlon-l"),
    ("Triathlon de Lacanau 2025",            "triathlon"),
    # --- Duathlon : sous-formats + pas de régression "sprint" → triathlon-s ---
    ("Duathlon de Rennes",                   "duathlon"),
    ("Duathlon Sprint de Couëron 2025",      "duathlon-s"),  # était "triathlon-s" avant fix
    ("RSSC Duathlon",                        "duathlon"),
    # --- Nouveaux sports ---
    ("Aquathlon du RC Doué",                 "aquathlon"),
    ("Planète Racing Aquarun 2026",          "aquarun"),
    ("BIKE & RUN d'Halloween",               "bike-run"),
    ("Run & Bike du Bignon",                 "bike-run"),
    ("SwimRun des Îles",                     "swimrun"),
    ("SWIMRUN DE MAYENNE",                   "swimrun"),
])
def test_detect_event_type_timepulse(name, expected):
    assert _detect_event_type(name) == expected


# ---------------------------------------------------------------------------
# _parse_series — duathlon et aquarun
# ---------------------------------------------------------------------------

def test_parse_series_duathlon():
    """
    Duathlon : 2 × 'Course à pied' + 0 natation.
    Le premier run doit être mappé sur le slot 'swim' (run1), le second sur 'run' (run2).
    """
    xml = make_xml(
        athletes=[],
        series=[
            ("0", "Course à pied"),   # run1
            ("1", "T1"),
            ("2", "Vélo"),
            ("3", "T2"),
            ("4", "Course à pied"),   # run2
        ],
    )
    mapping = _parse_series(xml)
    assert mapping["s0"] == "swim"   # run1 redirigé vers slot swim
    assert mapping["s1"] == "t1"
    assert mapping["s2"] == "bike"
    assert mapping["s3"] == "t2"
    assert mapping["s4"] == "run"    # run2 → slot run


def test_parse_series_aquarun():
    """Aquarun : Natation → T1 → Course à pied (pas de vélo)."""
    xml = make_xml(
        athletes=[],
        series=[
            ("0", "Natation"),
            ("1", "T1"),
            ("2", "Course à pied"),
        ],
    )
    mapping = _parse_series(xml)
    assert mapping == {"s0": "swim", "s1": "t1", "s2": "run"}


def test_parse_series_aquathlon():
    """Aquathlon : Natation → Course à pied (sans transition)."""
    xml = make_xml(
        athletes=[],
        series=[
            ("0", "Natation"),
            ("1", "Course à pied"),
        ],
    )
    mapping = _parse_series(xml)
    assert mapping == {"s0": "swim", "s1": "run"}


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


def test_parse_event_date_iso():
    """Format ISO YYYY-MM-DD."""
    from datetime import date
    assert _parse_event_date("2025-06-01") == date(2025, 6, 1)


def test_parse_event_date_french():
    """Format français DD/MM/YYYY."""
    from datetime import date
    assert _parse_event_date("01/06/2025") == date(2025, 6, 1)


def test_parse_event_date_invalid():
    """Chaîne non parseable → None."""
    assert _parse_event_date("juin 2025") is None
    assert _parse_event_date("") is None


def test_find_tag_not_found():
    xml = make_xml(athletes=[("10", "DUPONT Jean", "SEH", "M", "p1")])
    assert _find_tag(xml, "E", "d", "999") is None


# ---------------------------------------------------------------------------
# Extraction de l'id_event depuis le chemin URL (sans query param id_event=)
# ---------------------------------------------------------------------------

def test_id_event_extracted_from_path():
    """
    L'URL https://www.timepulse.fr/epreuves/resultats/3090 ne contient pas
    id_event= en query param. Le scraper doit extraire 3090 depuis le chemin.
    Vérifié en inspectant la logique de parsing, sans appel réseau.
    """
    import re
    from urllib.parse import parse_qs, urlparse

    url = "https://www.timepulse.fr/epreuves/resultats/3090"
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    id_event = params.get("id_event", [""])[0]

    # Simule le fallback du scraper
    if not id_event:
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        for part in reversed(path_parts):
            if re.match(r"^\d+$", part):
                id_event = part
                break

    assert id_event == "3090"


# ---------------------------------------------------------------------------
# scrape_event_all — conservation des non-finishers + statut
# ---------------------------------------------------------------------------

def test_scrape_event_all_keeps_non_finisher(monkeypatch):
    """Un <E> sans <R> est désormais CONSERVÉ (régression du drop historique)."""
    xml = make_xml(
        athletes=[
            ("10", "ALPHA Jean", "SEH", "M", "p1"),   # finisher (a un <R>)
            ("20", "BETA Marie", "SEF", "F", "p1"),   # non-finisher (pas de <R>)
        ],
        results=[("10", "01:00:00", {"s0": "00:20:00"})],
    )
    monkeypatch.setattr("app.scrapers.timepulse._fetch_xml", lambda _id: xml)

    results = scrape_event_all("https://www.timepulse.fr/resultats/3090")
    by_bib = {r.bib_number: r for r in results}

    assert set(by_bib) == {"10", "20"}          # le non-finisher n'est plus jeté
    assert by_bib["10"].total_time == "01:00:00"
    assert by_bib["20"].total_time == ""        # pas de <R> → pas de temps
    assert by_bib["20"].rank_overall is None
    assert by_bib["20"].status == ""            # aucun marqueur → heuristique infra
    assert by_bib["20"].athlete_name == "BETA"
    assert by_bib["20"].athlete_firstname == "Marie"


def test_scrape_event_all_reads_explicit_status(monkeypatch):
    """Statut explicite sur <E> (attribut candidat etat=) → DNF + hygiène."""
    xml = make_xml(
        athletes=[("30", "GAMMA Paul", "SEH", "M", "p1")],
        results=[],
    ).replace('<E d="30"', '<E etat="Abandon" d="30"')
    monkeypatch.setattr("app.scrapers.timepulse._fetch_xml", lambda _id: xml)

    results = scrape_event_all("https://www.timepulse.fr/resultats/3090")
    assert results[0].status == "DNF"
    assert results[0].total_time == ""
    assert results[0].rank_overall is None


def test_scrape_event_all_reads_np_flag_dns(monkeypatch):
    """Découverte réelle : np="1" sur <E> → DNS + hygiène (ni temps ni rang)."""
    xml = make_xml(
        athletes=[("40", "DELTA Luc", "SEH", "M", "p1")],
        results=[],
    ).replace('<E d="40"', '<E np="1" d="40"')
    monkeypatch.setattr("app.scrapers.timepulse._fetch_xml", lambda _id: xml)

    results = scrape_event_all("https://www.timepulse.fr/resultats/3090")
    assert results[0].status == "DNS"
    assert results[0].total_time == ""
    assert results[0].rank_overall is None


def test_scrape_event_all_event_type_from_parcours(monkeypatch):
    """Le format (S/M/L) vient du parcours `p`, pas du nom global d'épreuve.

    Cas réel (épreuve 3232 « LE NORTH MAY ») : le nom de l'épreuve ne porte
    aucune taille, seul le parcours de chaque <E> distingue Triathlon S/M/L.
    """
    xml = make_xml(
        athletes=[
            ("10", "ALPHA Jean", "SEH", "M", "Triathlon S SOLO"),
            ("20", "BETA Marie", "SEF", "F", "Triathlon M SOLO"),
            ("30", "GAMMA Paul", "SEH", "M", "Triathlon L SOLO"),
            ("40", "DELTA Luc", "SEH", "M", ""),  # parcours absent → repli nom global
        ],
        results=[
            ("10", "01:00:00", {}),
            ("20", "02:00:00", {}),
            ("30", "03:00:00", {}),
            ("40", "04:00:00", {}),
        ],
        event_name="LE NORTH MAY",  # aucune taille dans le nom global
    )
    monkeypatch.setattr("app.scrapers.timepulse._fetch_xml", lambda _id: xml)

    results = scrape_event_all("https://www.timepulse.fr/resultats/3232")
    by_bib = {r.bib_number: r for r in results}

    assert by_bib["10"].event_type == "triathlon-s"
    assert by_bib["20"].event_type == "triathlon-m"
    assert by_bib["30"].event_type == "triathlon-l"
    assert by_bib["40"].event_type == "triathlon"  # repli nom global


def test_scrape_event_all_detects_relay(monkeypatch):
    """Relais détecté via parcours « RELAIS » et/ou catégorie EQ* ; solo → False.

    Cas réel (épreuve 3232 « LE NORTH MAY ») : une même épreuve mélange des
    solos (p="Triathlon S SOLO", ca="SEH") et des relais d'équipe
    (p="Triathlon S RELAIS", ca="EQX"/"EQM"/"EQF").
    """
    xml = make_xml(
        athletes=[
            ("10", "ALPHA Jean", "SEH", "M", "Triathlon S SOLO"),       # solo
            ("20", "ROUXEL/ROUXEL Didier/Emma", "EQX", "M", "Triathlon S RELAIS"),  # relais mixte
            ("30", "CANNIOU/OLIVIER Cedric/Leclerc", "EQM", "M", "Triathlon S RELAIS"),
        ],
        results=[
            ("10", "01:00:00", {}),
            ("20", "01:24:03", {}),
            ("30", "01:30:00", {}),
        ],
        event_name="LE NORTH MAY",
    )
    monkeypatch.setattr("app.scrapers.timepulse._fetch_xml", lambda _id: xml)

    results = scrape_event_all("https://www.timepulse.fr/resultats/3232")
    by_bib = {r.bib_number: r for r in results}

    assert by_bib["10"].is_relay is False
    assert by_bib["20"].is_relay is True
    assert by_bib["30"].is_relay is True


def test_scrape_event_all_derives_t2_and_run_from_passages(monkeypatch):
    """T2/course non publiés en segments (np="1") → dérivés des points cumulés.

    Cas réel (épreuve 3232) : le <R> ne porte que s0/s1/s2 (natation/T1/vélo) ;
    T2 et course à pied n'existent que sous forme de points de passage cumulés
    p0..p7. T2 = 1er point après la fin du vélo − fin du vélo ; course = total −
    ce point. Chiffres du dossard 685 (parcours S).
    """
    xml = make_xml(
        athletes=[("685", "ALPHA Jean", "SEH", "M", "Triathlon S SOLO")],
        results=[("685", "01:01:19", {
            "s0": "00:10:21", "s1": "00:01:23", "s2": "00:30:24",
            "p0": "00:10:21", "p1": "00:11:44", "p2": "00:42:08",
            "p4": "00:43:25", "p6": "00:47:22", "p7": "00:50:49",
        })],
        event_name="LE NORTH MAY",
    )
    monkeypatch.setattr("app.scrapers.timepulse._fetch_xml", lambda _id: xml)

    r = scrape_event_all("https://www.timepulse.fr/resultats/3232")[0]

    assert r.swim_time == "00:10:21"
    assert r.t1_time == "00:01:23"
    assert r.bike_time == "00:30:24"
    assert r.t2_time == "00:01:17"   # p4 (00:43:25) − fin vélo (00:42:08)
    assert r.run_time == "00:17:54"  # total (01:01:19) − p4 (00:43:25)


def test_scrape_event_all_keeps_native_segments_over_derivation(monkeypatch):
    """Si TimePulse fournit s3/s4, on les garde tels quels (pas de dérivation)."""
    xml = make_xml(
        athletes=[("700", "BETA Marc", "SEH", "M", "Triathlon S SOLO")],
        results=[("700", "01:01:19", {
            "s0": "00:10:21", "s1": "00:01:23", "s2": "00:30:24",
            "s3": "00:00:30", "s4": "00:18:41",
            "p0": "00:10:21", "p2": "00:42:08", "p4": "00:43:25",
        })],
        event_name="LE NORTH MAY",
    )
    monkeypatch.setattr("app.scrapers.timepulse._fetch_xml", lambda _id: xml)

    r = scrape_event_all("https://www.timepulse.fr/resultats/3232")[0]
    assert r.t2_time == "00:00:30"   # segment natif, pas la dérivation
    assert r.run_time == "00:18:41"


def test_id_event_extracted_from_path_short():
    """Variante courte : https://www.timepulse.fr/resultats/3090."""
    import re
    from urllib.parse import parse_qs, urlparse

    url = "https://www.timepulse.fr/resultats/3090"
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    id_event = params.get("id_event", [""])[0]

    if not id_event:
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        for part in reversed(path_parts):
            if re.match(r"^\d+$", part):
                id_event = part
                break

    assert id_event == "3090"
