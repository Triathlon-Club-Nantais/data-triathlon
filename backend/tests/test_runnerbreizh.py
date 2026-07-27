"""Unit tests for scrapers/runnerbreizh.py (no network).

Fixtures are real excerpts of www.runnerbreizh.fr captured on 2026-07-27, trimmed
to a few rows: decorative attributes were dropped, the structure (`table#titre-courses`
for the banner, `table.tableau-courses` with one header row then data rows, 8 cells
per row) is intact. Ground truth:
`docs/superpowers/specs/2026-07-27-runnerbreizh-sondage.md`.

Naming follows constitution principle I: English for technical identifiers,
French only for business rationale in comments.
"""
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.scrapers import runnerbreizh
from app.services.geocode_service import extract_city
from app.services.mapping import build_splits

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / f"runnerbreizh_{name}.html").read_text(encoding="utf-8")


PAGE1_TRIATHLON = _fixture("page1_triathlon")   # Quiberon M 2025, 3 rows
PAGE_LAST = _fixture("page2_derniere")          # last, partial page
PAGE_EMPTY = _fixture("page_vide")              # past the last page, valid title
PAGE_UNKNOWN = _fixture("page_introuvable")     # unknown event id: blank title
DUATHLON = _fixture("duathlon")                 # misleading column labels
AQUATHLON = _fixture("aquathlon")               # empty bike cell
DUO = _fixture("duo")                           # relay: shared time and rank
ANOMALIES = _fixture("lignes_anomales")         # anonymous, mangled name, off-format
REPUBLISHED = _fixture("republication")         # "Chronométrée par BREIZHCHRONO"

EVENT_URL = (
    "https://www.runnerbreizh.fr/requetetriathlons.php"
    "?CourseFichierGpsNom=2025-09-0749quiberon"
)


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text, self.status_code = text, status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPError(f"HTTP {self.status_code}")


class FakeClient:
    """Fake HTTP client: serves fixtures by page number, records every call.

    Recording matters as much as serving: the network cost (`pages + 1` requests,
    never one per participant) is an asserted invariant, not a hope.
    """

    def __init__(self, pages: dict[int, str], default: str | None = None):
        self.pages = pages
        self.default = default if default is not None else PAGE_EMPTY
        self.calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url: str):
        self.calls.append(url)
        page = 1
        if "page=" in url:
            page = int(url.split("page=")[1].split("&")[0])
        return FakeResponse(self.pages.get(page, self.default))


def test_parse_title_reads_event_metadata():
    meta = runnerbreizh._parse_title(PAGE1_TRIATHLON)

    assert meta.name == "Triathlon de Quiberon M"
    assert meta.event_date == date(2025, 9, 7)
    assert meta.city == "Quiberon"
    assert meta.distance_km == 49.5
    assert meta.event_type == "triathlon-m"


def test_parse_title_strips_the_per_segment_distances():
    """« Triathlon de Quiberon M (1.5/38/10) » → « Triathlon de Quiberon M ».

    Le suffixe de distances n'est pas cosmétique : gardé dans le nom, il rend
    l'épreuve introuvable pour l'extraction de commune de la carte, et fabrique un
    doublon si la même épreuve arrive par un autre fournisseur (SC-008).
    """
    meta = runnerbreizh._parse_title(PAGE1_TRIATHLON)

    assert "(" not in meta.name
    assert extract_city(meta.name) == "Quiberon"


def test_result_rows_skips_the_header_row():
    rows = runnerbreizh._result_rows(PAGE1_TRIATHLON)

    assert len(rows) == 3
    assert "Nom et Prénom" not in rows[0].get_text()


def test_result_rows_is_empty_past_the_last_page():
    """Le critère d'arrêt de la pagination : la table n'a plus que son en-tête."""
    assert runnerbreizh._result_rows(PAGE_EMPTY) == []


def test_result_rows_tolerates_a_missing_table():
    assert runnerbreizh._result_rows("<html><body>rien</body></html>") == []


def _cells(html: str, row: int = 0):
    return runnerbreizh._result_rows(html)[row].find_all("td")


def test_parse_segment_cell_splits_time_rank_gap_and_speed():
    cell = runnerbreizh._parse_segment_cell(_cells(PAGE1_TRIATHLON)[2])

    assert cell.time == "00:23:14"
    assert cell.rank == 2
    assert cell.gap == "0.62%"
    assert cell.speed == "3.87 km/h"


def test_parse_segment_cell_on_an_empty_cell_yields_no_time():
    """L'aquathlon garde sa colonne « Vélo » affichée mais vide : pas un défaut,
    pas un segment non plus."""
    cell = runnerbreizh._parse_segment_cell(_cells(AQUATHLON)[3])

    assert cell.time == ""
    assert cell.rank is None


def _first_result(html: str, url: str = EVENT_URL, page: int = 1):
    meta = runnerbreizh._parse_title(html)
    rows = runnerbreizh._result_rows(html)
    return runnerbreizh._parse_row(rows[0], meta, url, page)


def test_parse_row_fills_the_participant_fields():
    result = _first_result(PAGE1_TRIATHLON)

    assert (result.athlete_name, result.athlete_firstname) == ("ABDELMOULA", "Jawad")
    assert result.total_time == "01:45:35"
    assert result.rank_overall == 1
    assert result.rank_category == 1
    assert result.category == "SEM"
    assert result.gender == "M"
    assert result.provider == "runnerbreizh"
    assert result.source_url == EVENT_URL


def test_parse_row_fills_the_positional_segment_slots():
    """Colonnes 2/3/5 → slots swim/bike/run, sans lire les libellés d'en-tête.

    Les transitions ne sont pas publiées : T1 et T2 restent vides, et c'est
    `mapping.build_splits` qui décidera des libellés selon la discipline.
    """
    result = _first_result(PAGE1_TRIATHLON)

    assert result.swim_time == "00:23:14"
    assert result.bike_time == "00:49:06"
    assert result.run_time == "00:30:43"
    assert (result.t1_time, result.t2_time) == ("", "")
    assert result.segments is None


def test_parse_row_leaves_bib_and_club_empty():
    """Le site n'en publie aucun : le dossard vide fait jouer la déduplication de
    repli par athlète, et le club vide sort la participation du périmètre TCN —
    arbitré, cf. spec FR-015."""
    result = _first_result(PAGE1_TRIATHLON)

    assert result.bib_number == ""
    assert result.club == ""
    assert result.status == ""


def test_parse_row_reads_female_gender_from_the_category():
    """« 29/SEF » → F. La catégorie est la seule source disponible sur **toutes**
    les lignes : la classe du lien coureur (`<a class="M">`) n'existe que pour les
    inscrits au site, 16 lignes sur 50 à Quiberon."""
    rows = runnerbreizh._result_rows(ANOMALIES)
    meta = runnerbreizh._parse_title(ANOMALIES)
    result = runnerbreizh._parse_row(rows[2], meta, EVENT_URL, 1)

    assert result.category == "SEF"
    assert result.gender == "F"


def test_raw_data_keeps_what_the_model_has_no_column_for():
    """Rangs par segment, écarts, vitesses, rang avant la dernière CàP, évolutions
    et taille du plateau : rien de tout cela n'a de colonne, et rien n'est perdu."""
    result = _first_result(PAGE1_TRIATHLON)
    raw = result.raw_data

    assert raw["page"] == 1
    assert raw["field_size"] == 322
    assert raw["rank_trend"] == "↗ 1"
    assert raw["percentile"] == "0.31%"
    assert raw["rank_before_run"] == 2
    assert raw["rank_before_run_trend"] == "="
    assert raw["segment_details"] == [
        {"position": 1, "time": "00:23:14", "rank": 2, "gap": "0.62%", "speed": "3.87 km/h"},
        {"position": 2, "time": "00:49:06", "rank": 1, "gap": "0.31%", "speed": "46.43 km/h"},
        {"position": 3, "time": "00:30:43", "rank": 1, "gap": "0.31%", "speed": "19.53 km/h"},
    ]


def test_raw_data_keeps_the_runner_id_when_the_site_links_the_athlete():
    """`di=709927` n'existe que pour les coureurs inscrits au site : présent, il
    est conservé ; absent, la clé ne mentira pas en valant autre chose que ""."""
    rows = runnerbreizh._result_rows(PAGE1_TRIATHLON)
    meta = runnerbreizh._parse_title(PAGE1_TRIATHLON)

    linked = runnerbreizh._parse_row(rows[2], meta, EVENT_URL, 1)
    unlinked = runnerbreizh._parse_row(rows[0], meta, EVENT_URL, 1)

    assert linked.raw_data["runner_id"] == "709927"
    assert unlinked.raw_data["runner_id"] == ""


def test_anonymous_row_keeps_its_raw_label_as_the_name():
    """« ?DOSSARD #9998 » : 3 lignes sur 322 à Quiberon (mesuré à l'import réel).

    Le libellé entier devient le nom, sans prénom : `split_athlete_name` en ferait
    (« ?DOSSARD », « #9998 »), et l'UI afficherait « #9998 » comme un prénom. Ces
    lignes sont importées et non écartées — les retirer créerait autant de trous
    dans le classement, que l'indice de fiabilité compte en anomalies et qui
    masqueraient le ratio de place de toute l'épreuve.
    """
    result = _first_result(ANOMALIES)

    assert result.athlete_name == "?DOSSARD #9998"
    assert result.athlete_firstname == ""
    assert result.bib_number == ""
    assert result.total_time == "02:15:15"
    assert result.rank_overall == 75
    # Catégorie « 0 /M » : le site n'a pas de rang de catégorie à donner, mais le
    # genre y reste lisible.
    assert (result.rank_category, result.category, result.gender) == (0, "M", "M")


def test_mangled_name_is_kept_verbatim():
    """« PROD?HOMME Anais » : le `?` est dans le HTML servi (vérifié à l'octet).

    On ne devine pas l'apostrophe : la graphie corrigée, si elle arrive par un
    autre fournisseur, sera réconciliée par le mécanisme de l'issue #66.
    """
    rows = runnerbreizh._result_rows(ANOMALIES)
    meta = runnerbreizh._parse_title(ANOMALIES)

    result = runnerbreizh._parse_row(rows[2], meta, EVENT_URL, 1)

    assert result.athlete_name == "PROD?HOMME"
    assert result.athlete_firstname == "Anais"


def test_off_format_row_is_skipped_and_logged(caplog):
    """Une ligne à 7 cellules est ignorée, pas lue à l'aveugle : un décalage de
    colonne rangerait une vitesse dans un temps de segment."""
    rows = runnerbreizh._result_rows(ANOMALIES)
    meta = runnerbreizh._parse_title(ANOMALIES)

    with caplog.at_level("WARNING"):
        result = runnerbreizh._parse_row(rows[3], meta, EVENT_URL, 1)

    assert result is None
    assert "7 cells" in caplog.text


def test_duathlon_splits_are_relabelled_run_bike_run():
    """En duathlon, « 1ère épreuve » est une course à pied et « CàP » la seconde.

    Le scraper ne lit aucun libellé d'en-tête : il remplit les slots positionnels,
    et c'est `mapping.build_splits` qui les nomme d'après la discipline. Ce test
    verrouille l'accord entre les deux — un ordre de slots inversé le casserait.
    """
    result = _first_result(DUATHLON)

    assert result.event_type == "duathlon-s"
    assert build_splits(result) == {
        "course1": "00:16:03",
        "bike": "00:30:16",
        "course2": "00:08:10",
    }


def test_aquathlon_yields_no_bike_segment():
    """La colonne « Vélo » reste affichée mais vide : aucun segment vélo ne doit
    apparaître, ni dans les slots, ni dans les splits."""
    result = _first_result(AQUATHLON)

    assert result.event_type == "aquathlon"
    assert result.bike_time == ""
    assert build_splits(result) == {"swim": "00:18:04", "run": "00:19:21"}


def test_triathlon_splits_keep_the_swim_bike_run_labels():
    result = _first_result(PAGE1_TRIATHLON)

    assert build_splits(result) == {
        "swim": "00:23:14",
        "bike": "00:49:06",
        "run": "00:30:43",
    }


def test_duo_rows_are_flagged_as_relay_and_share_time_and_rank():
    """« TriBreizh en Duo » publie une ligne par équipier, temps et rang partagés.

    Les deux lignes sont importées : ce sont deux participations réelles. Le rang
    partagé fera sortir l'épreuve comme « non fiable » selon la règle actuelle de
    l'indice de qualité — limite connue et documentée, hors périmètre de #56.
    """
    meta = runnerbreizh._parse_title(DUO)
    rows = runnerbreizh._result_rows(DUO)
    results = [runnerbreizh._parse_row(r, meta, EVENT_URL, 1) for r in rows]

    assert len(results) == 4
    assert all(r.is_relay for r in results)
    assert [r.total_time for r in results[:2]] == ["04:45:06", "04:45:06"]
    assert [r.rank_overall for r in results[:2]] == [1, 1]
    assert {r.athlete_name for r in results[:2]} == {"THOMAS", "COGREL"}


def test_relay_is_detected_from_the_event_name_and_from_the_category():
    """Deux signaux indépendants : le nom qualifie l'épreuve entière, la catégorie
    confirme ligne à ligne. Un seul des deux suffit."""
    assert runnerbreizh._is_relay("TriBreizh en Duo L", "1/SEM") is True
    assert runnerbreizh._is_relay("Triathlon de Quiberon M", "1/M+M") is True
    assert runnerbreizh._is_relay("Triathlon en Relais de X", "") is True
    assert runnerbreizh._is_relay("Triathlon de Quiberon M", "1/SEM") is False


def test_team_category_leaves_the_gender_unset():
    """« M+F » décrit la composition de l'équipe, pas la personne de la ligne :
    en déduire un genre en donnerait un faux à l'un des deux équipiers."""
    meta = runnerbreizh._parse_title(DUO)
    rows = runnerbreizh._result_rows(DUO)
    mixed = [runnerbreizh._parse_row(r, meta, EVENT_URL, 1) for r in rows[2:]]

    assert [r.category for r in mixed] == ["M+F", "M+F"]
    assert {r.gender for r in mixed} == {""}


def test_parse_row_carries_the_event_metadata():
    result = _first_result(PAGE1_TRIATHLON)

    assert result.event_name == "Triathlon de Quiberon M"
    assert result.event_date == date(2025, 9, 7)
    assert result.event_type == "triathlon-m"
    assert result.distance_km == 49.5


# ---------------------------------------------------------------------------
# scrape_event_all: pagination, network cost, refusals
# ---------------------------------------------------------------------------


def _fake_client(monkeypatch, pages: dict[int, str], default: str | None = None):
    client = FakeClient(pages, default)
    monkeypatch.setattr(runnerbreizh.httpx, "Client", lambda *a, **k: client)
    return client


def test_scrape_event_all_walks_every_page(monkeypatch):
    _fake_client(monkeypatch, {1: PAGE1_TRIATHLON, 2: PAGE_LAST})

    results = runnerbreizh.scrape_event_all(EVENT_URL)

    assert len(results) == 5
    assert [r.raw_data["page"] for r in results] == [1, 1, 1, 2, 2]


def test_scrape_event_all_costs_pages_plus_one_requests(monkeypatch):
    """`pages + 1` requêtes, jamais une par participant.

    L'invariant est asserté, pas espéré : c'est la garde contre une régression du
    type « une requête par fiche », que le coût de T2Area rend tentante alors que
    rien ne l'exige ici.
    """
    client = _fake_client(monkeypatch, {1: PAGE1_TRIATHLON, 2: PAGE_LAST})

    runnerbreizh.scrape_event_all(EVENT_URL)

    assert len(client.calls) == 3
    assert "page=1" in client.calls[0]
    assert "page=3" in client.calls[-1]


def test_scrape_event_all_stops_on_the_first_empty_page(monkeypatch):
    """Le total annoncé (`/31` pour 62 lignes en relais) ne peut pas borner la
    pagination : seule la première page sans ligne l'arrête."""
    client = _fake_client(monkeypatch, {1: DUO})

    results = runnerbreizh.scrape_event_all(EVENT_URL)

    assert len(results) == 4
    assert len(client.calls) == 2


def test_scrape_event_all_on_an_event_without_ranking_returns_empty(monkeypatch):
    """Titre valide mais aucune ligne : une épreuve sans classé publié, pas une
    erreur — à distinguer de l'identifiant inconnu."""
    _fake_client(monkeypatch, {1: PAGE_EMPTY})

    assert runnerbreizh.scrape_event_all(EVENT_URL) == []


def test_republished_event_logs_a_warning(monkeypatch, caplog):
    """« Chronométrée par BREIZHCHRONO » : un provider que nous scrapons nativement,
    avec dossards **et** clubs. Aucune URL source n'est reconstructible (le lien ne
    pointe que l'accueil du chronométreur), d'où un avertissement à l'opérateur."""
    _fake_client(monkeypatch, {1: REPUBLISHED})

    with caplog.at_level("WARNING"):
        results = runnerbreizh.scrape_event_all(EVENT_URL)

    assert "BREIZHCHRONO" in caplog.text
    assert results[0].raw_data["timekeeper"] == "BREIZHCHRONO"


def test_event_without_timekeeper_mention_logs_nothing(monkeypatch, caplog):
    _fake_client(monkeypatch, {1: PAGE1_TRIATHLON})

    with caplog.at_level("WARNING"):
        results = runnerbreizh.scrape_event_all(EVENT_URL)

    assert caplog.text == ""
    assert "timekeeper" not in results[0].raw_data


# ---------------------------------------------------------------------------
# URL canonicalisation: the real Sheet spellings
# ---------------------------------------------------------------------------

#: The four shapes actually found in the Sheet, plus the bare form.
SHEET_SHAPES = [
    "https://www.runnerbreizh.fr/requetetriathlons.php?CourseFichierGpsNom=2025-09-0749quiberon",
    "https://www.runnerbreizh.fr/requetetriathlons.php"
    "?CourseFichierGpsNom=2025-09-0749quiberon&page=2&tricourse=&Sexe=",
    "https://www.runnerbreizh.fr/requetetriathlons.php"
    "?CourseFichierGpsNom=2025-09-0749quiberon&page=3&tricourse=4&Sexe=F",
    "https://runnerbreizh.fr/requetetriathlons.php"
    "?CourseFichierGpsNom=2025-09-0749quiberon&page=7",
]


@pytest.mark.parametrize("url", SHEET_SHAPES)
def test_canonical_url_drops_every_view_parameter(url):
    """`page`, `tricourse` et `Sexe` sont des vues de la même épreuve.

    `Sexe=F` renvoie un sous-ensemble : le garder amputerait l'import. Et les deux
    graphies du Sheet doivent converger, sans quoi une même épreuve porterait deux
    clés de cache TTL.
    """
    assert runnerbreizh.canonical_url(url) == EVENT_URL


def test_canonical_url_encodes_an_apostrophe_in_the_event_id():
    """Cas réel : `2026-07-05112lessables-d'olonne`."""
    canonical = runnerbreizh.canonical_url(
        "https://www.runnerbreizh.fr/requetetriathlons.php"
        "?CourseFichierGpsNom=2026-07-05112lessables-d%27olonne&page=2"
    )

    assert canonical.endswith("CourseFichierGpsNom=2026-07-05112lessables-d%27olonne")


def test_scrape_from_an_intermediate_page_starts_over_at_page_one(monkeypatch):
    """8 des 10 liens du Sheet pointent une page intermédiaire : partir de là
    perdrait les premières pages, donc les meilleurs classés — silencieusement."""
    client = _fake_client(
        monkeypatch, {1: PAGE1_TRIATHLON, 2: PAGE_LAST},
    )

    results = runnerbreizh.scrape_event_all(SHEET_SHAPES[2])

    assert len(results) == 5
    assert "page=1" in client.calls[0]
    assert all(r.source_url == EVENT_URL for r in results)


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------


def test_runner_profile_url_is_refused_before_any_request(monkeypatch):
    """La fiche coureur est un palmarès multi-épreuves, pas une épreuve : le
    fan-out mesuré coûterait ~130 requêtes et produirait N Course pour une URL."""
    client = _fake_client(monkeypatch, {})

    with pytest.raises(ValueError, match="ne désigne pas une épreuve"):
        runnerbreizh.scrape_event_all(
            "https://www.runnerbreizh.fr/triathlons.php?CoureurNom=KUENTZ&CoureurPrenom=Olivier"
        )

    assert client.calls == []


def test_refusal_message_names_the_expected_url_shape():
    """Le message est ré-affiché verbatim par le front et par le détail des échecs
    de la CLI : il doit dire à l'opérateur quoi corriger."""
    with pytest.raises(ValueError) as excinfo:
        runnerbreizh.canonical_url("https://www.runnerbreizh.fr/liste_triathlons.php")

    message = str(excinfo.value)
    assert "requetetriathlons.php" in message
    assert "CourseFichierGpsNom" in message
    assert "fiche coureur" in message


def test_unknown_event_id_is_refused_rather_than_read_as_empty(monkeypatch):
    """Identifiant inconnu : le site répond 200 avec un `<title>` vide et aucune
    ligne. Sans cette garde, l'épreuve passerait pour un classement non publié, et
    `_require_event_name` n'a rien à refuser dans une liste vide."""
    _fake_client(monkeypatch, {1: PAGE_UNKNOWN})

    with pytest.raises(ValueError, match="introuvable"):
        runnerbreizh.scrape_event_all(EVENT_URL)
