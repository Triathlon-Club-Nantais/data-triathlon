"""
Tests unitaires pour scrapers/sportinnovation.py (sans réseau).

Couvre les helpers purs : parsing de la cellule nom ("NOM PrénomG-CatG"),
mapping des colonnes depuis l'en-tête, construction d'un résultat depuis une
ligne HTML, détection du type d'épreuve, et extraction des métadonnées
(nom d'événement + date) depuis la page de détail d'un participant.
"""
from datetime import date
from pathlib import Path

import pytest

from app.scrapers import sportinnovation as _si
from app.scrapers.classify import classify_event_type
from app.scrapers.sportinnovation import (
    _classify_results_url,
    _col_indices,
    _compose_course_name,
    _parse_api_athlete,
    _parse_html_row,
    _parse_name_cell,
    _parse_race_meta,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_name_cell_standard():
    """'GUEGANO JordanH-S3H' → (GUEGANO, Jordan, H, S3H)."""
    lastname, firstname, gender, cat = _parse_name_cell("GUEGANO JordanH-S3H")
    assert lastname == "GUEGANO"
    assert firstname == "Jordan"
    assert gender == "H"
    assert cat == "S3H"


def test_parse_name_cell_composed_lastname_known_limitation():
    """
    Limite connue : pour un nom de famille composé ("LE GALL"), `_NAME_RE` rattache
    le second mot au prénom (la classe prénom accepte les majuscules). Le genre et la
    catégorie restent corrects. Test verrouillant le comportement actuel — à mettre à
    jour si le regex est amélioré.
    """
    lastname, firstname, gender, cat = _parse_name_cell("LE GALL MarieF-V1F")
    assert lastname == "LE"
    assert firstname == "GALL Marie"
    assert gender == "F"
    assert cat == "V1F"


def test_classify_event_type():
    assert classify_event_type("Triathlon M") == "triathlon-m"
    assert classify_event_type("Triathlon S") == "triathlon-s"
    assert classify_event_type("Aquathlon du RC Doué") == "aquathlon"
    assert classify_event_type("Bike & Run d'Halloween") == "bike-run"
    assert classify_event_type("SwimRun des Îles") == "swimrun"
    assert classify_event_type("Duathlon Sprint") == "duathlon-s"


HEADERS = ["Place", "Dossard", "Nom", "Club", "Tps Off.", "Nat", "T1", "Vélo", "T2", "CAP"]


def test_col_indices():
    col = _col_indices(HEADERS)
    assert col["rank_overall"] == 0
    assert col["bib"] == 1
    assert col["name"] == 2
    assert col["club"] == 3
    assert col["total_time"] == 4
    assert col["swim_time"] == 5
    assert col["t1_time"] == 6
    assert col["bike_time"] == 7
    assert col["t2_time"] == 8
    assert col["run_time"] == 9


def test_col_indices_does_not_read_the_nationality_column_as_swim():
    # En-têtes réels de l'épreuve 7034 (aquathlon, Carnac 2025) : « Nat. » est la
    # nationalité (« FRA »), pas la natation (#971).
    headers = [
        "Place", "Dossard", "Nom", "Place Cat.", "Equipe / Club", "Temps Officiel (Réel)",
        "Écart", "TpsOff", "TpsReel", "Nat.", "",
    ]
    assert "swim_time" not in _col_indices(headers)


def test_col_indices_reads_tps_nat_as_swim():
    # En-têtes réels de l'épreuve 7031 (triathlon M, Carnac 2025).
    headers = [
        "Place", "Dossard", "Nom", "Place Cat.", "Equipe / Club", "Temps Officiel", "Écart",
        "Tps Off.", "Tps Nat", "Transition 1", "Tps Velo", "Transition 2", "Tps CAP", "",
    ]
    assert _col_indices(headers)["swim_time"] == 8


def test_parse_html_row():
    col = _col_indices(HEADERS)
    tds = [
        "1", "42", "DUPONT JeanH-S3H", "TCN",
        "01:59:00", "00:11:00", "00:01:00", "01:05:00", "00:00:50", "00:41:10",
    ]
    r = _parse_html_row(tds, col, "http://x", "Triathlon M")
    assert r.event_type == "triathlon-m"
    assert r.athlete_name == "DUPONT"
    assert r.athlete_firstname == "Jean"
    assert r.gender == "H"
    assert r.category == "S3H"
    assert r.bib_number == "42"
    assert r.club == "TCN"
    assert r.rank_overall == 1
    assert r.total_time == "01:59:00"
    assert r.swim_time == "00:11:00"
    assert r.t1_time == "00:01:00"
    assert r.bike_time == "01:05:00"
    assert r.t2_time == "00:00:50"
    assert r.run_time == "00:41:10"


# ── _parse_race_meta — nom d'événement + date, depuis la page de détail legacy
#
# La page liste `/Evenements/Resultats/{id}` n'expose ni le nom de l'événement
# ni sa date (le bandeau est rempli en JS). La page du modal de détail,
# `/Evenements/Resultats/Detail/{id}/1`, porte les deux : un <h6> « Course
# (jj/mm/aaaa) » et un lien de partage « Résultats - Course - Événement ».

def test_parse_race_meta_extrait_course_evenement_et_date():
    html = (FIXTURES / "sportinnovation_detail_7031.html").read_text(encoding="utf-8")
    race_name, event_name, event_date = _parse_race_meta(html)
    assert race_name == "Triathlon M"
    assert event_name == "Triathlon de Carnac 2025"
    assert event_date == date(2025, 10, 5)


def test_parse_race_meta_course_contenant_un_tiret():
    """Le nom de course peut contenir « - » : le découpage part du <h6>, pas du dernier tiret."""
    html = (
        '<h6 class="col-12">Bike &amp; Run - Kids (04/10/2025)</h6>'
        '<a href="https://www.facebook.com/sharer/sharer.php?u=https://x'
        '&t=Résultats - Bike &amp; Run - Kids - Triathlon de Carnac 2025"></a>'
    )
    race_name, event_name, event_date = _parse_race_meta(html)
    assert race_name == "Bike & Run - Kids"
    assert event_name == "Triathlon de Carnac 2025"
    assert event_date == date(2025, 10, 4)


def test_parse_race_meta_sans_lien_de_partage():
    """Sans lien de partage, on garde la course et la date ; l'événement reste vide."""
    race_name, event_name, event_date = _parse_race_meta("<h6>Aquathlon Pupilles (04/10/2025)</h6>")
    assert race_name == "Aquathlon Pupilles"
    assert event_name == ""
    assert event_date == date(2025, 10, 4)


def test_parse_race_meta_page_vide():
    assert _parse_race_meta("<div>rien</div>") == ("", "", None)


def test_parse_race_meta_date_invalide_ignoree():
    race_name, event_name, event_date = _parse_race_meta("<h6>Triathlon M (32/13/2025)</h6>")
    assert race_name == "Triathlon M"
    assert event_date is None


# ── _compose_course_name — « Événement - Course », clé d'unicité de la Course
#
# `uq_course_identity` = (name, event_date, event_type, is_relay). Les quatre
# aquathlons de Carnac partagent date + event_type : sans le nom de course dans
# le nom, ils fusionneraient en une seule Course.

def test_compose_course_name_concatene():
    assert _compose_course_name("Triathlon de Carnac 2025", "Triathlon M") == (
        "Triathlon de Carnac 2025 - Triathlon M"
    )


def test_compose_course_name_aquathlons_restent_distincts():
    noms = {
        _compose_course_name("Triathlon de Carnac 2025", r)
        for r in ("Aquathlon Pupilles", "Aquathlon Benjamins", "Aquathlon Minimes")
    }
    assert len(noms) == 3


def test_compose_course_name_evenement_manquant():
    assert _compose_course_name("", "Triathlon M") == "Triathlon M"


def test_compose_course_name_course_manquante():
    assert _compose_course_name("Triathlon de Carnac 2025", "") == "Triathlon de Carnac 2025"


def test_compose_course_name_identiques_pas_de_doublon():
    """Événement mono-course : « Swimrun Cote Beaute 2025 », pas « X - X »."""
    assert _compose_course_name("Swimrun Cote Beaute 2025", "Swimrun Cote Beaute 2025") == (
        "Swimrun Cote Beaute 2025"
    )


# ── _reconcile_race_dates : date de course contredite par l'année du titre (#1193)
#
# Mesure prod 06/10 : la course L de « Bayman - Triathlon du Mont Saint-Michel
# 2024 » publie « (10/10/2026) » sur sa page détail, sa sœur M « (06/10/2024) ».

BAYMAN = "Bayman - Triathlon du Mont Saint-Michel 2024"


def test_reconcile_race_dates_replaces_a_date_contradicting_the_title_year():
    dates = _si._reconcile_race_dates([
        (BAYMAN, date(2024, 10, 6)),
        (BAYMAN, date(2026, 10, 10)),
        (BAYMAN, date(2024, 10, 6)),
    ])
    assert dates == [date(2024, 10, 6), date(2024, 10, 6), date(2024, 10, 6)]


def test_reconcile_race_dates_takes_the_most_frequent_sibling_date():
    dates = _si._reconcile_race_dates([
        (BAYMAN, date(2024, 10, 5)),
        (BAYMAN, date(2024, 10, 6)),
        (BAYMAN, date(2024, 10, 6)),
        (BAYMAN, date(2026, 10, 10)),
    ])
    assert dates[3] == date(2024, 10, 6)


def test_reconcile_race_dates_breaks_a_frequency_tie_on_the_earliest_date():
    dates = _si._reconcile_race_dates([
        (BAYMAN, date(2024, 10, 6)),
        (BAYMAN, date(2024, 10, 5)),
        (BAYMAN, date(2026, 10, 10)),
    ])
    assert dates[2] == date(2024, 10, 5)


def test_reconcile_race_dates_drops_the_date_without_a_matching_sibling():
    assert _si._reconcile_race_dates([(BAYMAN, date(2026, 10, 10))]) == [None]


def test_reconcile_race_dates_keeps_dates_that_agree_with_the_title():
    """Carnac : les aquathlons courent la veille des triathlons, même année."""
    carnac = "Triathlon de Carnac 2025"
    metas = [(carnac, date(2025, 10, 4)), (carnac, date(2025, 10, 5))]
    assert _si._reconcile_race_dates(metas) == [date(2025, 10, 4), date(2025, 10, 5)]


def test_reconcile_race_dates_leaves_a_title_without_year_alone():
    metas = [("BayMan", date(2026, 6, 1)), ("BayMan", None)]
    assert _si._reconcile_race_dates(metas) == [date(2026, 6, 1), None]


def test_reconcile_race_dates_ignores_a_title_carrying_two_years():
    """« Saison 2024-2025 » ne désigne pas une année : rien n'est corrigé."""
    metas = [("Challenge 2024-2025", date(2025, 3, 1))]
    assert _si._reconcile_race_dates(metas) == [date(2025, 3, 1)]


# ── _parse_html_row — porte désormais le nom composé et la date ──────────────

def test_parse_html_row_porte_nom_composé_et_date():
    col = {"name": 0, "bib": 1, "total_time": 2}
    tds = ["DUPONT JeanH-S3H", "42", "01:23:45"]
    r = _parse_html_row(
        tds, col, "http://x", "Aquathlon Pupilles",
        course_name="Triathlon de Carnac 2025 - Aquathlon Pupilles",
        event_date=date(2025, 10, 4),
    )
    assert r.event_name == "Triathlon de Carnac 2025 - Aquathlon Pupilles"
    assert r.event_date == date(2025, 10, 4)
    # Le type reste classifié sur le titre de course, jamais sur le nom composé.
    assert r.event_type == "aquathlon"


# ── _classify_results_url — distingue la forme 2026 /race/{slug} de /{codeUrl}

def test_classify_results_url_race_form():
    kind, ident = _classify_results_url("https://results.sportinnovation.fr/race/zmhc-triathlon-m")
    assert (kind, ident) == ("race", "zmhc-triathlon-m")


def test_classify_results_url_detail_form():
    kind, ident = _classify_results_url("https://results.sportinnovation.fr/detail/51636b-18-c1066a43c01880e8")
    assert (kind, ident) == ("detail", "51636b-18-c1066a43c01880e8")


def test_classify_results_url_event_form():
    kind, ident = _classify_results_url("https://results.sportinnovation.fr/bayman_triathlon")
    assert (kind, ident) == ("event", "bayman_triathlon")


def test_classify_results_url_empty_raises():
    with pytest.raises(ValueError):
        _classify_results_url("https://results.sportinnovation.fr/")


# ── _parse_api_athlete — mapping d'un athlète JSON (API results.sportinnovation.fr)

def test_parse_api_athlete():
    a = {
        "lastName": "SAMSON", "firstName": "Fabian", "bib": "213",
        "clubName": None, "sex": "M", "category": "M SENIOR",
        "generalRanking": 1, "sexRanking": 1, "categoryRanking": 1,
        "officialTime": "01:53:37", "realTime": "01:53:37",
    }
    r = _parse_api_athlete(a, "http://x", "Bayman", "triathlon-m", None)
    assert r.event_name == "Bayman"
    assert r.event_type == "triathlon-m"
    assert r.athlete_name == "SAMSON"
    assert r.athlete_firstname == "Fabian"
    assert r.bib_number == "213"
    assert r.club == ""            # None → chaîne vide
    assert r.gender == "M"
    assert r.category == "M SENIOR"
    assert r.rank_overall == 1
    assert r.rank_gender == 1
    assert r.rank_category == 1
    assert r.total_time == "01:53:37"


def test_parse_api_athlete_falls_back_to_real_time():
    a = {"lastName": "X", "bib": "1", "officialTime": "", "realTime": "00:59:00"}
    r = _parse_api_athlete(a, "http://x", "E", "triathlon", None)
    assert r.total_time == "00:59:00"


# ── Statut non-finisher — HTML (colonne temps) + API (champ status/state) ────

def test_parse_html_row_explicit_status():
    """Colonne temps = 'Abandon' → status DNF + temps purgé."""
    col = {"name": 0, "bib": 1, "total_time": 2}
    tds = ["DUPONT JeanH-S3H", "42", "Abandon"]
    r = _parse_html_row(tds, col, "http://x", "Triathlon S")
    assert r.status == "DNF"
    assert r.total_time == ""


def test_parse_html_row_finisher_no_status():
    col = {"name": 0, "bib": 1, "total_time": 2}
    tds = ["DUPONT JeanH-S3H", "42", "01:23:45"]
    r = _parse_html_row(tds, col, "http://x", "Triathlon S")
    assert r.status == ""
    assert r.total_time == "01:23:45"


def test_parse_api_athlete_explicit_status():
    """Champ JSON status='DNS' → DNS + hygiène."""
    a = {
        "lastName": "Dupont", "firstName": "Jean", "bib": 42,
        "status": "DNS", "generalRanking": "5", "officialTime": "",
    }
    r = _parse_api_athlete(a, "http://x", "Triathlon", "triathlon-s", None)
    assert r.status == "DNS"
    assert r.total_time == ""
    assert r.rank_overall is None


# ── Second schéma de l'API results (≈11 % des courses : 17 sur 155 en 2026-07).
#
# Les rangs, temps et référence athlète y portent d'autres noms :
#   generalRank / sexRank / categoryRank   (au lieu de …Ranking)
#   officialTimeFfa / realTimeFfa          (au lieu de officialTime / realTime)
#   ni `id` ni `slug`                      → pas de splits récupérables
# Sans ces alias, l'athlète ressort sans temps ni rang, donc DNF à l'import.

def test_parse_api_athlete_schema_ffa():
    a = {
        "lastName": "BOURGUENOLLE", "firstName": "Pierre-arnaud", "bib": "3008",
        "clubName": "ENTENTE ATHLETIQUE DU LAC DAIGUEBELETTE", "sex": "H", "category": "M0H",
        "generalRank": 1, "sexRank": 1, "categoryRank": 1,
        "officialTimeFfa": "11:40:03", "realTimeFfa": "11:40:03", "status": None,
    }
    r = _parse_api_athlete(a, "http://x", "La Barjo 2026 - La mora", "trail", None)
    assert r.total_time == "11:40:03"
    assert r.rank_overall == 1
    assert r.rank_gender == 1
    assert r.rank_category == 1
    assert r.status == ""
    assert r.club == "ENTENTE ATHLETIQUE DU LAC DAIGUEBELETTE"


def test_parse_api_athlete_schema_ffa_temps_au_dela_de_24h():
    """Un ultra dépasse 24 h : le temps reste une chaîne, jamais tronquée."""
    a = {"lastName": "CASROUGE", "bib": "1", "generalRank": 1, "officialTimeFfa": "29:46:00"}
    r = _parse_api_athlete(a, "http://x", "Raid", "trail", None)
    assert r.total_time == "29:46:00"


def test_parse_api_athlete_schema_ffa_non_finisher():
    """En schéma FFA les non-partants n'ont pas de temps : DNS + rangs purgés."""
    a = {"lastName": "PATOUX", "bib": "", "status": "DNS",
         "generalRank": None, "officialTimeFfa": None, "realTimeFfa": None}
    r = _parse_api_athlete(a, "http://x", "La Barjo 2026 - La petite barjo", "trail", None)
    assert r.status == "DNS"
    assert r.total_time == ""
    assert r.rank_overall is None


def test_parse_api_athlete_schema_historique_prime():
    """Si les deux jeux de clés coexistent, le schéma historique fait foi."""
    a = {
        "lastName": "X", "bib": "1",
        "generalRanking": 3, "generalRank": 99,
        "officialTime": "01:00:00", "officialTimeFfa": "09:09:09",
    }
    r = _parse_api_athlete(a, "http://x", "E", "triathlon", None)
    assert r.rank_overall == 3
    assert r.total_time == "01:00:00"


def test_athlete_ref_par_athlete():
    """La référence pour les splits se lit par athlète : `id`, sinon `slug`, sinon rien."""
    from app.scrapers.sportinnovation import _athlete_ref

    assert _athlete_ref({"id": 42, "slug": "s"}) == 42
    assert _athlete_ref({"slug": "zmhc-1"}) == "zmhc-1"
    assert _athlete_ref({"bib": "3008"}) is None  # schéma FFA : aucune référence


def test_fetch_splits_parallel_schema_ffa_ne_fabrique_pas_de_reference():
    """Sans `id`/`slug`, aucun appel splits : sinon `/api/results/{bib}` renverrait
    l'athlète d'une autre course (l'id est global, pas relatif au dossard)."""
    from app.scrapers import sportinnovation as si

    appels = []
    si_orig = si._fetch_athlete_splits
    try:
        si._fetch_athlete_splits = lambda ref: appels.append(ref) or {}
        out = si._fetch_splits_parallel([{"bib": "3008", "generalRank": 1}])
    finally:
        si._fetch_athlete_splits = si_orig
    assert appels == []
    assert out == {}


# ── _scrape_results_race — chemin API : même convention de nommage que le legacy

class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeClient:
    """Client httpx minimal : sert des payloads indexés par suffixe d'URL."""

    def __init__(self, routes):
        self.routes = routes

    def get(self, url, **_kwargs):
        for suffix, payload in self.routes.items():
            if url.endswith(suffix):
                return _FakeResponse(payload)
        raise AssertionError(f"URL non routée : {url}")


def test_scrape_event_api_ignore_les_courses_sans_slug(monkeypatch):
    """3 courses réelles sur 155 n'ont pas de `slug` : elles sont injoignables,
    pas fatales. Un KeyError ferait échouer l'import de tout l'événement."""
    from app.scrapers import sportinnovation as si

    monkeypatch.setattr(si, "_fetch_splits_parallel", lambda athletes, **kw: {})
    client = _FakeClient({
        "/events": [{"slug": "ev-1", "customUrl": "mon_event", "title": "Mon Event"}],
        "/events/ev-1": {"title": "Mon Event", "eventDate": "2026-06-20"},
        "/events/ev-1/races": [
            {"title": "Joëlettes"},                       # sans slug → ignorée
            {"slug": "r-2", "title": "Marathon"},
        ],
        "/races/r-2/results": [{"lastName": "X", "bib": "1", "officialTime": "03:00:00"}],
    })

    # Le helper est testé directement : `scrape_event_all` ouvre son propre client.
    results = si._scrape_event_api("mon_event", "https://results.sportinnovation.fr/mon_event", client)
    assert len(results) == 1
    assert results[0].event_name == "Mon Event - Marathon"


def test_scrape_event_api_evenement_sans_slug_erreur_explicite():
    """Un événement de l'API peut n'avoir que `customUrl` et être injoignable
    (« Marathon de La Rochelle ») : message clair plutôt que KeyError."""
    from app.scrapers import sportinnovation as si

    client = _FakeClient({
        "/events": [{"customUrl": "marathon_de_la_rochelle", "title": "Marathon de La Rochelle"}],
    })
    with pytest.raises(ValueError, match="non adressable"):
        si._scrape_event_api("marathon_de_la_rochelle", "http://x", client)


def test_race_results_api_reponse_en_erreur_leve():
    """Import direct d'une course dont /results répond 500 : erreur explicite."""
    from app.scrapers import sportinnovation as si

    client = _FakeClient({"/races/r-1/results": {"error": "More than one result was found"}})
    with pytest.raises(ValueError, match="Résultats indisponibles"):
        si._race_results_api("r-1", "Joëlette", "Ev", None, "http://x", client)


def test_scrape_event_api_course_en_erreur_nempeche_pas_les_autres(monkeypatch):
    """Une course cassée côté fournisseur (500) ne doit pas faire échouer
    l'import de tout l'événement — cas réel des « 20Km de Paris »."""
    from app.scrapers import sportinnovation as si

    monkeypatch.setattr(si, "_fetch_splits_parallel", lambda athletes, **kw: {})
    client = _FakeClient({
        "/events": [{"slug": "ev-1", "customUrl": "paris", "title": "20Km de Paris"}],
        "/events/ev-1": {"title": "20Km de Paris", "eventDate": "2026-06-20"},
        "/events/ev-1/races": [
            {"slug": "r-ok", "title": "20 km"},
            {"slug": "r-ko", "title": "20 km Joëlette"},
        ],
        "/races/r-ok/results": [{"lastName": "X", "bib": "1", "officialTime": "01:20:00"}],
        "/races/r-ko/results": {"error": "More than one result was found"},
    })

    results = si._scrape_event_api("paris", "http://x", client)
    assert len(results) == 1
    assert results[0].event_name == "20Km de Paris - 20 km"


def test_scrape_event_api_reponse_races_en_erreur():
    """Deux événements partagent un slug → /races répond 500 avec un objet
    d'erreur. Itérer dessus donnerait des chaînes, pas des courses."""
    from app.scrapers import sportinnovation as si

    client = _FakeClient({
        "/events": [{"slug": "ev-1", "customUrl": "mon_event", "title": "Mon Event"}],
        "/events/ev-1": {"title": "Mon Event", "eventDate": "2026-06-20"},
        "/events/ev-1/races": {"error": "More than one result was found for query"},
    })
    with pytest.raises(ValueError, match="courses"):
        si._scrape_event_api("mon_event", "http://x", client)


def test_race_results_api_derives_the_overall_rank_when_none_is_published(monkeypatch):
    """#1210 : Défis de Saint-Nazaire 2026, schéma FFA sans aucun rang publié.
    Le rang se déduit de `rankingSeconds`, finishers seulement."""
    from app.scrapers import sportinnovation as si

    monkeypatch.setattr(si, "_fetch_splits_parallel", lambda athletes, **kw: {})
    client = _FakeClient({
        "/races/tri-s/results": [
            {"lastName": "LENT", "bib": "3", "rankingSeconds": 4000, "officialTimeFfa": "01:06:40"},
            {"lastName": "ABANDON", "bib": "4", "status": "DNF", "rankingSeconds": None},
            {"lastName": "RAPIDE", "bib": "1", "rankingSeconds": 3600, "officialTimeFfa": "01:00:00"},
            {"lastName": "MOYEN", "bib": "2", "officialTimeFfa": "01:03:00"},
        ],
    })

    results = si._race_results_api("tri-s", "Triathlon S", "Défis", None, "http://x", client)

    rangs = {r.athlete_name: r.rank_overall for r in results}
    assert rangs == {"RAPIDE": 1, "MOYEN": 2, "LENT": 3, "ABANDON": None}


def test_race_results_api_keeps_published_ranks(monkeypatch):
    """Un rang publié n'est jamais recalculé, même s'il manque sur une ligne."""
    from app.scrapers import sportinnovation as si

    monkeypatch.setattr(si, "_fetch_splits_parallel", lambda athletes, **kw: {})
    client = _FakeClient({
        "/races/tri-s/results": [
            {"lastName": "A", "bib": "1", "generalRank": 2, "rankingSeconds": 3600},
            {"lastName": "B", "bib": "2", "rankingSeconds": 3500, "officialTimeFfa": "00:58:20"},
        ],
    })

    results = si._race_results_api("tri-s", "Triathlon S", "Défis", None, "http://x", client)

    assert [r.rank_overall for r in results] == [2, None]


def test_scrape_results_race_compose_le_nom_et_porte_la_date(monkeypatch):
    from app.scrapers import sportinnovation as si

    monkeypatch.setattr(si, "_fetch_splits_parallel", lambda athletes, **kw: {})
    client = _FakeClient({
        "/races/zmhc-aquathlon-pupilles": {
            "slug": "zmhc-aquathlon-pupilles",
            "title": "Aquathlon Pupilles",
            "eventSlug": "gqjk02-triathlon-de-carnac-2025",
        },
        "/events/gqjk02-triathlon-de-carnac-2025": {
            "title": "Triathlon de Carnac 2025",
            "eventDate": "2025-10-04",
        },
        "/races/zmhc-aquathlon-pupilles/results": [
            {"lastName": "DUPONT", "firstName": "Jean", "bib": "7", "officialTime": "00:20:00"},
        ],
    })

    results = si._scrape_results_race("zmhc-aquathlon-pupilles", "http://x", client)

    assert len(results) == 1
    assert results[0].event_name == "Triathlon de Carnac 2025 - Aquathlon Pupilles"
    assert results[0].event_type == "aquathlon"
    assert results[0].event_date == date(2025, 10, 4)


# ── Couverture hors réseau des chemins sans test (#1067) ─────────────────────


@pytest.mark.parametrize(
    ("location", "slot"),
    [
        ("Temps Natation", "swim"),
        ("Transition 1", "t1"),
        ("Temps Vélo", "bike"),
        ("Transition 2", "t2"),
        ("Temps CaP", "run"),
        ("IN1", "swim"),
        ("OUT1", "t1"),
        ("VELO1", "bike"),
        ("OUT2", "t2"),
        ("IN2", "run"),
        ("CAP1", None),
        ("START", None),
        ("FINISH", None),
    ],
)
def test_location_to_slot_maps_triathlon_labels_and_duathlon_checkpoints(location, slot):
    assert _si._location_to_slot(location) == slot


def test_intermediates_to_splits_reads_the_observed_payload():
    """Forme réelle de `/api/results/3953335?intermediates=1` (2026-09-24)."""
    intermediates = [
        {"position": None, "location": "Temps Natation", "officialTime": "00:19:49"},
        {"position": None, "location": "Transition 1", "officialTime": "00:01:22"},
        {"position": None, "location": "Temps Vélo", "officialTime": "00:57:18"},
        {"position": None, "location": "Transition 2", "officialTime": "00:01:40"},
        {"position": None, "location": "Temps CaP", "officialTime": "00:33:30"},
    ]

    assert _si._intermediates_to_splits(intermediates) == {
        "swim": "00:19:49", "t1": "00:01:22", "bike": "00:57:18", "t2": "00:01:40", "run": "00:33:30",
    }


def test_intermediates_to_splits_keeps_the_first_time_of_a_slot():
    intermediates = [
        {"position": 1, "location": "Temps Natation", "officialTime": "00:19:49"},
        {"position": 2, "location": "IN1", "officialTime": "00:25:00"},
    ]

    assert _si._intermediates_to_splits(intermediates) == {"swim": "00:19:49"}


def _pages(monkeypatch, pages):
    appels = []

    def fake(event_id, client, search="", page=1):
        appels.append(page)
        return "Triathlon M", pages[page - 1] if page <= len(pages) else [], {"bib": 1}

    monkeypatch.setattr(_si, "_fetch_html_results", fake)
    return appels


def test_fetch_all_pages_concatenates_full_pages_until_a_short_one(monkeypatch):
    pleine = [["x", str(i)] for i in range(_si._PAGE_SIZE)]
    appels = _pages(monkeypatch, [pleine, pleine, [["x", "fin"]]])

    nom, lignes, col = _si._fetch_all_pages("42", client=None)

    assert (nom, col, appels) == ("Triathlon M", {"bib": 1}, [1, 2, 3])
    assert len(lignes) == 2 * _si._PAGE_SIZE + 1


def test_fetch_all_pages_stops_on_an_empty_page(monkeypatch):
    pleine = [["x", str(i)] for i in range(_si._PAGE_SIZE)]
    appels = _pages(monkeypatch, [pleine])

    _nom, lignes, _col = _si._fetch_all_pages("42", client=None)

    assert appels == [1, 2]
    assert len(lignes) == _si._PAGE_SIZE


class _Reponse:
    def __init__(self, text="", payload=None):
        self.text, self._payload, self.status_code = text, payload, 200

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _Client:
    def __init__(self, reponse):
        self.reponse, self.urls = reponse, []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, **kwargs):
        self.urls.append(url)
        return self.reponse


def _legacy(monkeypatch, html, lignes_par_course):
    client = _Client(_Reponse(text=html))
    monkeypatch.setattr(_si.http, "client", lambda *a, **k: client)
    monkeypatch.setattr(
        _si, "_fetch_all_pages", lambda rid, c: ("Triathlon M", lignes_par_course[rid], {"bib": 1})
    )
    monkeypatch.setattr(_si, "_fetch_race_meta", lambda rid, c: ("BayMan", date(2026, 6, 1)))
    monkeypatch.setattr(
        _si, "_parse_html_row",
        lambda tds, col, race_url, race_name, course_name, event_date: (race_url, tds[1]),
    )


def test_legacy_event_discovers_every_race_and_dedupes_bibs_per_race(monkeypatch):
    html = (
        '<select name="raceSearch"><option value="">--</option>'
        '<option value="11">S</option><option value="12">M</option></select>'
    )
    _legacy(monkeypatch, html, {"11": [["a", "1"], ["b", "1"], ["c", "2"]], "12": [["d", "1"]]})

    resultats = _si.scrape_event_all("https://sportinnovation.fr/Evenements/Resultats/10")

    base = "https://sportinnovation.fr/Evenements/Resultats"
    assert resultats == [(f"{base}/11", "1"), (f"{base}/11", "2"), (f"{base}/12", "1")]


def test_legacy_event_without_race_select_falls_back_on_the_event_id(monkeypatch):
    _legacy(monkeypatch, "<html></html>", {"10": [["a", "7"]]})

    resultats = _si.scrape_event_all("https://sportinnovation.fr/Evenements/Resultats/10")

    assert resultats == [("https://sportinnovation.fr/Evenements/Resultats/10", "7")]


def test_legacy_event_rewrites_a_race_date_contradicting_the_event_year(monkeypatch):
    html = (
        '<select name="raceSearch">'
        '<option value="6450">L</option><option value="6433">M</option></select>'
    )
    _legacy(monkeypatch, html, {"6450": [["a", "1"]], "6433": [["b", "2"]]})
    metas = {
        "6450": (BAYMAN, date(2026, 10, 10)),
        "6433": (BAYMAN, date(2024, 10, 6)),
    }
    monkeypatch.setattr(_si, "_fetch_race_meta", lambda rid, c: metas[rid])
    monkeypatch.setattr(
        _si, "_parse_html_row",
        lambda tds, col, race_url, race_name, course_name, event_date: (race_url, event_date),
    )

    resultats = _si.scrape_event_all("https://sportinnovation.fr/Evenements/Resultats/6450")

    base = "https://sportinnovation.fr/Evenements/Resultats"
    assert resultats == [
        (f"{base}/6450", date(2024, 10, 6)),
        (f"{base}/6433", date(2024, 10, 6)),
    ]


def test_detail_url_resolves_its_race_slug_then_imports_the_race(monkeypatch):
    client = _Client(_Reponse(payload={"raceSlug": "bayman-m"}))
    monkeypatch.setattr(_si.http, "client", lambda *a, **k: client)
    delegues = []
    monkeypatch.setattr(
        _si, "_scrape_results_race",
        lambda slug, url, c: delegues.append(slug) or ["ok"],
    )

    assert _si.scrape_event_all("https://results.sportinnovation.fr/detail/3953335") == ["ok"]
    assert delegues == ["bayman-m"]


def test_detail_url_without_race_slug_says_so(monkeypatch):
    client = _Client(_Reponse(payload={"error": "Not Found"}))
    monkeypatch.setattr(_si.http, "client", lambda *a, **k: client)

    with pytest.raises(ValueError, match="raceSlug"):
        _si.scrape_event_all("https://results.sportinnovation.fr/detail/3953335")


# ── Swimrun DUO : deux lignes par dossard (#1226) ────────────────────────────

def _duo_963_results(monkeypatch):
    import json

    data = json.loads((FIXTURES / "sportinnovation_duo_963.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(_si, "_fetch_splits_parallel", lambda athletes, **kw: {})
    client = _FakeClient({
        f"/races/{data['race']['slug']}": data["race"],
        f"/events/{data['race']['eventSlug']}": data["event"],
        f"/races/{data['race']['slug']}/results": data["results"],
    })
    return _si._scrape_results_race(data["race"]["slug"], "http://x", client)


def test_duo_race_yields_one_relay_row_per_team(monkeypatch):
    from app.scrapers.utils import split_relay_teammates

    results = _duo_963_results(monkeypatch)

    by_bib = {r.bib_number: r for r in results}
    assert sorted(by_bib) == ["12", "31", "45", "7"]
    assert all(r.is_relay for r in results)
    assert by_bib["12"].athlete_name == "MARTIN Paul / LE GALL Marie-Anne"
    assert by_bib["12"].athlete_firstname == ""
    assert split_relay_teammates(by_bib["12"].athlete_name) == [
        ("MARTIN", "Paul"), ("LE GALL", "Marie-Anne"),
    ]
    assert by_bib["12"].total_time == "01:30:10"


def test_duo_race_ranks_teams_not_teammates(monkeypatch):
    results = _duo_963_results(monkeypatch)

    assert {r.bib_number: r.rank_overall for r in results} == {
        "7": 1, "12": 2, "45": 3, "31": None,
    }
    assert {r.bib_number: r.status for r in results}["31"] == "DNF"


def test_duo_race_keeps_shared_team_attributes_only(monkeypatch):
    by_bib = {r.bib_number: r for r in _duo_963_results(monkeypatch)}

    assert (by_bib["45"].gender, by_bib["45"].category) == ("F", "M1F")
    assert by_bib["7"].club == "ST NAZAIRE TRI"
    # Équipe mixte : ni le genre ni la catégorie d'un seul équipier.
    assert (by_bib["12"].gender, by_bib["12"].category) == ("", "")
    assert by_bib["12"].club == "TRIATHLON CLUB NANTAIS"


def test_race_titled_duo_is_a_relay_even_with_one_row_per_bib(monkeypatch):
    monkeypatch.setattr(_si, "_fetch_splits_parallel", lambda athletes, **kw: {})
    client = _FakeClient({
        "/races/sr/results": [
            {"lastName": "DUPONT", "firstName": "Jean", "bib": "1", "officialTimeFfa": "01:00:00"},
        ],
    })

    (result,) = _si._race_results_api("sr", "Swimrun DUO", "Défis", None, "http://x", client)

    assert result.is_relay
    assert (result.athlete_name, result.athlete_firstname) == ("DUPONT", "Jean")


def test_solo_race_is_not_a_relay(monkeypatch):
    monkeypatch.setattr(_si, "_fetch_splits_parallel", lambda athletes, **kw: {})
    client = _FakeClient({
        "/races/sr/results": [
            {"lastName": "DUPONT", "firstName": "Jean", "bib": "1", "officialTimeFfa": "01:00:00"},
            {"lastName": "MARTIN", "firstName": "Paul", "bib": "2", "officialTimeFfa": "01:01:00"},
        ],
    })

    results = _si._race_results_api("sr", "Swimrun Solo", "Défis", None, "http://x", client)

    assert [(r.athlete_name, r.is_relay, r.rank_overall) for r in results] == [
        ("DUPONT", False, 1), ("MARTIN", False, 2),
    ]


def test_duo_race_imports_both_teammates_without_duplicate_bib(db_session, monkeypatch):
    from app.repositories import athlete_repository
    from app.services import import_persistence

    import_persistence.persist_results(db_session, "http://x", _duo_963_results(monkeypatch))

    martin = athlete_repository.get_by_identity_keys(db_session, "MARTIN", "Paul")
    le_gall = athlete_repository.get_by_identity_keys(db_session, "LE GALL", "Marie-Anne")
    (participation,) = martin.participations
    assert participation.teammates == [martin, le_gall]
    assert participation.course.is_relay
    assert "duplicate_bib" not in (participation.course.quality_issues or {})
