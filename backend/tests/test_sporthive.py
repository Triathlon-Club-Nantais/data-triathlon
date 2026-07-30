"""
Tests unitaires pour scrapers/sporthive.py (sans réseau).

Les fixtures sont des extraits **réels** de l'API MYLAPS Sporthive, réduits à
4 participants par page (cf. docs/superpowers/specs/2026-07-30-sporthive-api-sondage.md).
Le schéma réel est revérifié par le test `integration` sur Vertou 2024.
"""
import json
from datetime import date
from pathlib import Path

import pytest

from app.scrapers import sporthive
from app.scrapers.base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, STATUS_FINISHER

FIXTURES = Path(__file__).parent / "fixtures"

VERTOU = "7191895923677191680"
VERTOU_S = "7192778311832786688"
VERTOU_RELAIS = "7192778311832787200"


def _fixture(nom):
    return json.loads((FIXTURES / nom).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# _parse_url — les deux familles d'identifiants, les deux façades
# --------------------------------------------------------------------------

def test_parse_url_forme_canonique():
    assert sporthive._parse_url(f"https://sporthive.com/events/s/{VERTOU}") == VERTOU


def test_parse_url_accepte_un_identifiant_guid():
    """Les événements récents sont identifiés par GUID, pas par snowflake.

    Exiger `\\d+` refuserait tout le fonds récent (§Les URLs du sondage).
    """
    guid = "bdea2f10-1510-481c-b5ef-ef7f1926a06f"
    assert sporthive._parse_url(f"https://sporthive.com/events/s/{guid}") == guid


def test_parse_url_ignore_le_segment_race():
    """Une URL de course rapporte l'événement entier, comme chez ok-time."""
    assert sporthive._parse_url(
        f"https://sporthive.com/events/s/{VERTOU}/race/{VERTOU_S}"
    ) == VERTOU


@pytest.mark.parametrize("suffixe", ["/bib/42", "/team/7195685540963419392", "/"])
def test_parse_url_ignore_les_segments_profonds(suffixe):
    url = f"https://sporthive.com/events/s/{VERTOU}/race/{VERTOU_S}{suffixe}"
    assert sporthive._parse_url(url) == VERTOU


def test_parse_url_accepte_la_facade_results():
    """`results.sporthive.com/events/{id}` : l'ancienne façade, 307 vers la SPA."""
    assert sporthive._parse_url(
        f"https://results.sporthive.com/events/{VERTOU}"
    ) == VERTOU


def test_parse_url_ignore_lindex_de_course_de_la_facade_results():
    """`/races/3` porte un **index**, inexploitable par l'API : on l'ignore."""
    assert sporthive._parse_url(
        f"https://results.sporthive.com/events/{VERTOU}/races/3/team/6958824786005156352"
    ) == VERTOU


def test_parse_url_rejette_une_epreuve_motorisee():
    """`sporthive.com/events/{id}` sans `/s/` = Speedhive motorisé, autre API.

    Le `s` est la seule chose qui sépare l'endurance du motorisé : sans ce
    refus, on requêterait l'API endurance avec un id de course de moto.
    """
    with pytest.raises(ValueError, match="Speedhive"):
        sporthive._parse_url("https://sporthive.com/events/3632319")


def test_parse_url_rejette_une_page_hors_resultats():
    with pytest.raises(ValueError, match="non reconnue"):
        sporthive._parse_url("https://sporthive.com/practice")


# --------------------------------------------------------------------------
# Statuts — `validity`, jamais `dns`/`dsq`
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("validity", "attendu"),
    [(None, STATUS_FINISHER), ("DQ", STATUS_DSQ), ("DNF", STATUS_DNF), ("DNS", STATUS_DNS)],
)
def test_status_lit_validity(validity, attendu):
    """`DQ` (et non `DSQ`) est le libellé de la source."""
    assert sporthive._status({"validity": validity}) == attendu


def test_status_ignore_les_booleens_dns_dsq():
    """Ils sont à `false` sur les 1746 participants sondés, DQ compris.

    S'y fier classait finisher la totalité des non-finishers du panel.
    """
    assert sporthive._status({"validity": "DQ", "dns": False, "dsq": False}) == STATUS_DSQ


def test_status_dun_libelle_inconnu_reste_indetermine():
    """Un statut non mesuré ne doit pas être forcé à finisher : l'infra tranche."""
    assert sporthive._status({"validity": "XYZ"}) == ""


# --------------------------------------------------------------------------
# Temps — la fraction à 7 décimales
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("brut", "attendu"),
    [
        ("02:04:45", "02:04:45"),
        ("00:31:34.000", "00:31:34"),
        ("00:40:58.7230000", "00:40:58"),
        ("", ""),
        (None, ""),
    ],
)
def test_temps_tronque_la_fraction(brut, attendu):
    """`normalize_time` renvoie tel quel ce qu'il ne reconnaît pas : la fraction
    doit tomber **avant**, sinon `00:40:58.7230000` part en base."""
    assert sporthive._time(brut) == attendu


# --------------------------------------------------------------------------
# Splits — positionnels en multisport, `segments` en mono-sport
# --------------------------------------------------------------------------

def test_legs_multisport_alimentent_les_slots_positionnels():
    """Ordre constant natation/T1/vélo/T2/course, quels que soient les libellés."""
    participant = _fixture("sporthive_participants_vertou_s_p0.json")["content"][0]
    slots = sporthive._slots(participant)
    assert slots == {
        "swim_time": "00:10:47",
        "t1_time": "00:00:55",
        "bike_time": "00:29:44",
        "t2_time": "00:00:41",
        "run_time": "00:19:11",
    }


def test_legs_multisport_ne_produisent_pas_de_segments():
    """Deux legs nommés `TRANSITION` collisionneraient en `TRANSITION (2)`."""
    participant = _fixture("sporthive_participants_vertou_s_p0.json")["content"][0]
    assert sporthive._segments(participant) is None


def test_epreuve_tronquee_ne_remplit_que_les_slots_publies():
    """« Après Natation » n'a qu'un leg : les slots suivants restent vides."""
    participant = {"legs": [{"sportName": "SWIM", "legDuration": "00:22:22"}]}
    assert sporthive._slots(participant) == {"swim_time": "00:22:22"}


def test_monosport_utilise_les_points_de_passage_du_leg_unique():
    """Un seul leg : son `legDuration` est faux (00:06:33 pour un marathon).

    L'information est dans `participantSplits`, aux libellés signifiants.
    """
    participant = _fixture("sporthive_participants_marathon.json")["content"][0]
    assert sporthive._slots(participant) == {}
    segments = sporthive._segments(participant)
    assert segments[:3] == [("5k", "00:14:34"), ("10k", "00:14:33"), ("15k", "00:14:42")]
    assert len(segments) == 10


def test_monosport_sans_point_de_passage_ne_rend_aucun_segment():
    participant = {"legs": [{"type": "Running", "legDuration": "00:06:33"}]}
    assert sporthive._segments(participant) is None
    assert sporthive._slots(participant) == {}


# --------------------------------------------------------------------------
# Le scrape complet, sur client factice
# --------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeClient:
    """Client httpx factice : route les chemins de l'API sur les fixtures.

    Enregistre les URLs demandées — c'est ainsi que les tests de pagination
    vérifient le nombre d'appels réellement émis.
    """

    def __init__(self, routes):
        self.routes = routes
        self.appels = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, **kwargs):
        self.appels.append(url)
        for motif, payload in self.routes.items():
            if motif in url:
                if callable(payload):
                    return FakeResponse(payload(url))
                return FakeResponse(payload)
        raise AssertionError(f"URL non routée : {url}")


def _routes_vertou(**surcharges):
    """Vertou réduit à sa seule course « Triathlon S », 1 page de 4 lignes."""
    races = [r for r in _fixture("sporthive_races_vertou.json") if r["id"] == VERTOU_S]
    page = _fixture("sporthive_participants_vertou_s_p0.json")
    page["totalPages"] = 1
    page["totalElements"] = 4
    page["last"] = True
    routes = {
        f"/events/{VERTOU}/races": races,
        f"/events/{VERTOU}": _fixture("sporthive_event_vertou.json"),
        f"/races/{VERTOU_S}/participants": page,
    }
    routes.update(surcharges)
    return routes


def _fake(monkeypatch, routes):
    client = FakeClient(routes)
    monkeypatch.setattr(sporthive.httpx, "Client", lambda **kw: client)
    return client


def test_scrape_event_all_rend_les_participants(monkeypatch):
    _fake(monkeypatch, _routes_vertou())
    resultats = sporthive.scrape_event_all(f"https://sporthive.com/events/s/{VERTOU}")

    assert len(resultats) == 4
    premier = resultats[0]
    assert (premier.athlete_name, premier.athlete_firstname) == ("FRADIN", "Nathan")
    assert premier.club == "LES SABLES VENDEE TRI"
    assert premier.bib_number == "27"
    assert premier.gender == "M"
    assert premier.category == "CAM"
    assert premier.total_time == "01:01:15"
    assert premier.rank_overall == 1
    assert premier.rank_category == 1
    assert premier.rank_gender == 1
    assert premier.status == STATUS_FINISHER
    assert premier.provider == "sporthive"


def test_scrape_event_all_qualifie_le_nom_par_la_course(monkeypatch):
    """Sans qualification, les 5 courses de Vertou fusionnent et leurs dossards
    entrent en collision (issue #21)."""
    _fake(monkeypatch, _routes_vertou())
    resultats = sporthive.scrape_event_all(f"https://sporthive.com/events/s/{VERTOU}")
    assert resultats[0].event_name == "Triathlon de Vertou 2024 - Triathlon S"


def test_scrape_event_all_date_et_type(monkeypatch):
    _fake(monkeypatch, _routes_vertou())
    resultats = sporthive.scrape_event_all(f"https://sporthive.com/events/s/{VERTOU}")
    assert resultats[0].event_date == date(2024, 5, 5)
    assert resultats[0].event_type == "triathlon-s"


def test_scrape_event_all_classe_le_duathlon_sur_le_nom_de_course(monkeypatch):
    """Le `raceName` classe ; `eventName`/`eventType` ne sont qu'un appoint.

    Concaténer les deux ferait d'un duathlon un triathlon (piège ok-time).
    """
    races = [{
        "id": "7192821317418056192", "raceName": "Duathlon Jeunes 10-13 Ans",
        "date": "2024-05-05T00:00:00", "distanceInMeter": 4800,
        "classificationsCount": 4, "raceImportType": 1,
    }]
    page = _fixture("sporthive_participants_vertou_s_p0.json")
    page["totalPages"] = 1
    page["last"] = True
    _fake(monkeypatch, {
        f"/events/{VERTOU}/races": races,
        f"/events/{VERTOU}": _fixture("sporthive_event_vertou.json"),
        "/races/7192821317418056192/participants": page,
    })
    resultats = sporthive.scrape_event_all(f"https://sporthive.com/events/s/{VERTOU}")
    assert resultats[0].event_type.startswith("duathlon")


def test_scrape_event_all_pagine_jusqua_la_derniere_page(monkeypatch):
    """`size` est plafonné à 10 : une course de 25 lignes coûte 3 requêtes."""
    page = _fixture("sporthive_participants_vertou_s_p0.json")

    def page_n(url):
        numero = int(url.split("page=")[1].split("&")[0])
        return {**page, "totalPages": 3, "totalElements": 25,
                "number": numero, "last": numero == 2}

    client = _fake(monkeypatch, _routes_vertou(**{
        f"/races/{VERTOU_S}/participants": page_n,
    }))
    resultats = sporthive.scrape_event_all(f"https://sporthive.com/events/s/{VERTOU}")

    pages = [u for u in client.appels if "/participants" in u]
    assert len(pages) == 3
    assert "page=0" in pages[0] and "page=2" in pages[2]
    assert all("size=10" in u for u in pages)
    assert len(resultats) == 12


def test_scrape_event_all_ignore_une_course_sans_classement(monkeypatch):
    """`classificationsCount: 0` (course technique, épreuve à venir) : pas une
    anomalie, et surtout aucune requête à émettre pour elle."""
    races = _fixture("sporthive_races_vertou.json")
    vide = {**races[0], "id": "9999", "raceName": "Tussentijden",
            "classificationsCount": 0, "raceImportType": 3}
    client = _fake(monkeypatch, _routes_vertou(**{
        f"/events/{VERTOU}/races": [vide] + [r for r in races if r["id"] == VERTOU_S],
    }))
    resultats = sporthive.scrape_event_all(f"https://sporthive.com/events/s/{VERTOU}")

    assert len(resultats) == 4
    assert not any("/races/9999/" in u for u in client.appels)


def test_scrape_event_all_leve_si_aucune_course_na_de_classement(monkeypatch):
    """Un événement à venir doit se solder par une erreur parlante, pas par un
    import silencieux à 0 participant."""
    races = [{**_fixture("sporthive_races_vertou.json")[0], "classificationsCount": 0}]
    _fake(monkeypatch, _routes_vertou(**{f"/events/{VERTOU}/races": races}))
    with pytest.raises(ValueError, match="aucun classement"):
        sporthive.scrape_event_all(f"https://sporthive.com/events/s/{VERTOU}")


def test_scrape_event_all_marque_les_non_finishers(monkeypatch):
    """Les DQ n'ont ni temps ni rang : `overallPosition` vaut 0, pas None."""
    page = _fixture("sporthive_participants_vertou_s_dq.json")
    page["totalPages"] = 1
    page["last"] = True
    _fake(monkeypatch, _routes_vertou(**{f"/races/{VERTOU_S}/participants": page}))
    resultats = sporthive.scrape_event_all(f"https://sporthive.com/events/s/{VERTOU}")

    disqualifies = [r for r in resultats if r.status == STATUS_DSQ]
    assert len(disqualifies) == 2
    assert disqualifies[0].total_time == ""
    assert disqualifies[0].rank_overall is None


def test_scrape_event_all_relais_une_ligne_par_equipe(monkeypatch):
    """`name` porte le nom d'équipe, `teamName` est nul : pas de club à inventer."""
    page = _fixture("sporthive_participants_vertou_relais.json")
    page["totalPages"] = 1
    page["last"] = True
    races = [r for r in _fixture("sporthive_races_vertou.json") if r["id"] == VERTOU_RELAIS]
    _fake(monkeypatch, {
        f"/events/{VERTOU}/races": races,
        f"/events/{VERTOU}": _fixture("sporthive_event_vertou.json"),
        f"/races/{VERTOU_RELAIS}/participants": page,
    })
    resultats = sporthive.scrape_event_all(f"https://sporthive.com/events/s/{VERTOU}")

    assert resultats[0].is_relay is True
    assert resultats[0].club == ""
    assert resultats[0].athlete_name


def test_scrape_event_all_conserve_la_charge_source(monkeypatch):
    _fake(monkeypatch, _routes_vertou())
    resultats = sporthive.scrape_event_all(f"https://sporthive.com/events/s/{VERTOU}")
    assert resultats[0].raw_data["raceId"] == VERTOU_S
    assert resultats[0].raw_data["eventId"] == VERTOU


def test_scrape_event_all_source_url_est_lurl_demandee(monkeypatch):
    """Clé de cache TTL côté import_service : elle ne doit pas être réécrite."""
    url = f"https://sporthive.com/events/s/{VERTOU}/race/{VERTOU_S}"
    _fake(monkeypatch, _routes_vertou())
    resultats = sporthive.scrape_event_all(url)
    assert resultats[0].source_url == url
