"""
Tests unitaires pour scrapers/prolivesport.py (sans réseau).

Couvre les helpers purs : mapping des splits (champ→rôle), parsing d'un athlète
depuis le dict JSON de l'API, et détection du type d'épreuve. Puis le fan-out
par course (#269), dont le regroupement des lignes qui protège du défaut
central : l'API ignore le segment `race` d'une requête sur une partie des
événements et rend l'événement entier.
"""
import json

import httpx
import pytest

from app.scrapers import prolivesport
from app.scrapers.classify import classify_event_type
from app.scrapers.prolivesport import (
    _build_split_map,
    _derive_status,
    _is_relay,
    _parse_athlete,
    _parse_url,
    _resolve_race,
    _SplitPlan,
    _sub_source_url,
)

#: Plan de split vide (aucun rôle résolu, sans ambiguïté) — pour les tests qui
#: ne portent pas sur les splits eux-mêmes.
_PLAN_VIDE = _SplitPlan(resolved={}, ambigu=False, tous_les_champs=[])

# Liste de courses telle que renvoyée par result/raceList/{eventId}/
RACES = [
    {"race": "PO-PU"}, {"race": "BE-MI"}, {"race": "S_Light"}, {"race": "Challenge"},
    {"race": "TREP"}, {"race": "TRGP"}, {"race": "S"}, {"race": "M"},
]


def test_build_split_map_un_seul_candidat_par_role():
    splits = [
        {"race": "S", "field": "Nat", "label": "Natation"},
        {"race": "S", "field": "Tr1", "label": "T1"},
        {"race": "S", "field": "Velo", "label": "Vélo"},
        {"race": "S", "field": "Tr2", "label": "T2"},
        {"race": "S", "field": "Cap", "label": "Course à pied"},
        {"race": "M", "field": "AutreNat", "label": "Natation"},  # autre course → ignoré
    ]
    plan = _build_split_map(splits, race="S")
    assert plan.resolved == {
        "swim": "Nat", "t1": "Tr1", "bike": "Velo", "t2": "Tr2", "run": "Cap",
    }
    assert plan.ambigu is False


def test_build_split_map_ambiguite_carte_979():
    """Carte exacte citée par l'issue #280 : bike a 3 candidats (T3/T6/T7),
    run en a 2 (T5/T8)."""
    splits = [
        {"race": "M", "field": "T1", "label": "Swim"},
        {"race": "M", "field": "T2", "label": "#1"},
        {"race": "M", "field": "T3", "label": "Bike"},
        {"race": "M", "field": "T4", "label": "#2"},
        {"race": "M", "field": "T5", "label": "Run"},
        {"race": "M", "field": "T6", "label": "BikeStart"},
        {"race": "M", "field": "T7", "label": "BikeEnd"},
        {"race": "M", "field": "T8", "label": "RunStart"},
    ]
    plan = _build_split_map(splits, race="M")
    assert plan.resolved == {"swim": "T1", "t1": "T2", "t2": "T4"}  # bike/run absents : ambigus
    assert plan.ambigu is True
    assert plan.tous_les_champs == [
        ("T1", "Swim"), ("T2", "#1"), ("T3", "Bike"), ("T4", "#2"),
        ("T5", "Run"), ("T6", "BikeStart"), ("T7", "BikeEnd"), ("T8", "RunStart"),
    ]


def test_build_split_map_libelle_non_reconnu_reste_dans_tous_les_champs():
    """`Split1` (event 1082/1079) ne matche aucun rôle : absent de `resolved`,
    présent dans `tous_les_champs` — nécessaire pour ne rien perdre si la
    course bascule en `segments` pour une autre raison."""
    splits = [
        {"race": "M", "field": "T1", "label": "Bike"},
        {"race": "M", "field": "T9", "label": "Split1"},
    ]
    plan = _build_split_map(splits, race="M")
    assert plan.resolved == {"bike": "T1"}
    assert plan.ambigu is False
    assert plan.tous_les_champs == [("T1", "Bike"), ("T9", "Split1")]


def test_build_split_map_tri_par_suffixe_numerique_du_champ():
    """L'ordre de la réponse API est mélangé (mesuré) : `tous_les_champs` est
    trié sur le suffixe numérique, pas sur l'ordre d'arrivée."""
    splits = [
        {"race": "M", "field": "T9", "label": "Split1"},
        {"race": "M", "field": "T3", "label": "Bike"},
        {"race": "M", "field": "T1", "label": "Swim"},
    ]
    plan = _build_split_map(splits, race="M")
    assert [f for f, _ in plan.tous_les_champs] == ["T1", "T3", "T9"]


def test_parse_athlete_fields_and_splits():
    athlete = {
        "lastname": "Dupont",
        "firstname": "Jean",
        "number": "42",
        "club": "TCN",
        "categoryRef": "S3H",
        "sex": "H",
        "rank": "5",
        "rankSex": "4",
        "rankCat": "1",
        "time": "01:59:00",
        "timeNat": "00:11:00",
        "timeTr1": "00:01:00",
        "timeVelo": "01:05:00",
        "timeTr2": "00:00:50",
        "timeCap": "00:41:10",
    }
    plan = _SplitPlan(
        resolved={"swim": "Nat", "t1": "Tr1", "bike": "Velo", "t2": "Tr2", "run": "Cap"},
        ambigu=False,
        tous_les_champs=[],  # non utilisé hors ambiguïté
    )
    r = _parse_athlete(athlete, plan, "http://x", "Triathlon Test", "triathlon-s", None)

    assert r.athlete_name == "DUPONT"          # lastname en majuscules
    assert r.athlete_firstname == "Jean"
    assert r.bib_number == "42"
    assert r.club == "TCN"
    assert r.category == "S3H"
    assert r.gender == "H"
    assert r.rank_overall == 5
    assert r.rank_gender == 4
    assert r.rank_category == 1
    assert r.total_time == "01:59:00"
    assert r.swim_time == "00:11:00"
    assert r.t1_time == "00:01:00"
    assert r.bike_time == "01:05:00"
    assert r.t2_time == "00:00:50"
    assert r.run_time == "00:41:10"
    assert r.segments is None  # pas d'ambiguïté → pas de segments


def test_parse_athlete_ambiguite_route_tout_vers_segments():
    """Non-régression de l'issue #280, carte exacte de l'événement 979."""
    athlete = {
        "lastname": "Dupont", "number": "245", "time": "01:45:17",
        "timeT1": "00:20:42", "timeT2": "00:01:29", "timeT3": "00:51:31",
        "timeT4": "00:01:12", "timeT5": "00:30:25", "timeT6": "00:22:11",
        "timeT7": "01:13:41", "timeT8": "01:14:53",
    }
    plan = _SplitPlan(
        resolved={"swim": "T1", "t1": "T2", "t2": "T4"},  # bike/run ambigus → absents
        ambigu=True,
        tous_les_champs=[
            ("T1", "Swim"), ("T2", "#1"), ("T3", "Bike"), ("T4", "#2"),
            ("T5", "Run"), ("T6", "BikeStart"), ("T7", "BikeEnd"), ("T8", "RunStart"),
        ],
    )
    r = _parse_athlete(athlete, plan, "http://x", "E", "triathlon-m", None)

    assert r.bike_time == ""
    assert r.run_time == ""
    assert r.swim_time == ""  # tout ou rien : même un rôle non ambigu part en segments
    assert r.t1_time == ""
    assert r.t2_time == ""
    assert r.segments == [
        ("Swim", "00:20:42"), ("#1", "00:01:29"), ("Bike", "00:51:31"),
        ("#2", "00:01:12"), ("Run", "00:30:25"), ("BikeStart", "00:22:11"),
        ("BikeEnd", "01:13:41"), ("RunStart", "01:14:53"),
    ]


def test_parse_athlete_ambiguite_ignore_les_champs_vides_dans_segments():
    athlete = {
        "lastname": "Test", "number": "1", "time": "01:00:00",
        "timeT3": "00:30:00", "timeT6": "",
    }
    plan = _SplitPlan(resolved={}, ambigu=True, tous_les_champs=[("T3", "Bike"), ("T6", "BikeStart")])

    r = _parse_athlete(athlete, plan, "http://x", "E", "triathlon-m", None)

    assert r.segments == [("Bike", "00:30:00")]  # BikeStart vide → écarté, comme les slots aujourd'hui


def test_parse_athlete_skips_zero_splits():
    """Un split à 00:00:00 ne doit pas être enregistré."""
    athlete = {"lastname": "Test", "number": "1", "time": "01:00:00", "timeNat": "00:00:00"}
    plan = _SplitPlan(resolved={"swim": "Nat"}, ambigu=False, tous_les_champs=[])
    r = _parse_athlete(athlete, plan, "http://x", "E", "triathlon-s", None)
    assert r.swim_time == ""


def test_parse_athlete_finisher_keeps_time_and_ranks_and_status():
    athlete = {
        "lastname": "Dupont", "firstname": "Jean", "number": "42",
        "rank": "5", "rankSex": "4", "rankCat": "1", "time": "01:59:00",
    }
    r = _parse_athlete(athlete, _PLAN_VIDE, "http://x", "E", "triathlon-s", None)
    assert r.status == "finisher"
    assert r.total_time == "01:59:00"
    assert r.rank_overall == 5
    assert r.rank_gender == 4
    assert r.rank_category == 1


def test_parse_athlete_dns_clears_time_and_ranks():
    # Non-partant : pas de temps. L'API renvoie des rangs sentinelles (99991/99992).
    athlete = {
        "lastname": "Martin", "number": "7",
        "rank": "99991", "rankSex": "99992", "rankCat": "99991", "time": "",
    }
    r = _parse_athlete(athlete, _PLAN_VIDE, "http://x", "E", "triathlon-s", None)
    assert r.status == "DNS"
    assert r.total_time == ""
    assert r.rank_overall is None
    assert r.rank_gender is None
    assert r.rank_category is None


def test_parse_athlete_dnf_clears_time_and_ranks():
    athlete = {
        "lastname": "Durand", "number": "8",
        "dnf": "O", "rank": "99991", "time": "00:00:00",
    }
    r = _parse_athlete(athlete, _PLAN_VIDE, "http://x", "E", "triathlon-s", None)
    assert r.status == "DNF"
    assert r.total_time == ""
    assert r.rank_overall is None


# ---------------------------------------------------------------------------
# _is_relay — un relais ProliveSport a category="Relay" / categoryRef="R"
# (les courses solo portent des catégories d'âge : Senior/SE, Master/MA…)
# ---------------------------------------------------------------------------

def test_is_relay_from_category_ref():
    assert _is_relay({"category": "Relay", "categoryRef": "R"}) is True


def test_is_relay_from_category_label_only():
    assert _is_relay({"category": "relay", "categoryRef": ""}) is True


def test_is_relay_solo_age_category():
    assert _is_relay({"category": "Senior", "categoryRef": "SE"}) is False


def test_parse_athlete_detects_relay():
    athlete = {
        "lastname": "CEMONTRIATHLON", "firstname": ".", "number": "754",
        "category": "Relay", "categoryRef": "R", "sex": "X",
        "rank": "1", "time": "00:54:47",
    }
    r = _parse_athlete(athlete, _PLAN_VIDE, "http://x", "Triathlon Audencia", "triathlon", None)
    assert r.is_relay is True


def test_parse_athlete_solo_not_relay():
    athlete = {"lastname": "Dupont", "number": "1", "categoryRef": "SE", "time": "01:00:00"}
    r = _parse_athlete(athlete, _PLAN_VIDE, "http://x", "E", "triathlon-s", None)
    assert r.is_relay is False


def test_classify_event_type():
    assert classify_event_type("Triathlon M") == "triathlon-m"
    assert classify_event_type("Triathlon S") == "triathlon-s"
    assert classify_event_type("Duathlon Sprint") == "duathlon-s"
    assert classify_event_type("Aquathlon") == "aquathlon"
    assert classify_event_type("Triathlon") == "triathlon"


# ---------------------------------------------------------------------------
# _parse_url — supporte la forme query ET la forme front /result/{id}/{index}
# ---------------------------------------------------------------------------

def test_parse_url_query_form():
    assert _parse_url("https://www.prolivesport.fr/index.php?eventId=1082&race=S") == ("1082", "S")


def test_parse_url_query_form_no_race():
    assert _parse_url("https://www.prolivesport.fr/index.php?eventId=1082") == ("1082", "")


def test_parse_url_path_form():
    """Forme front : /result/{eventId}/{raceIndex}."""
    assert _parse_url("https://www.prolivesport.fr/result/1082/6") == ("1082", "6")


def test_parse_url_path_form_no_race():
    assert _parse_url("https://www.prolivesport.fr/result/1082") == ("1082", "")


def test_parse_url_missing_event_id_raises():
    with pytest.raises(ValueError):
        _parse_url("https://www.prolivesport.fr/")


# ---------------------------------------------------------------------------
# _resolve_race — un token numérique est un index positionnel dans raceList
# ---------------------------------------------------------------------------

def test_resolve_race_by_positional_index():
    assert _resolve_race("6", RACES) == "S"   # index 6 (0-based) = "S"


def test_resolve_race_by_code():
    assert _resolve_race("S", RACES) == "S"


def test_resolve_race_empty_uses_first():
    assert _resolve_race("", RACES) == "PO-PU"


def test_resolve_race_index_out_of_range_raises():
    with pytest.raises(ValueError):
        _resolve_race("99", RACES)


# ---------------------------------------------------------------------------
# _derive_status — lit dsq / dnf / time (le champ dns de l'API n'est pas fiable)
# ---------------------------------------------------------------------------

def test_derive_status_dsq():
    assert _derive_status({"dsq": "O", "time": "01:59:00"}) == "DSQ"


def test_derive_status_dnf():
    assert _derive_status({"dnf": "O", "time": ""}) == "DNF"


def test_derive_status_finisher_with_time():
    # Cas réel : dns="O" alors que l'athlète a fini → finisher (pas DNS).
    assert _derive_status({"time": "01:59:00", "dns": "O"}) == "finisher"


def test_derive_status_dns_no_time():
    assert _derive_status({"time": "", "dns": "O"}) == "DNS"


def test_derive_status_dns_zero_time():
    assert _derive_status({"time": "00:00:00"}) == "DNS"


def test_derive_status_dsq_takes_precedence_over_dnf():
    assert _derive_status({"dsq": "O", "dnf": "O", "time": ""}) == "DSQ"


# ---------------------------------------------------------------------------
# Constantes de statut + champ ScrapedResult.status
# ---------------------------------------------------------------------------

def test_status_constants_values():
    from app.scrapers.base import (
        STATUS_DNF,
        STATUS_DNS,
        STATUS_DSQ,
        STATUS_FINISHER,
    )
    assert STATUS_FINISHER == "finisher"
    assert STATUS_DNF == "DNF"
    assert STATUS_DNS == "DNS"
    assert STATUS_DSQ == "DSQ"


def test_scraped_result_status_defaults_empty():
    from app.scrapers.base import ScrapedResult
    r = ScrapedResult(source_url="http://x", provider="prolivesport")
    assert r.status == ""


# ---------------------------------------------------------------------------
# Fan-out par course (#269)
#
# Sondage : docs/superpowers/specs/2026-08-11-prolivesport-fanout-sondage.md.
# Les charges factices reproduisent le défaut mesuré : `indiv/{event}/{race}/`
# rend l'événement **entier** dès que le code de course porte un espace ou un
# tiret bas. Seul le champ `race` de chaque ligne dit la vérité.
# ---------------------------------------------------------------------------

URL_979 = (
    "https://www.prolivesport.fr/index.php?chap=event&sub=liveV3"
    "&eventId=979&race=Triathlon%20M"
)
NOM_979 = "Les triathlons Open de la presqu'ile de Quiberon 2024"

RACES_979 = [
    {"race": "Triathlon XS", "distance": "12.5"},
    {"race": "Triathlon S", "distance": "25.75"},
    {"race": "Triathlon M", "distance": "51.5"},
]

SPLITS_979 = [
    {"race": "Triathlon M", "field": "Nat", "label": "Natation"},
    {"race": "Triathlon M", "field": "Velo", "label": "Vélo"},
    {"race": "Triathlon S", "field": "Nat", "label": "Natation"},
]


def _ligne(race: str, number: str, lastname: str, **extra) -> dict:
    return {
        "race": race, "number": number, "lastname": lastname, "firstname": "Jean",
        "club": "TRIATHLON CLUB NANTAIS", "categoryRef": "SE", "sex": "M",
        "time": "01:00:00", "rank": "1", "timeNat": "00:11:00",
        **extra,
    }


#: L'événement 979 entier : ce que l'API rend pour **n'importe laquelle** de ses
#: trois courses (mesuré : 815 lignes pour `race=Triathlon M`, dont 479 d'autres
#: courses).
EVENEMENT_979 = [
    _ligne("Triathlon XS", "1", "AAA"),
    _ligne("Triathlon S", "2", "BBB"),
    _ligne("Triathlon S", "3", "CCC"),
    _ligne("Triathlon M", "4", "DDD"),
    _ligne("Triathlon M", "5", "EEE"),
]


class _Reponse:
    def __init__(self, charge, status_code: int = 200):
        self.status_code = status_code
        self._charge = charge

    @property
    def text(self) -> str:
        return "" if self._charge is None else json.dumps(self._charge)

    def json(self):
        if self._charge is None:
            raise json.JSONDecodeError("Expecting value", "", 0)
        return self._charge

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPError(f"HTTP {self.status_code}")


class _ApiFactice:
    """L'API ProLiveSport en factice : `event/detail`, `raceList`, `splitDetail`,
    `indiv`.

    `indiv` est une fonction `(race) -> list[dict] | _Reponse`, ce qui permet de
    jouer les trois comportements mesurés : filtre honoré, filtre ignoré
    (événement entier), et HTTP 500 à corps vide.
    """

    def __init__(self, *, races=RACES_979, splits=SPLITS_979, indiv=None, nom=NOM_979):
        self.races = races
        self.splits = splits
        self.indiv = indiv or (lambda race: EVENEMENT_979)
        self.nom = nom
        self.calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    @property
    def appels_indiv(self) -> list[str]:
        return [u for u in self.calls if "/result/indiv/" in u]

    def get(self, url: str, **kwargs):
        self.calls.append(url)
        if "/event/detail/" in url:
            return _Reponse({"result": [
                {"eventName": self.nom, "eventDateStart": "2024-06-15"},
            ]})
        if "/result/raceList/" in url:
            return _Reponse({"success": True, "result": self.races})
        if "/result/splitDetail/" in url:
            return _Reponse({"success": True, "result": self.splits})
        if "/result/indiv/" in url:
            race = url.split("/result/indiv/")[1].split("/", 1)[1].rstrip("/")
            charge = self.indiv(race)
            if isinstance(charge, _Reponse):
                return charge
            return _Reponse({"success": True, "result": charge})
        raise AssertionError(f"URL non prévue par le factice : {url}")


def _api(monkeypatch, **kwargs) -> _ApiFactice:
    api = _ApiFactice(**kwargs)
    monkeypatch.setattr(prolivesport.httpx, "Client", lambda *a, **k: api)
    return api


def _par_course(resultats) -> dict[str, list]:
    groupes: dict[str, list] = {}
    for r in resultats:
        groupes.setdefault(r.source_url, []).append(r)
    return groupes


# --- le défaut central : regrouper par le champ `race` de chaque ligne ------

def test_fanout_regroupe_les_lignes_par_course_quand_lapi_ignore_le_filtre(monkeypatch):
    """Non-régression du défaut n° 1 du sondage.

    L'API rend les 5 lignes de l'événement pour chacune des 3 courses. Sans
    regroupement, chaque `Course` recevrait les 5 — 815 participations dans un
    « Triathlon M » qui n'en compte que 336, et l'événement stocké 3 fois.
    """
    _api(monkeypatch)

    resultats, _trace = prolivesport.scrape_event_fanout(URL_979)

    assert len(resultats) == 5  # et non 15
    tailles = {url: len(rs) for url, rs in _par_course(resultats).items()}
    assert tailles == {
        _sub_source_url("979", "Triathlon XS"): 1,
        _sub_source_url("979", "Triathlon S"): 2,
        _sub_source_url("979", "Triathlon M"): 2,
    }
    for url, rs in _par_course(resultats).items():
        course = url.rsplit("race=", 1)[1].replace("%20", " ")
        assert {r.raw_data["race"] for r in rs} == {course}


def test_fanout_reutilise_une_reponse_qui_couvre_plusieurs_courses(monkeypatch):
    """Un seul GET pour les 3 courses : les réponses pèsent jusqu'à 14,7 Mo,
    en refaire une par course serait absurde (constat n° 4 du sondage)."""
    api = _api(monkeypatch)

    prolivesport.scrape_event_fanout(URL_979)

    assert len(api.appels_indiv) == 1


def test_fanout_appelle_chaque_course_quand_le_filtre_est_honore(monkeypatch):
    """Filtre honoré (codes sans espace ni tiret bas) : une requête par course."""
    api = _api(monkeypatch, indiv=lambda race: [
        ligne for ligne in EVENEMENT_979 if ligne["race"] == race
    ])

    resultats, trace = prolivesport.scrape_event_fanout(URL_979)

    assert len(api.appels_indiv) == 3
    assert trace.heats_enumerated == 3
    assert len(resultats) == 5


def test_fanout_nominal_rend_une_trace_complete(monkeypatch):
    _api(monkeypatch)

    _resultats, trace = prolivesport.scrape_event_fanout(URL_979)

    assert trace.heats_enumerated == 3
    assert trace.heats_cached == 0
    assert trace.heats_imported == 0  # dérivé côté import_service
    assert trace.failures == []
    assert trace.cached_urls == []


def test_fanout_source_url_par_course_reprend_la_forme_du_sheet(monkeypatch):
    """`source_url` = clé de cache TTL = forme du Sheet, au caractère près.

    `Course` est retrouvée par égalité exacte de `source_url`
    (`course_repository.get_latest_by_source_url`) : un `+` au lieu de `%20`
    créerait un doublon au lieu de réécrire la Course existante.
    """
    _api(monkeypatch)

    resultats, _trace = prolivesport.scrape_event_fanout(URL_979)

    assert URL_979 in {r.source_url for r in resultats}


def test_sub_source_url_encode_lespace_en_pourcent_vingt():
    assert _sub_source_url("979", "Triathlon M") == URL_979
    assert _sub_source_url("1082", "M_relay") == (
        "https://www.prolivesport.fr/index.php?chap=event&sub=liveV3"
        "&eventId=1082&race=M_relay"
    )


# --- contrat du patron #195 : cache, progression, isolation d'échec ---------

def test_fanout_cache_probe_saute_une_course_fraiche(monkeypatch):
    _api(monkeypatch)
    fraiche = _sub_source_url("979", "Triathlon M")

    resultats, trace = prolivesport.scrape_event_fanout(
        URL_979, cache_probe=lambda sub_url: sub_url == fraiche,
    )

    assert trace.heats_enumerated == 3
    assert trace.heats_cached == 1
    assert trace.cached_urls == [fraiche]
    assert fraiche not in {r.source_url for r in resultats}
    assert len(resultats) == 3  # 1 XS + 2 S


def test_fanout_on_heat_start_non_notifie_pour_une_course_cachee(monkeypatch):
    """`total` = nombre de courses **à scraper**, pas le nombre énuméré — sinon
    la progression sauterait des indices sur un ré-import majoritairement caché.
    """
    _api(monkeypatch)
    fraiche = _sub_source_url("979", "Triathlon M")
    vus: list[tuple] = []

    prolivesport.scrape_event_fanout(
        URL_979,
        cache_probe=lambda sub_url: sub_url == fraiche,
        on_heat_start=lambda slug, label, index, total: vus.append(
            (slug, label, index, total)
        ),
    )

    assert vus == [
        ("Triathlon XS", "Triathlon XS", 1, 2),
        ("Triathlon S", "Triathlon S", 2, 2),
    ]


def test_fanout_echec_dune_course_isole_les_autres(monkeypatch):
    """Un 500 persistant sur une course n'emporte pas l'événement."""
    def indiv(race):
        if race == "Triathlon S":
            return _Reponse(None, status_code=500)
        return [ligne for ligne in EVENEMENT_979 if ligne["race"] == race]

    _api(monkeypatch, indiv=indiv)

    resultats, trace = prolivesport.scrape_event_fanout(URL_979)

    assert trace.heats_enumerated == 3
    assert [echec["heat_slug"] for echec in trace.failures] == ["Triathlon S"]
    assert len(resultats) == 3  # 1 XS + 2 M, le S manque
    assert "Triathlon S" not in {r.raw_data["race"] for r in resultats}


def test_fanout_sans_course_rend_une_trace_vide(monkeypatch):
    api = _api(monkeypatch, races=[])

    resultats, trace = prolivesport.scrape_event_fanout(URL_979)

    assert resultats == []
    assert trace.heats_enumerated == 0
    assert trace.failures == []
    assert api.appels_indiv == []


# --- ce que chaque course porte : type, nom qualifié, splits ----------------

def test_fanout_event_type_deduit_du_code_de_chaque_course(monkeypatch):
    """Le type venait du jeton de l'URL : les 815 lignes de l'événement 979
    étaient toutes typées `triathlon-m`, XS et S compris."""
    _api(monkeypatch)

    resultats, _trace = prolivesport.scrape_event_fanout(URL_979)

    types = {r.raw_data["race"]: r.event_type for r in resultats}
    assert types == {
        "Triathlon XS": "triathlon-xs",
        "Triathlon S": "triathlon-s",
        "Triathlon M": "triathlon-m",
    }


def test_fanout_nom_devenement_qualifie_par_la_course(monkeypatch):
    """Sans qualification, les 3 courses fusionnent en une seule `Course` et
    leurs dossards entrent en collision (issue #21)."""
    _api(monkeypatch)

    resultats, _trace = prolivesport.scrape_event_fanout(URL_979)

    assert {r.event_name for r in resultats} == {
        f"{NOM_979} - Triathlon XS",
        f"{NOM_979} - Triathlon S",
        f"{NOM_979} - Triathlon M",
    }


def test_fanout_split_map_par_course_en_un_seul_appel(monkeypatch):
    """`splitDetail` rend l'événement entier : un GET, filtré par course.

    L'événement 1060 exposait le défaut : la carte était construite pour
    « CHTRI 6-7 ans » (aucun split publié) puis appliquée aux 11 courses.
    """
    api = _api(monkeypatch)

    resultats, _trace = prolivesport.scrape_event_fanout(URL_979)

    assert len([u for u in api.calls if "/result/splitDetail/" in u]) == 1
    par_course = {r.raw_data["race"]: r for r in resultats}
    assert par_course["Triathlon M"].swim_time == "00:11:00"
    assert par_course["Triathlon M"].bike_time == ""      # timeVelo absent
    assert par_course["Triathlon S"].swim_time == "00:11:00"
    assert par_course["Triathlon XS"].swim_time == ""     # aucun split publié


def test_fanout_ambiguite_de_role_route_vers_segments(monkeypatch):
    """Non-régression #280 en conditions de fan-out : la course Triathlon M a
    ses rôles bike/run ambigus (Bike/BikeStart/BikeEnd, Run/RunStart) → aucun
    des deux slots n'est renseigné, tout part dans `segments`."""
    splits_avec_ambiguite = SPLITS_979 + [
        {"race": "Triathlon M", "field": "T6", "label": "BikeStart"},
        {"race": "Triathlon M", "field": "T7", "label": "BikeEnd"},
        {"race": "Triathlon M", "field": "T5", "label": "Run"},
        {"race": "Triathlon M", "field": "T8", "label": "RunStart"},
    ]
    _api(monkeypatch, splits=splits_avec_ambiguite)

    resultats, _trace = prolivesport.scrape_event_fanout(URL_979)

    m = [r for r in resultats if r.raw_data["race"] == "Triathlon M"]
    assert all(r.bike_time == "" and r.run_time == "" for r in m)
    assert all(r.segments for r in m)


def test_fanout_event_date_partagee_par_les_courses(monkeypatch):
    from datetime import date

    _api(monkeypatch)

    resultats, _trace = prolivesport.scrape_event_fanout(URL_979)

    assert {r.event_date for r in resultats} == {date(2024, 6, 15)}


# --- reprise sur les 500 intermittents (constat n° 4 du sondage) ------------

def test_fetch_indiv_reprend_apres_des_500_a_corps_vide(monkeypatch):
    """Mesuré : 3 × HTTP 500 puis succès au 4ᵉ essai sur une réponse de 14,7 Mo."""
    essais = {"n": 0}

    def indiv(race):
        essais["n"] += 1
        if essais["n"] < 3:
            return _Reponse(None, status_code=500)
        return EVENEMENT_979

    api = _api(monkeypatch, indiv=indiv)

    lignes = prolivesport._fetch_indiv("979", "Triathlon M", api)

    assert len(lignes) == 5
    assert essais["n"] == 3


def test_fetch_indiv_abandonne_apres_les_essais(monkeypatch):
    api = _api(monkeypatch, indiv=lambda race: _Reponse(None, status_code=500))

    with pytest.raises(httpx.HTTPError):
        prolivesport._fetch_indiv("979", "Triathlon M", api)

    assert len(api.appels_indiv) == prolivesport._ESSAIS_INDIV


# --- le chemin mono-course (échappatoire `--single-heat`) -------------------

def test_scrape_event_all_ne_garde_que_les_lignes_de_la_course(monkeypatch):
    """L'échappatoire filtre aussi : sinon `--single-heat` reconstruirait le
    fourre-tout de 815 lignes."""
    _api(monkeypatch)

    resultats = prolivesport.scrape_event_all(URL_979)

    assert len(resultats) == 2
    assert {r.raw_data["race"] for r in resultats} == {"Triathlon M"}
    assert {r.source_url for r in resultats} == {URL_979}


def test_scrape_event_all_qualifie_le_nom_comme_le_fanout(monkeypatch):
    _api(monkeypatch)

    resultats = prolivesport.scrape_event_all(URL_979)

    assert {r.event_name for r in resultats} == {f"{NOM_979} - Triathlon M"}


# --- forme slug : page de série, non résoluble (constat n° 5 du sondage) ----

def test_parse_url_page_de_serie_dit_ce_quelle_est():
    """`/fftri/grand-prix-duathlon` est une page de série rendue côté navigateur :
    aucun `eventId` à en tirer. Le message doit le dire, pas laisser croire que
    le fournisseur n'est pas supporté."""
    with pytest.raises(ValueError, match="série"):
        _parse_url("https://www.prolivesport.fr/fftri/grand-prix-duathlon")


def test_parse_url_racine_reste_une_url_sans_identifiant():
    with pytest.raises(ValueError, match="identifiant d'événement"):
        _parse_url("https://www.prolivesport.fr/")


# --- le provider du registre -------------------------------------------------

def test_provider_delegue_au_fanout_et_expose_last_trace(monkeypatch):
    """`import_service._scrape_all` lit `last_trace` pour peupler les 5 compteurs."""
    from app.scrapers import registry

    _api(monkeypatch)
    provider = registry.ProLiveSportProvider()

    resultats = provider.scrape_event_all(URL_979)

    assert len(resultats) == 5
    assert provider.last_trace is not None
    assert provider.last_trace.heats_enumerated == 3


def test_provider_transmet_le_cache_probe(monkeypatch):
    from app.scrapers import registry

    _api(monkeypatch)
    fraiche = _sub_source_url("979", "Triathlon M")
    provider = registry.ProLiveSportProvider()

    provider.scrape_event_all(URL_979, cache_probe=lambda u: u == fraiche)

    assert provider.last_trace.heats_cached == 1


def test_provider_single_heat_cible_la_course_de_lurl(monkeypatch):
    from app.scrapers import registry

    _api(monkeypatch)
    provider = registry.ProLiveSportProvider()

    resultats = provider.scrape_event_all(URL_979, single_heat=True)

    assert {r.raw_data["race"] for r in resultats} == {"Triathlon M"}
    assert provider.last_trace.heats_enumerated == 1


def test_provider_est_un_fanout_provider_donc_recoit_les_kwargs():
    """Le dispatcher route sur `isinstance(provider, FanoutProvider)` : hors de
    cette classe, `cache_probe` ne serait jamais transmis."""
    from app.scrapers import registry

    provider = registry.get_provider(URL_979)
    assert isinstance(provider, registry.FanoutProvider)
    assert provider.name == "prolivesport"
