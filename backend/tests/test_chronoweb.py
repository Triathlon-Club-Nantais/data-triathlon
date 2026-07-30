"""Unit tests for scrapers/chronoweb.py (no network).

Fixtures under `fixtures/chronoweb/` are reduced but **verbatim** excerpts of
chronoweb.com pages downloaded on 2026-07-30: only whole rows were dropped, no
markup was rewritten, so the structural traps stay in — stacked ranks
(`div.display_rank_global` over `div.display_rank_cat.hidden`), one row per
timing point rather than per participant, inline PHP warnings, `data-*`
attributes. Ground truth for every claim asserted here:
`docs/superpowers/specs/2026-07-29-chronoweb-sondage.md`.

Naming follows constitution principle I: English for technical identifiers,
French only for business rationale in comments.
"""
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.scrapers import chronoweb
from app.scrapers.base import ScrapedResult
from app.services.mapping import build_splits

FIXTURES = Path(__file__).parent / "fixtures" / "chronoweb"


def _fixture(name: str) -> str:
    return (FIXTURES / f"{name}.html").read_text(encoding="utf-8")


TRIATHLON = _fixture("event_triathlon")              # Oléron 2024, 3 races, N→V→C
POINT_MANQUANT = _fixture("event_point_manquant")    # Oléron 2025, finisher missing a point
DUATHLON = _fixture("event_duathlon")                # Toulouse 2024, C→V→C, relay, derived rank
AQUATHLON_RELAIS = _fixture("event_aquathlon_relais")  # La Verrerie 2025, 8 alternating points
MONO_POINT = _fixture("event_mono_point")            # ALEFPA Trail 2025, one point per race
SANS_CLASSEMENT = _fixture("event_sans_classement")  # Chalain 2015, named but no ranking
INCONNU = _fixture("event_inconnu")                  # unknown event id: 200 without h2.name
CATALOGUE = _fixture("catalogue")                    # /resultats.php, 3 of its 222 rows

EVENT_URL = "https://chronoweb.com/resultats_evenement.php?event=323"


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text, self.status_code = text, status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPError(f"HTTP {self.status_code}")


class FakeClient:
    """Fake HTTP client: routes by URL, records every call.

    Recording matters as much as serving: "at most two requests per imported
    event" (FR-020) and "never the participant page" (FR-019) are asserted
    invariants, and the only place they can be checked is this counter.
    """

    def __init__(self, event: str = TRIATHLON, catalogue: str = CATALOGUE,
                 catalogue_status: int = 200):
        self.event, self.catalogue = event, catalogue
        self.catalogue_status = catalogue_status
        self.calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url: str):
        self.calls.append(url)
        if "resultats_evenement.php" in url:
            return FakeResponse(self.event)
        if "resultats.php" in url:
            return FakeResponse(self.catalogue, self.catalogue_status)
        raise AssertionError(f"URL inattendue : {url}")


def test_parse_event_meta_reads_name_and_date():
    meta = chronoweb._parse_event_meta(chronoweb._soup(TRIATHLON))

    assert meta.name == "Triathlon d'Oléron 2024"
    assert meta.event_date == date(2024, 10, 6)
    # La commune n'est pas sur la page de résultats : elle vient du catalogue.
    assert meta.city == ""


def test_parse_races_reads_every_option_of_the_selector():
    """Une URL désigne un événement, pas une épreuve : les 3 sont lues d'un coup."""
    races = chronoweb._parse_races(chronoweb._soup(TRIATHLON), chronoweb._parse_event_meta(chronoweb._soup(TRIATHLON)))

    assert [(r.race_id, r.label) for r in races] == [
        ("1147", "Triathlon M"), ("1148", "Triathlon S"), ("1149", "Triathlon XS"),
    ]
    assert [r.event_type for r in races] == ["triathlon-m", "triathlon-s", "triathlon-xs"]
    assert not any(r.is_relay for r in races)


def test_parse_races_classifies_with_the_event_name_as_context():
    """« S D3 » ne nomme aucun sport : c'est « Duathlon de Toulouse 2024 » qui le dit."""
    races = chronoweb._parse_races(chronoweb._soup(DUATHLON), chronoweb._parse_event_meta(chronoweb._soup(DUATHLON)))

    assert [r.event_type for r in races][:1] == ["duathlon-s"]


def test_parse_races_marks_a_relay_from_its_label():
    """Le libellé marque le relais ; la catégorie ne le peut pas (`MASC` existe
    aussi en individuel, cf. research R6)."""
    races = {r.label: r for r in
             chronoweb._parse_races(chronoweb._soup(DUATHLON), chronoweb._parse_event_meta(chronoweb._soup(DUATHLON)))}

    assert races["S Relais"].is_relay is True
    assert races["S D3"].is_relay is False


def test_canonical_url_keeps_only_the_event_parameter():
    """`epreuve`, `cat` et `point` ne sont que des paramètres d'affichage : la page
    servie est la même. Les retirer donne une clé d'événement unique pour les
    4 graphies d'Oléron 2024 présentes dans le Sheet."""
    assert chronoweb.canonical_url(
        "https://chronoweb.com/resultats_evenement.php?event=323&epreuve=1147"
    ) == EVENT_URL
    assert chronoweb.canonical_url(
        "https://chronoweb.com/resultats_evenement.php?event=323&epreuve=1148&cat=all&point=10"
    ) == EVENT_URL


def test_canonical_url_accepts_the_www_host():
    assert chronoweb.canonical_url(
        "https://www.chronoweb.com/resultats_evenement.php?event=323"
    ) == EVENT_URL


def _rows(html: str, race_id: str):
    return chronoweb._parse_passages(chronoweb._soup(html), race_id)


def _row(html: str, race_id: str, bib: str, point_id: int):
    return next(r for r in _rows(html, race_id)
                if r.bib == bib and r.passage.point_id == point_id)


def test_parse_passages_yields_one_row_per_timing_point():
    """Une ligne = un passage. Le dossard 360 en occupe trois, pas trois participants."""
    rows = _rows(TRIATHLON, "1147")

    assert len(rows) == 12
    assert sorted(r.passage.point_id for r in rows if r.bib == "360") == [1, 8, 14]


def test_parse_passages_reads_the_finish_row_of_bib_360():
    row = _row(TRIATHLON, "1147", "360", 14)

    assert (row.bib, row.name, row.category) == ("360", "MARIN Thomas", "MSE")
    assert row.passage.point_name == "Course"
    # Cumul (2ᵉ cellule) et durée du segment (6ᵉ) sont deux colonnes distinctes.
    assert row.passage.cumulative == "02:13:26"
    assert row.passage.segment == "00:39:26"
    assert row.passage.rank_overall == 1
    assert row.passage.rank_category == 1
    assert row.passage.speed == "15.22 km/h"
    assert row.passage.rank_gain == "0"


def test_parse_passages_never_reads_the_rank_from_the_cell_text():
    """La cellule de classement superpose deux `<div>`, dont un `hidden` : lue au
    texte elle rend « 11 » pour un 1ᵉʳ/1ᵉʳ et « 11837 » pour un 118ᵉ/37ᵉ."""
    cell = (chronoweb._soup(TRIATHLON)
            .select_one("div.results_epreuve.epreuve_1147 a.table-row.body div.table-cell.classement"))
    assert cell.get_text(strip=True) == "11"

    row = _row(TRIATHLON, "1147", "360", 14)
    assert (row.passage.rank_overall, row.passage.rank_category) == (1, 1)


def test_parse_passages_skips_a_row_whose_cell_count_is_off(caplog):
    """Ligne synthétique : la source publie 9 cellules sur les 89 épreuves du
    panel. Une ligne d'un autre format est ignorée — les autres restent importées."""
    html = """<div class="results_epreuve epreuve_9" data-race="9">
      <div class="htmltable results_list">
        <a class="table-row body" data-cat="MSE" data-point="1" data-pointname="Course">
          <div class="table-cell classement"><div class="display_rank_global">1</div>
          <div class="display_rank_cat hidden">1</div></div>
          <div class="table-cell">00:10:00</div>
        </a>
        <a class="table-row body" data-cat="MSE" data-point="1" data-pointname="Course">
          <div class="table-cell classement"><div class="display_rank_global">2</div>
          <div class="display_rank_cat hidden">2</div></div>
          <div class="table-cell">00:11:00</div>
          <div class="table-cell text-left lineinfo_name">MARTIN Paul</div>
          <div class="table-cell lineinfo_bib">7</div>
          <div class="table-cell">MSE</div>
          <div class="table-cell">00:11:00</div>
          <div class="table-cell">2</div>
          <div class="table-cell vmoyenne text-left">10.0 km/h</div>
          <div class="table-cell gain">0</div>
        </a>
      </div></div>"""

    rows = _rows(html, "9")

    assert [r.bib for r in rows] == ["7"]
    assert any("2 cells instead of 9" in r.getMessage() for r in caplog.records)


def test_group_runners_counts_bibs_not_rows():
    """Compter les lignes triplerait l'effectif d'un triathlon à trois points."""
    runners = chronoweb._group_runners(_rows(TRIATHLON, "1147"))

    assert len(runners) == 5
    assert sorted(r.bib for r in runners) == ["187", "248", "347", "360", "422"]


def test_group_runners_orders_passages_by_point_id():
    runner = next(r for r in chronoweb._group_runners(_rows(TRIATHLON, "1147"))
                  if r.bib == "360")

    assert [p.point_id for p in runner.passages] == [1, 8, 14]
    assert [p.point_name for p in runner.passages] == ["Natation", "Vélo", "Course"]


def test_group_runners_keeps_a_bib_absent_from_the_final_point():
    """1,42 % du panel : un concurrent lu à un point sans figurer au dernier."""
    runners = {r.bib: r for r in chronoweb._group_runners(_rows(TRIATHLON, "1147"))}

    assert [p.point_id for p in runners["187"].passages] == [1, 8]
    assert [p.point_id for p in runners["248"].passages] == [1]


def test_final_point_is_the_race_maximum_not_the_runner_maximum():
    """Le point final se décide **par épreuve** : lu par participant, le dernier
    point d'un abandon deviendrait son point final, donc son temps et ses rangs."""
    rows = _rows(TRIATHLON, "1147")

    assert chronoweb._final_point(rows) == 14
    assert chronoweb._final_point(_rows(TRIATHLON, "1148")) == 10
    assert chronoweb._final_point(_rows(MONO_POINT, "1274")) == 2


def _runners(html: str, race_id: str):
    rows = _rows(html, race_id)
    return {r.bib: r for r in chronoweb._group_runners(rows)}, chronoweb._final_point(rows)


def test_final_passage_carries_the_total_time_and_both_ranks():
    runners, final = _runners(TRIATHLON, "1147")

    passage = chronoweb._final_passage(runners["360"], final)

    assert (passage.cumulative, passage.rank_overall, passage.rank_category) == (
        "02:13:26", 1, 1)


def test_final_passage_takes_the_ranks_of_a_runner_whose_ranks_move():
    """Contre-épreuve du dossard 360, 1ᵉʳ partout : celui-ci passe 205ᵉ → 93ᵉ → 45ᵉ.

    Sans lui, une implémentation qui lirait les **rangs** au premier passage tout
    en lisant le **temps** au dernier resterait verte — or c'est exactement ce que
    FR-005 interdit.
    """
    runners, final = _runners(TRIATHLON, "1147")

    assert [(p.rank_overall, p.rank_category) for p in runners["347"].passages] == [
        (205, 99), (93, 51), (45, 27)]

    passage = chronoweb._final_passage(runners["347"], final)
    assert (passage.cumulative, passage.rank_overall, passage.rank_category) == (
        "02:40:34", 45, 27)


def test_final_passage_is_none_for_a_runner_absent_from_the_final_point():
    """Un rang intermédiaire est un vrai rang de la source, mais d'une autre
    population : promu en rang de classement il doublonnerait celui d'un finisher
    et ferait ressortir toute l'épreuve peu fiable."""
    runners, final = _runners(TRIATHLON, "1147")

    assert chronoweb._final_passage(runners["187"], final) is None
    # Le rang qu'il occupait au vélo existe pourtant bien, et reste lisible.
    assert runners["187"].passages[-1].rank_overall == 24


def test_final_passage_of_a_finisher_missing_an_intermediate_point():
    """445 arrivées pour 439 passages au vélo : finir sans être lu au vélo n'est
    ni un abandon ni une erreur de lecture."""
    runners, final = _runners(POINT_MANQUANT, "1291")

    assert [p.point_id for p in runners["435"].passages] == [1, 10]
    assert chronoweb._final_passage(runners["435"], final).cumulative != ""


def _splits(html: str, race_id: str, bib: str):
    rows = _rows(html, race_id)
    runner = next(r for r in chronoweb._group_runners(rows) if r.bib == bib)
    return chronoweb._split_times(runner, chronoweb._race_points(rows))


def test_split_times_fills_the_five_slots_of_a_triathlon():
    """Les transitions ne sont pas publiées : `cumul − intervalle − cumul précédent`
    les rend au caractère près (contrôlé contre la fiche individuelle du site)."""
    slots, segments = _splits(TRIATHLON, "1147", "360")

    assert slots == {
        "swim_time": "00:24:24", "t1_time": "00:07:01", "bike_time": "01:00:09",
        "t2_time": "00:02:26", "run_time": "00:39:26",
    }
    assert segments is None


def test_split_times_sum_equals_the_total_time():
    """SC-005 : les 5 segments d'un triathlon complet reconstituent le temps total."""
    slots, _ = _splits(TRIATHLON, "1147", "360")

    assert sum(chronoweb._seconds(t) for t in slots.values()) == chronoweb._seconds("02:13:26")


def test_split_times_computes_the_two_transitions_of_bib_347():
    slots, _ = _splits(TRIATHLON, "1147", "347")

    assert (slots["t1_time"], slots["t2_time"]) == ("00:11:03", "00:03:38")


def test_split_times_on_a_single_point_race_has_no_transition():
    """Un trail à un seul point : rien à intercaler, et surtout rien à inventer."""
    slots, segments = _splits(MONO_POINT, "1274", "152")

    assert list(slots) == ["run_time"]
    assert segments is None


def test_split_times_leaves_both_transitions_empty_when_a_point_is_missing():
    """Une transition dont un point encadrant manque ne se déduit pas."""
    slots, _ = _splits(POINT_MANQUANT, "1291", "435")

    assert slots.get("bike_time", "") == ""
    assert slots.get("t1_time", "") == ""
    assert slots.get("t2_time", "") == ""
    assert slots["swim_time"] and slots["run_time"]


def test_split_times_on_a_duathlon_fills_the_same_positional_slots():
    """Le motif décide du remplissage, pas la discipline : `Course → Vélo → Course`
    occupe les mêmes slots que `Natation → Vélo → Course`."""
    slots, segments = _splits(DUATHLON, "1033", "1")

    assert slots == {
        "swim_time": "00:17:54", "t1_time": "00:00:32", "bike_time": "00:34:44",
        "t2_time": "00:00:36", "run_time": "00:11:15",
    }
    assert segments is None


def test_duathlon_slots_are_relabelled_without_any_swim_key():
    """C'est `build_splits` qui étiquette : un duathlon ne publie pas de natation."""
    slots, _ = _splits(DUATHLON, "1033", "1")
    scraped = ScrapedResult(source_url=EVENT_URL, provider="chronoweb",
                            event_type="duathlon-s", **slots)

    assert build_splits(scraped) == {
        "course1": "00:17:54", "t1": "00:00:32", "bike": "00:34:44",
        "t2": "00:00:36", "course2": "00:11:15",
    }


def test_split_times_on_a_derived_single_point_ranking():
    """« Challenge 1er Tour » n'a qu'un point `Vélo` : un seul segment, aucune
    transition. On n'essaie pas de distinguer un classement dérivé d'une vraie
    épreuve mono-segment — un trail n'a lui aussi qu'un point."""
    slots, segments = _splits(DUATHLON, "1042", "64")

    assert list(slots) == ["bike_time"]
    assert segments is None


#: Les 6 couples (motif de points, `event_type` classé) réellement observés sur
#: les 89 épreuves du panel — cas dégradés du classifieur compris (« Les
#: Géraldines », un point `Course`, classé `triathlon` ; « Challenge 1er Tour »,
#: un point `Vélo`, classé `duathlon`).
_PANEL_COMBINATIONS = [
    (("Natation", "Vélo", "Course"), "triathlon-m"),
    (("Natation", "Vélo", "Course"), "triathlon-s"),
    (("Course", "Vélo", "Course"), "duathlon-s"),
    (("Natation", "Course"), "aquathlon"),
    (("Course",), "course-a-pied"),
    (("Course",), "triathlon"),
    (("Vélo",), "duathlon"),
]


@pytest.mark.parametrize("pattern, event_type", _PANEL_COMBINATIONS)
def test_no_filled_slot_is_dropped_by_the_sport_template(pattern, event_type):
    """Garde de non-régression sur le couple (motif observé, type classé).

    Le remplissage suit le motif, mais l'étiquetage aval suit le **type**, et
    `build_splits` omet les slots absents du gabarit de la discipline. Un motif
    `N→V→C` sur une épreuve classée `aquathlon` perdrait donc `bike` et `t2` — le
    mode d'échec que le dépôt a déjà payé une fois. Aucun couple du panel n'est
    dans ce cas ; ce test tombe le jour où l'un le devient.
    """
    slots = dict.fromkeys(chronoweb._POINT_PATTERNS[pattern], "00:01:00")
    scraped = ScrapedResult(source_url=EVENT_URL, provider="chronoweb",
                            event_type=event_type, **slots)

    assert len(build_splits(scraped)) == len(slots), (
        f"{event_type} : {len(slots) - len(build_splits(scraped))} segment(s) "
        f"rempli(s) par le motif {pattern} sont jetés par le gabarit"
    )


def test_split_times_falls_back_to_source_labels_beyond_five_points():
    """8 points alternés (4 relayeurs) : les 5 slots positionnels n'y suffisent pas.

    Le motif n'est pas reconnu → libellés publiés par la source, sans plafond.
    **Aucune transition ici** : re-sondé le 2026-07-30 sur les 14 équipes de
    l'épreuve, les 7 écarts `cumul − intervalle − cumul précédent` valent tous
    **zéro** — les points de cette épreuve sont contigus. Un temps mort nul n'est
    pas enregistré (FR-008), l'équipe sort donc à 8 segments et non 15.
    """
    slots, segments = _splits(AQUATHLON_RELAIS, "1184", "955")

    assert slots == {}
    assert segments == [
        ("Natation", "00:03:08"), ("Course", "00:08:27"),
        ("Natation", "00:03:06"), ("Course", "00:08:20"),
        ("Natation", "00:03:27"), ("Course", "00:08:53"),
        ("Natation", "00:02:53"), ("Course", "00:06:56"),
    ]


def test_repeated_segment_labels_never_overwrite_a_time():
    """« Natation » quatre fois : `build_splits` suffixe les collisions ` (N)`."""
    _, segments = _splits(AQUATHLON_RELAIS, "1184", "955")
    scraped = ScrapedResult(source_url=EVENT_URL, provider="chronoweb",
                            event_type="aquathlon", segments=segments)

    splits = build_splits(scraped)

    assert len(splits) == 8
    assert splits["Natation"] == "00:03:08"
    assert splits["Natation (4)"] == "00:02:53"
    assert splits["Course (4)"] == "00:06:56"


def test_split_times_inserts_a_dead_time_on_an_unrecognised_pattern():
    """Cas construit — le panel n'a qu'un seul motif non reconnu, et ses points
    sont contigus. La règle vaut pourtant partout (FR-008) : un temps mort de
    relais est du temps de course réel, et rien en aval ne le rattraperait."""
    runner = chronoweb.Runner(bib="1", name="X", category="", passages=[
        chronoweb.Passage(point_id=1, point_name="Natation",
                          cumulative="00:10:00", segment="00:10:00"),
        chronoweb.Passage(point_id=2, point_name="Course",
                          cumulative="00:21:30", segment="00:11:00"),
        chronoweb.Passage(point_id=3, point_name="Natation",
                          cumulative="00:31:30", segment="00:10:00"),
    ])

    _, segments = chronoweb._split_times(
        runner, [(1, "Natation"), (2, "Course"), (3, "Natation")])

    assert segments == [
        ("Natation", "00:10:00"), ("Changement", "00:00:30"), ("Course", "00:11:00"),
        ("Natation", "00:10:00"),
    ]


@pytest.mark.parametrize("category, gender", [
    # FFTRI : le genre est le **préfixe**.
    ("MSE", "M"), ("FV1", "F"), ("MCA", "M"), ("FPU", "F"),
    # FFA : le genre est le **suffixe**. `M0F` est une femme malgré son M initial —
    # lire le premier caractère masculiniserait les 36 codes féminins masters.
    ("SEM", "M"), ("V1F", "F"), ("M0F", "F"), ("M1M", "M"), ("JUF", "F"),
    # Catégories « toutes classes » et catégories d'équipe.
    ("MASC", "M"), ("FEM", "F"),
    ("MIXT", ""), ("DUOX", ""), ("DUOM", ""), ("DUOF", ""),
    ("", ""), ("XYZ", ""),
])
def test_gender_from_category(category, gender):
    assert chronoweb._gender_from_category(category) == gender


def _results(html: str, race_id: str, meta: chronoweb.EventMeta | None = None):
    soup = chronoweb._soup(html)
    meta = meta or chronoweb._parse_event_meta(soup)
    race = next(r for r in chronoweb._parse_races(soup, meta) if r.race_id == race_id)
    rows = _rows(html, race_id)
    points, final = chronoweb._race_points(rows), chronoweb._final_point(rows)
    return [chronoweb._build_result(runner, race, meta, points, final, EVENT_URL, "323")
            for runner in chronoweb._group_runners(rows)]


def _result(html: str, race_id: str, bib: str, meta: chronoweb.EventMeta | None = None):
    return next(r for r in _results(html, race_id, meta) if r.bib_number == bib)


def test_build_result_maps_a_finisher_field_by_field():
    result = _result(TRIATHLON, "1147", "360")

    assert result.event_name == "Triathlon d'Oléron 2024 - Triathlon M"
    assert result.event_date == date(2024, 10, 6)
    assert result.event_type == "triathlon-m"
    assert (result.athlete_name, result.athlete_firstname) == ("MARIN", "Thomas")
    assert (result.category, result.gender) == ("MSE", "M")
    assert result.total_time == "02:13:26"
    assert (result.rank_overall, result.rank_category) == (1, 1)
    assert result.provider == "chronoweb"
    assert result.source_url == EVENT_URL


def test_build_result_leaves_empty_what_the_source_never_publishes():
    """Ni club, ni distance, ni rang de genre, ni statut — limites de la source,
    pas du fournisseur. `club` vide place ces participations hors `scope=club`."""
    result = _result(TRIATHLON, "1147", "360")

    assert result.club == ""
    assert result.status == ""
    assert result.distance_km is None
    assert result.rank_gender is None


def test_build_result_keeps_every_passage_in_raw_data():
    """Rangs intermédiaires, vitesses et gains de place n'ont pas de colonne au
    modèle : ils voyagent ici plutôt que d'être jetés."""
    result = _result(TRIATHLON, "1147", "360")

    assert result.raw_data["event_id"] == "323"
    assert result.raw_data["race_id"] == "1147"
    assert result.raw_data["race_label"] == "Triathlon M"
    assert [p["point_id"] for p in result.raw_data["points"]] == [1, 8, 14]
    assert result.raw_data["points"][0] == {
        "point_id": 1, "name": "Natation", "cumulative": "00:24:24",
        "segment": "00:24:24", "rank_overall": 1, "rank_category": 1,
        "speed": "1:38 min/100m", "rank_gain": "--",
    }


def test_build_result_of_a_non_finisher_has_no_time_and_no_rank():
    """Son rang au vélo reste lisible dans les données brutes, mais n'entre dans
    aucun classement : il doublonnerait celui d'un finisher."""
    result = _result(TRIATHLON, "1147", "187")

    assert result.total_time == ""
    assert result.rank_overall is None
    assert result.rank_category is None
    assert [p["rank_overall"] for p in result.raw_data["points"]] == [5, 24]


def test_no_overall_rank_appears_twice_in_an_individual_race():
    """SC-003 : c'est cette unicité que promeut le refus des rangs intermédiaires."""
    ranks = [r.rank_overall for r in _results(TRIATHLON, "1147") if r.rank_overall]

    assert len(ranks) == len(set(ranks))


def test_build_result_keeps_a_team_name_whole():
    """Le découpage nom/prénom des individus mutile 52 des 707 équipes du panel
    (« LIMOGES METROPOLE 2 » → prénom « 2 ») et fusionnerait deux équipes d'un
    même club sous une seule identité."""
    result = _result(DUATHLON, "1035", "504")

    assert result.is_relay is True
    assert result.athlete_name == "TRIPOTES TEAM GOLFECH RELAIS1"
    assert result.athlete_firstname == ""


def test_a_team_category_never_marks_an_individual_race_as_a_relay():
    """Contre-épreuve : `MASC` en « Triathlon M » est une catégorie « toutes
    classes », pas un marqueur d'équipe — seul le libellé d'épreuve le pose.

    Le prénom vide de cette ligne ne vient donc pas du chemin relais mais de
    `split_athlete_name`, dont c'est la limite documentée sur un nom tout en
    majuscules (« JEAN BONNEAU » : les deux lectures sont légitimes)."""
    result = _result(TRIATHLON, "1147", "422")

    assert result.is_relay is False
    assert result.gender == "M"
    assert (result.athlete_name, result.athlete_firstname) == ("JEAN BONNEAU", "")


def _scrape(monkeypatch, client: FakeClient, url: str = EVENT_URL):
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: client)
    return chronoweb.scrape_event_all(url)


def test_scrape_event_all_imports_every_race_of_the_event(monkeypatch):
    """Une URL désigne un événement : les 3 épreuves d'Oléron 2024 sortent
    ensemble, chacune sous son propre nom de course."""
    results = _scrape(monkeypatch, FakeClient())

    assert len(results) == 8
    assert sorted({r.event_name for r in results}) == [
        "Triathlon d'Oléron 2024 - Triathlon M",
        "Triathlon d'Oléron 2024 - Triathlon S",
        "Triathlon d'Oléron 2024 - Triathlon XS",
    ]
    assert {r.source_url for r in results} == {EVENT_URL}


def test_scrape_event_all_never_repeats_a_bib_within_a_race(monkeypatch):
    results = _scrape(monkeypatch, FakeClient())

    keys = [(r.event_name, r.bib_number) for r in results]
    assert len(keys) == len(set(keys))


def test_scrape_event_all_makes_at_most_two_requests(monkeypatch):
    """Le classement puis le catalogue — et jamais la fiche individuelle, cassée
    à la source sur les épreuves mono-point."""
    client = FakeClient()

    _scrape(monkeypatch, client)

    assert len(client.calls) == 2
    assert client.calls[0] == EVENT_URL
    assert not any("resultats_participant.php" in call for call in client.calls)


def test_scrape_event_all_reads_the_city_from_the_catalogue(monkeypatch):
    """La commune publiée (« St Georges d'Oléron ») est plus juste que celle
    déduite du nom d'épreuve (« Oléron »)."""
    results = _scrape(monkeypatch, FakeClient())

    assert {r.raw_data["city"] for r in results} == {"St Georges d'Oléron"}


def test_scrape_event_all_survives_a_failing_catalogue(monkeypatch, caplog):
    client = FakeClient(catalogue_status=500)

    results = _scrape(monkeypatch, client)

    assert len(results) == 8
    assert all("city" not in r.raw_data for r in results)
    assert len(client.calls) == 2
    assert any("catalogue unreachable" in r.getMessage() for r in caplog.records)


def test_scrape_event_all_survives_an_event_absent_from_the_catalogue(monkeypatch):
    """Le catalogue ne porte pas l'événement demandé : import complet, sans ville."""
    client = FakeClient(catalogue=_fixture("catalogue").replace("event=323", "event=999"))

    results = _scrape(monkeypatch, client)

    assert len(results) == 8
    assert all("city" not in r.raw_data for r in results)


def test_scrape_event_all_keeps_no_state_between_two_imports(monkeypatch):
    """`PROVIDERS` tient des instances singleton : un cache d'instance serait un
    cache de processus, y compris entre tests, pour ~340 Ko économisés."""
    client = FakeClient()
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: client)

    chronoweb.scrape_event_all(EVENT_URL)
    chronoweb.scrape_event_all(EVENT_URL)

    assert client.calls.count(f"{chronoweb.BASE_URL}{chronoweb.CATALOGUE_PATH}") == 2


def test_scrape_event_all_carries_the_splits_of_a_verified_runner(monkeypatch):
    """Contrôle de bout en bout sur le dossard vérifié à la main contre le site."""
    results = _scrape(monkeypatch, FakeClient())

    runner = next(r for r in results if r.bib_number == "360")
    assert (runner.swim_time, runner.t1_time, runner.bike_time,
            runner.t2_time, runner.run_time) == (
        "00:24:24", "00:07:01", "01:00:09", "00:02:26", "00:39:26")


def test_canonical_url_truncates_an_individual_sheet_to_its_event():
    """2 des 5 URLs chronoweb du Sheet sont des fiches individuelles. Leur
    événement est justement l'unité d'import : rien n'est perdu."""
    event_347 = "https://chronoweb.com/resultats_evenement.php?event=347"

    assert chronoweb.canonical_url(
        "https://chronoweb.com/resultats_participant.php?event=347&epreuve=1234&bib=599"
    ) == event_347
    assert chronoweb.canonical_url(
        "https://chronoweb.com/resultats_participant.php?event=347&epreuve=1235&bib=1563"
    ) == event_347


def test_the_four_sheet_spellings_of_one_event_collapse_into_one_url():
    spellings = [
        "https://chronoweb.com/resultats_evenement.php?event=323&epreuve=1147",
        "https://chronoweb.com/resultats_evenement.php?event=323&epreuve=1148&cat=all&point=10",
        "https://www.chronoweb.com/resultats_evenement.php?event=323",
        "https://chronoweb.com/resultats_participant.php?event=323&epreuve=1147&bib=360",
    ]

    assert {chronoweb.canonical_url(url) for url in spellings} == {EVENT_URL}


def test_scrape_event_all_from_an_individual_sheet_imports_the_whole_event(monkeypatch):
    client = FakeClient()

    results = _scrape(
        monkeypatch, client,
        "https://chronoweb.com/resultats_participant.php?event=323&epreuve=1147&bib=360",
    )

    assert len(results) == 8
    assert client.calls[0] == EVENT_URL
    assert not any("resultats_participant.php" in call for call in client.calls)


def test_two_spellings_of_one_event_yield_identical_results(monkeypatch):
    """Deux graphies du même événement ne doivent rien dupliquer en aval."""
    first = _scrape(monkeypatch, FakeClient(),
                    "https://chronoweb.com/resultats_evenement.php?event=323&epreuve=1147")
    second = _scrape(monkeypatch, FakeClient(),
                     "https://chronoweb.com/resultats_participant.php?event=323&bib=360")

    assert first == second


@pytest.mark.parametrize("url", [
    # Réellement présente dans le Sheet : une archive de résultats, pas une page.
    "https://chronoweb.com/files/pdf/Resultats_Triathlon_dOlron_2025.zip",
    "https://chronoweb.com/resultats_evenement.php",
    "https://chronoweb.com/",
])
def test_scrape_event_all_refuses_a_url_without_an_event_id(monkeypatch, url):
    """Refus **avant** tout réseau : le scraper ne doit jamais tenter de parser
    un binaire. Le message nomme la forme attendue, faute de quoi l'opérateur ne
    peut pas corriger la source."""
    client = FakeClient()
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: client)

    with pytest.raises(ValueError) as excinfo:
        chronoweb.scrape_event_all(url)

    assert "resultats_evenement.php?event=" in str(excinfo.value)
    assert client.calls == []


def test_scrape_event_all_reports_an_unknown_event_id(monkeypatch):
    """Le site répond 200 avec « Aucun évènement trouvé avec cet ID » : sans
    garde, une URL fausse passerait pour un événement sans classement publié."""
    with pytest.raises(ValueError, match="introuvable"):
        _scrape(monkeypatch, FakeClient(event=INCONNU))


def test_scrape_event_all_on_an_event_without_ranking_is_not_an_error(monkeypatch):
    """Chalain 2015 : nom présent, aucun tableau. Import vide, zéro exception —
    `import_service` le compte déjà en 0 importé."""
    assert _scrape(monkeypatch, FakeClient(event=SANS_CLASSEMENT)) == []


def test_the_two_failures_are_told_apart_by_their_message(monkeypatch):
    """« introuvable » et « sans classement » sont deux causes distinctes : c'est
    ce que l'opérateur lit dans « Épreuves en erreur (détail) » des bilans CLI."""
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: FakeClient(event=INCONNU))
    with pytest.raises(ValueError) as unknown:
        chronoweb.scrape_event_all(EVENT_URL)

    with pytest.raises(ValueError) as no_id:
        chronoweb.scrape_event_all("https://chronoweb.com/files/pdf/x.zip")

    assert str(unknown.value) != str(no_id.value)


def test_parse_races_tolerates_an_event_without_any_ranking():
    """Chalain 2015 annonce une épreuve et ne publie aucun tableau : pas une erreur."""
    soup = chronoweb._soup(SANS_CLASSEMENT)
    races = chronoweb._parse_races(soup, chronoweb._parse_event_meta(soup))

    assert [r.label for r in races] == ["M"]
