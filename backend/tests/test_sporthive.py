"""
Tests for scrapers/sporthive.py — **network-free** (constitution, principle III).

`httpx.Client` is monkeypatched by `FakeClient`, and every payload comes from a
JSON fixture under `fixtures/sporthive_*.json`, captured from the panel of the
sondage (`docs/superpowers/specs/2026-07-29-sporthive-sondage.md`, ground truth:
it outranks the design and the plan on any factual disagreement). Fixtures are
loaded via `_fixture`, never read by hand.

`FakeClient.calls` is not merely a counter: several tests here assert the
**absence** of a request — none to a race announcing zero entrants, none to the
`/races/1` ordinal — and an absence cannot be shown with a payload.
"""
import ast
import copy
import inspect
import json
import logging
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.core.club import is_tcn
from app.core.counter_scope import DEFAULT_TCN_CLUB_LABELS
from app.scrapers import sporthive
from app.scrapers.base import (
    STATUS_DNF,
    STATUS_DNS,
    STATUS_DSQ,
    STATUS_FINISHER,
)
from app.scrapers.classify import classify_event_type
from app.services.mapping import build_splits

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(nom: str) -> dict | list:
    """`dict | list` : `/events/{id}/races` rend un **tableau nu**, non paginé.

    Les autres routes rendent un objet (métadonnées, ou page Spring).
    """
    return json.loads((FIXTURES / nom).read_text(encoding="utf-8"))


class FakeResponse:
    """Fake HTTP response: `.status_code`, `.json()`, `.raise_for_status()`.

    Modeled on `test_oktime.py::FakeResponse` — this is all the real code will
    ever expect from an `httpx` response, nothing more.
    """

    def __init__(self, payload=None, status_code: int = 200):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPError(f"HTTP {self.status_code}")


class FakeClient:
    """Fake HTTP client: context manager, `.get(url, params=...)`.

    `routes` maps a **URL fragment** to the response to return. Matching
    happens on the **effective** URL, `params` merged into the query by
    `httpx.URL` — so two calls to the same route with `page=0` then `page=1`
    can carry distinct fragments and get distinct responses (pagination,
    batch 5). No route matches → `defaut` (404 by default, not a silent
    success: an unplanned call must show up).

    `self.calls` keeps the effective URL of **every** call, in order. It is
    not just a total: `calls_containing(fragment)` lets a test assert an
    **absence** of a request ("zero calls to /races/1/...") — that assertion
    shape, not a raw count, is what T013 and T027 will rely on.
    """

    def __init__(self, routes: dict[str, FakeResponse] | None = None, defaut: FakeResponse | None = None):
        self.routes = routes or {}
        self.defaut = defaut or FakeResponse({"message": "route non prevue"}, 404)
        self.calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url: str, params: dict | None = None) -> FakeResponse:
        effective = str(httpx.URL(url, params=params)) if params else url
        self.calls.append(effective)
        for fragment, reponse in self.routes.items():
            if fragment in effective:
                return reponse
        return self.defaut

    def calls_containing(self, fragment: str) -> list[str]:
        return [appel for appel in self.calls if fragment in appel]


def test_fake_client_routes_by_url_paginates_and_proves_a_call_absence():
    """The fake client returns the right payload per route, tells two pages of
    the same route apart via `params`, simulates an HTTP status, and the call
    counter lets a test assert no request went out to a given route — exactly
    what batch 6 (a race with `classificationsCount: 0`) and batch 10 (the
    anti-ordinal `/races/1` guard) will rely on.
    """
    event = {"eventName": "Triathlon de Test"}
    page0 = {"content": [{"bib": "1"}], "last": False}
    page1 = {"content": [{"bib": "2"}], "last": True}

    client = FakeClient(
        {
            "/events/42": FakeResponse(event),
            "/races/111/participants?page=0": FakeResponse(page0),
            "/races/111/participants?page=1": FakeResponse(page1),
            "/events/999": FakeResponse({"message": "introuvable"}, 404),
        }
    )

    assert client.get(f"{sporthive._API_BASE}/events/42").json() == event

    reponse_p0 = client.get(
        f"{sporthive._API_BASE}/races/111/participants",
        params={"page": 0, "size": sporthive._PAGE_SIZE},
    )
    reponse_p1 = client.get(
        f"{sporthive._API_BASE}/races/111/participants",
        params={"page": 1, "size": sporthive._PAGE_SIZE},
    )
    assert reponse_p0.json() == page0
    assert reponse_p1.json() == page1

    reponse_inconnue = client.get(f"{sporthive._API_BASE}/events/999")
    assert reponse_inconnue.status_code == 404
    with pytest.raises(httpx.HTTPError):
        reponse_inconnue.raise_for_status()

    # Two calls really went out to race 111...
    assert len(client.calls_containing("/races/111/participants")) == 2
    # ... and none to the dangerous ordinal /races/1 (trap #1 of the source):
    # this absence assertion, not a raw count, is what T013 and T027 will
    # reproduce against the real scraper.
    assert client.calls_containing("/races/1/participants") == []


# ── URL reading (T006 / T007) — the event id is the only thing the URL carries

#: The eight cases of the "Lecture d'URL" table of
#: specs/004-sporthive-scraper/contracts/provider-contract.md. The first six
#: are the same event seen at three depths (event / race / bib) and through
#: three façades — FR-002.
_EVENT_ID = "7237011278055708416"

_URLS_LISIBLES = [
    f"https://results.sporthive.com/events/{_EVENT_ID}",
    f"https://results.sporthive.com/events/{_EVENT_ID}/races/1",
    f"https://results.sporthive.com/events/{_EVENT_ID}/races/1/bib/426",
    f"https://results.sporthive.com/events/{_EVENT_ID}/races/1/bib/426/split",
    f"https://sporthive.com/events/s/{_EVENT_ID}/races/1",
    f"https://results.sporthive.com/en/events/{_EVENT_ID}/races/1",
]


@pytest.mark.parametrize("url", _URLS_LISIBLES)
def test_parse_url_reads_the_event_id_at_every_depth(url):
    """Three depths, three façades, one event: the race ordinal and the bib
    carry nothing the scraper needs (FR-002, D1/D3).
    """
    assert sporthive._parse_url(url) == _EVENT_ID


#: Two families of event ids coexist on the very same routes: the 19-digit
#: snowflake above (the historical stock) and this GUID, which is what the
#: source now mints for **recent** events. Measured on 30/07/2026 — both are
#: served by `/events/{id}`, `/events/{id}/races` and `/races/{id}/participants`
#: alike. A `\d+`-only pattern turns every recent event into an unreadable URL.
_EVENT_GUID = "bdea2f10-1510-481c-b5ef-ef7f1926a06f"

_URLS_GUID = [
    f"https://sporthive.com/events/s/{_EVENT_GUID}",
    f"https://sporthive.com/events/s/{_EVENT_GUID}/race/9c945c48-95ea-4680-bc98-cc5ea4e040c3",
    f"https://results.sporthive.com/events/{_EVENT_GUID}",
    f"https://results.sporthive.com/en/events/{_EVENT_GUID}/races/1",
]


@pytest.mark.parametrize("url", _URLS_GUID)
def test_parse_url_reads_a_guid_event_id(url):
    """The recent stock is GUID-identified, at every depth and façade.

    `2026 Europe Triathlon Junior Cup Izvorani` (3 races, 93 entrants) is one of
    them, and the deep form here is what the site itself puts in the address bar.
    """
    assert sporthive._parse_url(url) == _EVENT_GUID


@pytest.mark.parametrize("url", [
    "https://results.sporthive.com/events/abc",
    "https://results.sporthive.com/",
    "https://results.sporthive.com/profile",
    "https://sporthive.com/events/s/abc/races/1",
    # Accepting GUIDs must stay a **strict** widening: a truncated or
    # malformed GUID is still an unreadable URL, not a request to fire blind.
    "https://sporthive.com/events/s/bdea2f10-1510-481c-b5ef",
    "https://sporthive.com/events/s/bdea2f10151048...1c5ef-ef7f1926a06f",
])
def test_parse_url_refuses_a_path_without_an_event_id(url):
    """FR-003: the refusal names the expected form, it doesn't just say "no"."""
    with pytest.raises(ValueError, match=r"events/"):
        sporthive._parse_url(url)


def test_parse_url_never_exposes_the_race_ordinal():
    """Trap n°1 of the source, killed by construction (D1): `_parse_url` has no
    channel through which the `1` of `/races/1` could reach the API as a race
    id. `GET /races/1` answers 200 with an unrelated 2015 event.
    """
    lu = sporthive._parse_url(
        f"https://results.sporthive.com/events/{_EVENT_ID}/races/1/bib/426"
    )

    assert isinstance(lu, str)
    assert lu == _EVENT_ID


# ── API client and pagination (T010 / T011) ──────────────────────────────────

_RACE_ID = "7242234087144997120"


def test_fetch_event_and_races_read_the_two_metadata_routes():
    client = FakeClient({
        f"/events/{_EVENT_ID}/races": FakeResponse(_fixture("sporthive_races.json")),
        f"/events/{_EVENT_ID}": FakeResponse(_fixture("sporthive_event.json")),
    })

    event = sporthive._fetch_event(client, _EVENT_ID)
    races = sporthive._fetch_races(client, _EVENT_ID)

    assert event["eventName"] == "Triathlon Sud Vendee Dimanche"
    # A bare array, not a Spring page: `/races` is the only unpaginated route.
    assert [race["raceName"] for race in races] == [
        "Triathlon S", "Relais Triathlon S", "6-9 Ans",
        "10-13 Ans", "Triathlon M", "Relais Triathlon M",
    ]


def test_iter_participants_stops_on_last_and_always_asks_for_size_10():
    """`last` is the source's own stop criterion (D4), and `size` is capped at
    10 server-side — `size=50` gets a 400. Asserting the parameter on **every**
    call is what keeps a future "optimisation" from silently re-reading the
    same ten rows via the dead `count`/`offset` pair.
    """
    client = FakeClient({
        f"/races/{_RACE_ID}/participants?page=0": FakeResponse(
            _fixture("sporthive_participants_p0.json")
        ),
        f"/races/{_RACE_ID}/participants?page=1": FakeResponse(
            _fixture("sporthive_participants_p1.json")
        ),
    })

    lus = list(sporthive._iter_participants(client, _RACE_ID))

    assert [p["bib"] for p in lus][:3] == ["117", "203", "426"]
    assert len(lus) == 13
    # Two pages, and no third: `last: true` stopped the loop.
    appels = client.calls_containing("/participants")
    assert len(appels) == 2
    assert all(f"size={sporthive._PAGE_SIZE}" in appel for appel in appels)
    assert all("count=" not in appel and "offset=" not in appel for appel in appels)


def test_iter_participants_stops_on_an_empty_page_even_without_last():
    """A page past the end answers `content: []` without error. Stopping there
    too keeps the loop from depending on a single criterion.
    """
    page0 = _fixture("sporthive_participants_p0.json")
    vide = {**page0, "content": [], "number": 1, "last": False, "numberOfElements": 0}
    client = FakeClient({
        f"/races/{_RACE_ID}/participants?page=0": FakeResponse(page0),
        f"/races/{_RACE_ID}/participants?page=1": FakeResponse(vide),
    })

    lus = list(sporthive._iter_participants(client, _RACE_ID))

    assert len(lus) == 10
    assert len(client.calls_containing("/participants")) == 2


def test_iter_participants_raises_when_the_page_cap_is_reached(monkeypatch):
    """The cap covers a **false stop invariant** (D4, FR-009). Raising beats
    returning rows that are probably duplicated: a refused import replays
    (`rescrape-db --urls-from -`), a ranking silently truncated and marked
    reliable does not. Event scope, not race scope — nothing says the next race
    would fare better.
    """
    monkeypatch.setattr(sporthive, "_MAX_PAGES", 3)
    sans_fin = {**_fixture("sporthive_participants_p0.json"), "last": False}
    client = FakeClient({"/participants": FakeResponse(sans_fin)})

    with pytest.raises(ValueError, match=r"pagination|pages"):
        list(sporthive._iter_participants(client, _RACE_ID))

    assert len(client.calls_containing("/participants")) == 3


def test_fetch_json_lets_a_server_error_through_untranslated():
    """A 5xx is not a link problem: translating it into `ValueError` would make
    it read as one in the CLI report. Same rule as ok-time.
    """
    client = FakeClient(defaut=FakeResponse({"message": "boom"}, 503))

    with pytest.raises(httpx.HTTPError):
        sporthive._fetch_races(client, _EVENT_ID)


# ── Event scraping (T012–T021) — shared scaffolding ──────────────────────────

URL_SHEET = f"https://results.sporthive.com/events/{_EVENT_ID}/races/1/bib/426"


def _page(participants: list[dict], *, last: bool = True) -> dict:
    """A Spring page around `participants`.

    `totalElements` / `totalPages` are filled in for realism only: the scraper
    must never read them (D4). A test that started depending on them would be
    testing the wrong thing.
    """
    return {
        "content": participants,
        "number": 0,
        "size": 10,
        "totalElements": len(participants),
        "totalPages": 1,
        "first": True,
        "last": last,
        "numberOfElements": len(participants),
    }


def _course(ordinal: int, *, annonces: int = 1, nom: str = "", distance: int = 25750) -> dict:
    """One race of `/events/{id}/races`.

    `id` (snowflake) and `activeRaceId` (local ordinal) are deliberately kept
    disjoint, as they are on all 32 races of the panel: a test whose two
    identifiers happened to coincide would let trap n°1 through.
    """
    return {
        "id": f"72422340871449971{ordinal:02d}",
        "activeRaceId": ordinal,
        "raceName": nom or f"Triathlon {ordinal}",
        "classificationsCount": annonces,
        "distanceInMeter": distance,
    }


def _participant(bib: str, **surcharges) -> dict:
    """A finisher of the Sheet's Triathlon S (bib 426), bib overridden."""
    base = copy.deepcopy(_fixture("sporthive_participants_p0.json")["content"][2])
    base["bib"] = bib
    base.update(surcharges)
    return base


def _routes(courses: list[dict], pages: dict[int, list[list[dict]]]) -> dict:
    """Routes of a whole event. `pages` is keyed by `activeRaceId`, for
    readability — the scraper still has to go through `id` to reach them.

    `/races` is inserted **before** `/events/{id}`: the latter is a prefix of
    the former, and `FakeClient` matches fragments in insertion order.
    """
    routes: dict = {
        f"/events/{_EVENT_ID}/races": FakeResponse(courses),
        f"/events/{_EVENT_ID}": FakeResponse(_fixture("sporthive_event.json")),
    }
    for course in courses:
        lots = pages.get(course["activeRaceId"], [])
        for numero, lot in enumerate(lots):
            routes[f"/races/{course['id']}/participants?page={numero}"] = FakeResponse(
                _page(lot, last=numero == len(lots) - 1)
            )
    return routes


def _client_factice(monkeypatch, routes: dict, defaut: FakeResponse | None = None) -> FakeClient:
    client = FakeClient(routes, defaut)
    monkeypatch.setattr(sporthive.httpx, "Client", lambda *a, **k: client)
    return client


# ── T012 — completeness guard: race scope, never event scope ─────────────────


def test_scrape_event_all_drops_only_the_truncated_race(monkeypatch, caplog):
    """FR-008 / FR-008a: one race short of its announced count is dropped, the
    five others are imported, and **nothing** propagates. Refusing the whole
    event made it permanently unimportable — including the TCN members of the
    five healthy races (alternative rejected in D4).
    """
    courses = [_course(n) for n in range(1, 7)]
    courses[2]["classificationsCount"] = 2  # announces 2, only one will be served
    pages = {n: [[_participant(f"{n}01")]] for n in range(1, 7)}
    client = _client_factice(monkeypatch, _routes(courses, pages))

    with caplog.at_level(logging.WARNING, logger=sporthive.__name__):
        resultats = sporthive.scrape_event_all(URL_SHEET)

    assert len(resultats) == 5
    assert "301" not in {r.bib_number for r in resultats}
    # The warning is the **only** trace: the CLI report counts events, so this
    # one comes back a success with 5 races out of 6. Hence it must be usable
    # on its own — race name, ordinal, and both counts.
    journal = "\n".join(caplog.messages)
    assert "Triathlon 3" in journal
    assert "3" in journal and "1" in journal and "2" in journal
    # The dropped race was really paginated, it wasn't skipped upstream.
    assert client.calls_containing(f"/races/{courses[2]['id']}/participants")


def test_scrape_event_all_accepts_a_race_that_gained_entrants(monkeypatch, caplog):
    """The comparison is a **floor**, never an equality: a live race can gain
    ranked entrants between `/races` and the end of pagination. The surplus is
    logged, not refused (D4).
    """
    courses = [_course(1, annonces=1)]
    pages = {1: [[_participant("101"), _participant("102")]]}
    _client_factice(monkeypatch, _routes(courses, pages))

    with caplog.at_level(logging.INFO, logger=sporthive.__name__):
        resultats = sporthive.scrape_event_all(URL_SHEET)

    assert len(resultats) == 2
    assert any("2" in message and "1" in message for message in caplog.messages)


# ── T013 — a race with no ranked entrants costs no request ───────────────────


def test_scrape_event_all_skips_a_race_without_entrants_and_never_calls_it(monkeypatch, caplog):
    """FR-008b / D14. The skip is not cosmetic: an empty `Course` has no
    participation without `total_time`, so `cache.is_in_progress` calls it
    finished and freezes the **whole event**'s re-scrape for 30 days — the six
    races share one `source_url`.
    """
    courses = _fixture("sporthive_races_empty.json")
    routes = {
        f"/events/{_EVENT_ID}/races": FakeResponse(courses),
        f"/events/{_EVENT_ID}": FakeResponse(_fixture("sporthive_event.json")),
        f"/races/{courses[0]['id']}/participants?page=0": FakeResponse(
            _fixture("sporthive_participants_p0.json")
        ),
        f"/races/{courses[0]['id']}/participants?page=1": FakeResponse(
            _fixture("sporthive_participants_p1.json")
        ),
    }
    client = _client_factice(monkeypatch, routes)

    with caplog.at_level(logging.INFO, logger=sporthive.__name__):
        resultats = sporthive.scrape_event_all(URL_SHEET)

    assert len(resultats) == 13
    # Bare event name, not "… - Triathlon S": cf.
    # `test_the_sheets_s_race_keeps_the_bare_event_name_and_that_is_measured`.
    assert {r.event_name for r in resultats} == {"Triathlon Sud Vendee Dimanche"}
    # The point of the task: not just "absent from the result", but **no
    # request emitted** for it.
    assert client.calls_containing(f"/races/{courses[1]['id']}") == []
    assert any("Triathlon Decouverte" in message for message in caplog.messages)


# ── T014 — scalars: times, ranks, gender, status ─────────────────────────────


@pytest.mark.parametrize("brut, attendu", [
    ("00:57:33.2510000", "00:57:33"),   # 7-decimal fraction, the Sheet's form
    ("00:09:45.551", "00:09:45"),       # 3-decimal fraction, `legDuration` form
    ("00:57:33", "00:57:33"),
    ("00:00:00", ""),                   # non-finisher: zero means absent
    ("", ""),
    (None, ""),
])
def test_time_truncates_the_fraction_and_reads_zero_as_absent(brut, attendu):
    """D6. The truncation must come **before** `normalize_time`, whose
    `HH:MM:SS` pattern is anchored on the end of the string: it would return
    `00:57:33.2510000` verbatim and that value would land in the database.
    """
    assert sporthive._time(brut) == attendu


def test_total_time_prefers_the_chip_then_falls_back_on_the_gun():
    """The athlete's real time. Reversing the priority changes 7 435 rows of the
    panel; 2 925 have no chip and 2 092 no gun, so neither column is usable
    alone (D6).
    """
    ctx = sporthive._race_context(URL_SHEET, _fixture("sporthive_event.json"), _course(1))

    les_deux = sporthive._to_result(_participant("1"), ctx)
    gun_seul = sporthive._to_result(
        _participant("2", chipTimeOfParticipant=None, gunTimeOfParticipant="01:02:03"), ctx
    )
    aucun = sporthive._to_result(
        _participant("3", chipTimeOfParticipant=None, gunTimeOfParticipant=None), ctx
    )

    assert les_deux.total_time == "00:57:33"
    assert gun_seul.total_time == "01:02:03"
    assert aucun.total_time == ""


@pytest.mark.parametrize("brut, attendu", [(0, None), (None, None), (42, 42), ("7", 7)])
def test_rank_reads_zero_as_absent(brut, attendu):
    """D12: `overallPosition == 0` means "not ranked" (172 rows of the panel,
    all non-finishers). `normalize_rank` alone would return `0`, which the front
    displays as a place.
    """
    assert sporthive._rank(brut) == attendu


def test_gender_keeps_only_m_and_f():
    """`U` covers 4 243 rows (41 %) and the front doesn't render it: better
    empty than a value it can't display (D12, same as ok-time's `X`)."""
    ctx = sporthive._race_context(URL_SHEET, _fixture("sporthive_event.json"), _course(1))

    assert sporthive._to_result(_participant("1", gender="M"), ctx).gender == "M"
    assert sporthive._to_result(_participant("2", gender="F"), ctx).gender == "F"
    assert sporthive._to_result(_participant("3", gender="U"), ctx).gender == ""


@pytest.mark.parametrize("validity, attendu", [
    ("DNF", STATUS_DNF),
    ("DNS", STATUS_DNS),
    ("DQ", STATUS_DSQ),   # `DQ`, not `DSQ` — the source's spelling
])
def test_status_comes_from_validity_and_never_from_the_dead_booleans(validity, attendu):
    """Trap n°3: `dns` and `dsq` are `false` on 10 360 rows out of 10 360,
    including the 35 whose `validity` is `DNS`. Trusting them misses **100 %**
    of statuses. The fixture pins them to `false` on purpose.
    """
    ctx = sporthive._race_context(URL_SHEET, _fixture("sporthive_event.json"), _course(1))
    lignes = _fixture("sporthive_statuses.json")["content"]
    ligne = next(p for p in lignes if p["validity"] == validity)
    assert ligne["dns"] is False and ligne["dsq"] is False

    resultat = sporthive._to_result(ligne, ctx)

    assert resultat.status == attendu
    assert resultat.total_time == ""
    assert resultat.rank_overall is None


def test_status_falls_back_on_the_rank_when_the_source_is_silent(monkeypatch):
    """FR-014a / D5. 73 rows of the panel have neither `chipTime` nor `gunTime`
    while being **ranked**. Left to `mapping.derive_status` — "finisher if a
    total time, else DNF" — they would show up as abandons in the front's Place
    column. That is the ok-time trap, and the scraper speaks explicitly instead.
    """
    ctx = sporthive._race_context(URL_SHEET, _fixture("sporthive_event.json"), _course(1))
    classe, non_classe = _fixture("sporthive_no_time_ranked.json")["content"]

    resultat_classe = sporthive._to_result(classe, ctx)
    resultat_non_classe = sporthive._to_result(non_classe, ctx)

    assert (classe["chipTimeOfParticipant"], classe["gunTimeOfParticipant"]) == (None, None)
    assert classe["validity"] is None
    assert resultat_classe.status == STATUS_FINISHER
    assert resultat_classe.rank_overall == 42
    # Ranked at 0 and no time: nothing says finisher, DNF stands.
    assert resultat_non_classe.status == STATUS_DNF


def test_status_stays_empty_when_a_time_lets_the_infra_decide():
    """`""` means "the scraper doesn't take a side" (contract of
    `ScrapedResult`): a finisher with a time needs no explicit status, and
    posing one would duplicate `mapping.derive_status`."""
    ctx = sporthive._race_context(URL_SHEET, _fixture("sporthive_event.json"), _course(1))

    assert sporthive._to_result(_participant("1"), ctx).status == ""


def test_identity_is_split_except_on_a_relay(monkeypatch):
    """D11: splitting `LA COUSINADE` would create an athlete "COUSINADE, LA".
    The `tags` array, which looks like a ready-made split, is a search index
    (trap n°4) and yields the same shape for a team as for a person.
    """
    event = _fixture("sporthive_event.json")
    ctx_individuel = sporthive._race_context(URL_SHEET, event, _course(1, nom="Triathlon S"))
    ctx_relais = sporthive._race_context(URL_SHEET, event, _course(2, nom="Relais Triathlon S"))
    equipe = _fixture("sporthive_relay.json")["content"][0]

    personne = sporthive._to_result(_participant("426"), ctx_individuel)
    relais = sporthive._to_result(equipe, ctx_relais)

    assert (personne.athlete_name, personne.athlete_firstname) == ("RENAUD", "Thomas")
    assert (relais.athlete_name, relais.athlete_firstname) == ("LA COUSINADE", "")


# ── T015 — segments come from `type`; `sportName` only rescues an `Other` ────


def test_segments_label_a_five_leg_triathlon_in_order():
    legs = _fixture("sporthive_participants_p0.json")["content"][2]["legs"]

    assert sporthive._segments(legs) == [
        ("natation", "00:09:46"),
        ("transition", "00:01:32"),
        ("vélo", "00:27:43"),
        ("transition", "00:01:14"),
        ("course à pied", "00:17:21"),
    ]


def test_segments_put_the_kids_run_last_and_never_in_a_t2_slot():
    """The 4-leg sequence (one single transition) is what forbids a positional
    mapping to swim/t1/bike/t2/run: the run would land in the `t2` slot."""
    legs = _fixture("sporthive_kids.json")["content"][0]["legs"]

    segments = sporthive._segments(legs)

    assert segments == [
        ("natation", "00:03:12"),
        ("transition", "00:00:48"),
        ("vélo", "00:07:05"),
        ("course à pied", "00:04:33"),
    ]
    assert segments[-1][0] == "course à pied"


def test_segments_read_type_when_sportname_is_null():
    """`sportName` is `null` on 5 635 of the 24 042 legs of the panel (23 %) and
    isn't normalised where present (`SWIM` / `Swim` / `T1`). `type` is present
    24 042 times out of 24 042 (D7).
    """
    legs = _fixture("sporthive_monosport.json")["content"][0]["legs"]
    assert legs[0]["sportName"] is None

    assert sporthive._segments(legs) == [("course à pied", "00:38:12")]


def test_segments_drop_the_phantom_leg_of_a_non_finisher():
    """D8: a non-finisher publishes a single `Running` leg at `00:00:00` whose
    only split is `Start`. Filtering on the **duration** rather than the status
    also covers an untimed leg on a finisher, with no special case.
    """
    legs = _fixture("sporthive_statuses.json")["content"][0]["legs"]
    assert legs[0]["participantSplits"][0]["splitName"] == "Start"

    assert sporthive._segments(legs) == []


def test_segments_render_an_unknown_type_verbatim():
    """Never observed. Rendering it verbatim beats losing the time (D7)."""
    assert sporthive._segments(
        [{"type": "Kayaking", "sportName": "PADDLE", "legDuration": "00:12:00"}]
    ) == [("Kayaking", "00:12:00")]


def test_segments_fall_back_to_sportname_when_type_says_other():
    """`Other` is a **non**-answer, and the panel of 30/07/2026 has it.

    ACCURO Jersey Triathlon publishes `type: "Other"` on all five legs of its
    « Standard » race (177 entrants), swim included, while `sportName` names
    them correctly. Reading `type` alone rendered that whole race as `Other`,
    `Other (2)` … `Other (5)` once `build_splits` disambiguated — five times
    the same non-word where the source published five disciplines.

    `type` still comes first (D7 holds: it is the normalised field, present on
    all 24 042 legs of the earlier panel); `sportName` is only consulted when
    `type` carries no information.
    """
    legs = [
        {"sportName": "Swim", "type": "Other", "legDuration": "00:29:35"},
        {"sportName": "Transition 1", "type": "Other", "legDuration": "00:02:41"},
        {"sportName": "Bike", "type": "Other", "legDuration": "01:16:04"},
        {"sportName": "Transition 2", "type": "Other", "legDuration": "00:01:22"},
        {"sportName": "Run", "type": "Other", "legDuration": "00:48:19"},
    ]

    assert sporthive._segments(legs) == [
        ("natation", "00:29:35"),
        ("transition", "00:02:41"),
        ("vélo", "01:16:04"),
        ("transition", "00:01:22"),
        ("course à pied", "00:48:19"),
    ]


def test_segments_fall_back_on_the_lowercase_transitions_of_an_international_race():
    """2026 Europe Triathlon Junior Cup Izvorani: `type` is right on the three
    disciplines but `Other` on both transitions, which `sportName` names.
    """
    legs = [
        {"sportName": "swim", "type": "Swimming", "legDuration": "00:05:41"},
        {"sportName": "transition", "type": "Other", "legDuration": "00:01:16"},
        {"sportName": "bike", "type": "Cycling", "legDuration": "00:16:23"},
        {"sportName": "transition2", "type": "Other", "legDuration": "00:00:21"},
        {"sportName": "run", "type": "Running", "legDuration": "00:07:37"},
    ]

    assert [label for label, _ in sporthive._segments(legs)] == [
        "natation", "transition", "vélo", "transition", "course à pied",
    ]


def test_segments_keep_an_uninformative_type_when_sportname_is_null_too():
    """Nothing to fall back on: the time is kept rather than dropped (D7)."""
    assert sporthive._segments(
        [{"type": "Other", "sportName": None, "legDuration": "00:12:00"}]
    ) == [("Other", "00:12:00")]


def test_two_transitions_are_disambiguated_by_build_splits_not_overwritten():
    """The two transitions of a triathlon carry the same label on purpose:
    `mapping.build_splits` suffixes the second rather than silently overwriting
    a time. Verified here so the French labels are checked end to end.
    """
    ctx = sporthive._race_context(URL_SHEET, _fixture("sporthive_event.json"), _course(1))
    resultat = sporthive._to_result(_participant("426"), ctx)

    assert build_splits(resultat) == {
        "natation": "00:09:46",
        "transition": "00:01:32",
        "vélo": "00:27:43",
        "transition (2)": "00:01:14",
        "course à pied": "00:17:21",
    }


# ── T016 — event metadata ────────────────────────────────────────────────────


#: The five rows of the "Classification" table of the contract.
_CLASSIFICATION = [
    ("Triathlon S", "Triathlon Sud Vendee Dimanche", "Triathlon", "triathlon-s"),
    ("Triathlon M", "Triathlon Sud Vendee Dimanche", "Triathlon", "triathlon-m"),
    ("6-9 Ans", "Triathlon Sud Vendee Dimanche", "Triathlon", "triathlon"),
    ("Senior Men", "UK CAU Inter Counties Cross Country Championships", "Running",
     "course-a-pied"),
    ("Trail 10K", "Oeiras Trail", "Running", "trail"),
]


@pytest.mark.parametrize("race_name, event_name, event_type, attendu", _CLASSIFICATION)
def test_event_type_uses_the_source_event_type_as_context(
    race_name, event_name, event_type, attendu
):
    """D9, the most counter-intuitive point of the plan, and a measured one.
    `Senior Men` names no sport, so the classifier consults its context — and
    without `eventType` in it, the 2 852 rows of the UK cross would enter the
    database as `triathlon`, display as such and **survive**
    `federal_only=true`, the filter that exists to exclude them.
    """
    event = {"eventName": event_name, "eventType": event_type, "date": "2024-09-22T00:00:00"}
    race = {"id": "1", "activeRaceId": 1, "raceName": race_name, "distanceInMeter": 0}

    assert sporthive._race_context(URL_SHEET, event, race).event_type == attendu


def test_event_type_regression_lock_on_the_context_without_the_event_type():
    """The guard for the test above: dropping `eventType` from the context is a
    silent regression, `Senior Men` falling back on the classifier's default.
    """
    assert classify_event_type(
        "Senior Men", contexte="UK CAU Inter Counties Cross Country Championships"
    ) == "triathlon"


def test_race_context_qualifies_the_name_dates_and_measures():
    """One distinct `Course` per race (FR-006): without qualification the six
    races of an event merge into one and their bibs collide (#21). The date is
    read from the ISO string — no French parsing here (FR-020).
    """
    ctx = sporthive._race_context(
        URL_SHEET, _fixture("sporthive_event.json"), _course(5, nom="Triathlon M")
    )

    assert ctx.event_name == "Triathlon Sud Vendee Dimanche - Triathlon M"
    assert ctx.event_date == date(2024, 9, 22)
    assert ctx.distance_km == 25.75
    assert ctx.source_url == URL_SHEET


def test_the_sheets_s_race_keeps_the_bare_event_name_and_that_is_measured():
    """Divergence with the expected-name column of `data-model.md`, and it is
    the helper's behaviour that is authoritative.

    `qualify_event_name` skips the qualifier when it is already **a substring**
    of the name, and "triathlon s" is one of "triathlon **s**ud vendee
    dimanche". So the S race keeps the bare event name where `data-model.md`
    announced "… - Triathlon S". That column was written by hand — the document
    only claims to have run `classify_event_type` and the distance conversion.

    Not #21 for all that, and this test pins the reason: the six names stay
    **distinct**, so no two races merge and no bib collides. Fixing the
    shortcut would mean touching a helper shared by twelve providers and
    renaming courses already in the database — out of scope here (principle VI).
    """
    event = _fixture("sporthive_event.json")
    noms = {
        sporthive._race_context(URL_SHEET, event, _course(n, nom=nom)).event_name
        for n, nom in enumerate(
            [c["raceName"] for c in _fixture("sporthive_races.json")], start=1
        )
    }

    assert "Triathlon Sud Vendee Dimanche" in noms
    assert len(noms) == 6


@pytest.mark.parametrize("nom, attendu", [
    ("Relais Triathlon S", True),
    ("Olympic Team Relay", True),
    ("Sprint Team Relay", True),
    ("Équipes mixtes", True),
    ("Duo découverte", True),
    ("Triathlon S", False),
    ("6-9 Ans", False),
    ("Trail 10K", False),
    ("Senior Men", False),
])
def test_is_relay_is_decided_per_race_on_its_name(nom, attendu):
    """D10: decided per race, not per participant — otherwise `Course.is_relay`
    and `Participation.is_relay` diverge with the read order (ok-time
    precedent). No fallback on the shape of names is possible: the source
    publishes one row per team, with a free-form name and no teammate separator.
    """
    event = _fixture("sporthive_event.json")
    assert sporthive._race_context(URL_SHEET, event, _course(1, nom=nom)).is_relay is attendu


def test_distance_zero_is_absent_so_mapping_can_extract_it_from_the_name():
    ctx = sporthive._race_context(
        URL_SHEET, _fixture("sporthive_event.json"), _course(1, distance=0)
    )
    assert ctx.distance_km is None


def test_city_and_country_are_kept_verbatim_in_raw_data():
    """FR-022a / D15. `ScrapedResult` has no city field, and adding one would
    touch a contract shared by twelve providers for one of them. The `city` key
    is the one runnerbreizh already uses, for exactly this reason. `location`
    beats what the map would deduce from the event name — `geocode_service`
    renders "Sud Vendee Dimanche" there.
    """
    ctx = sporthive._race_context(URL_SHEET, _fixture("sporthive_event.json"), _course(1))
    resultat = sporthive._to_result(_participant("426"), ctx)

    assert resultat.raw_data["city"] == "L'Aiguillon sur Mer (85)"
    assert resultat.raw_data["country"] == "FRA"


def test_the_provider_slug_matches_the_registry_entry():
    """`--provider sporthive` filters on the registry name and the CLI compares
    it to `Course.provider`, filled from this module: a drift would make the
    option select nothing, silently.
    """
    from app.scrapers import registry

    assert sporthive._PROVIDER == registry.SporthiveProvider.name
    assert {
        r.provider
        for r in [
            sporthive._to_result(
                _participant("1"),
                sporthive._race_context(URL_SHEET, _fixture("sporthive_event.json"), _course(1)),
            )
        ]
    } == {"sporthive"}


# ── T022 / T024 — the club (US2): filled in, and judged elsewhere ────────────


@pytest.mark.parametrize("team_name, attendu_club, attendu_tcn", [
    ("TRI CLUB NANTAIS", "TRI CLUB NANTAIS", True),
    ("TRIATHLON CLUB NANTAIS", "TRIATHLON CLUB NANTAIS", True),
    # A neighbouring label: a Nantes club, not ours. This is the #76 false
    # positive — a substring match on "nantais" counted it in.
    ("ASPTT NANTES TRI", "ASPTT NANTES TRI", False),
    ("S/L STADE NANTAIS AC", "S/L STADE NANTAIS AC", False),
    (None, "", False),
    ("", "", False),
])
def test_club_is_carried_verbatim_and_judged_by_core_club(team_name, attendu_club, attendu_tcn):
    """FR-019. `teamName` is the club on individual races (44 % of the panel's
    rows, 686 distinct labels). The scraper carries it **as is**: whether it is
    the TCN is `core/club.py`'s call, and its alone.
    """
    ctx = sporthive._race_context(URL_SHEET, _fixture("sporthive_event.json"), _course(1))

    resultat = sporthive._to_result(_participant("426", teamName=team_name), ctx)

    assert resultat.club == attendu_club
    assert is_tcn(resultat.club) is attendu_tcn


def test_the_sheets_tcn_member_is_recognised_without_adding_a_label():
    """The one Sporthive link of the Sheet points at bib 426 of the S race — a
    "TRI CLUB NANTAIS", a label already in `core/club.py`'s allowlist. The
    event carries 29 of these participations.
    """
    lignes = _fixture("sporthive_participants_p0.json")["content"]

    assert [p["teamName"] for p in lignes if is_tcn(p["teamName"])] == [
        "TRI CLUB NANTAIS", "TRI CLUB NANTAIS"
    ]
    assert next(p for p in lignes if p["bib"] == "426")["teamName"] == "TRI CLUB NANTAIS"


def _litteraux_de_code(module) -> list[str]:
    """The module's string literals, **docstrings excluded**.

    Excluding prose is what makes the guard below meaningful rather than
    annoying: a docstring saying "`core/club.py` stays the only judge of TCN
    membership" is precisely the documentation we want, and a raw `grep` for
    "TCN" would forbid writing it. A hard-coded label, on the other hand, lives
    in a code literal — which this keeps.
    """
    arbre = ast.parse(inspect.getsource(module))
    porteurs = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    docstrings = {
        id(noeud.body[0].value)
        for noeud in ast.walk(arbre)
        if isinstance(noeud, porteurs)
        and noeud.body
        and isinstance(noeud.body[0], ast.Expr)
        and isinstance(noeud.body[0].value, ast.Constant)
        and isinstance(noeud.body[0].value.value, str)
    }
    return [
        noeud.value
        for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.Constant)
        and isinstance(noeud.value, str)
        and id(noeud) not in docstrings
    ]


def _identifiants_de_code(module) -> set[str]:
    """Names, attributes and imports the module actually references."""
    arbre = ast.parse(inspect.getsource(module))
    noms: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Name):
            noms.add(noeud.id)
        elif isinstance(noeud, ast.Attribute):
            noms.add(noeud.attr)
        elif isinstance(noeud, ast.alias):
            noms.update(noeud.name.split("."))
            if noeud.asname:
                noms.add(noeud.asname)
        elif isinstance(noeud, ast.ImportFrom) and noeud.module:
            noms.update(noeud.module.split("."))
    return noms


def test_the_module_never_reimplements_club_membership():
    """The guard of #76, where the predicate existed in three diverging copies
    and the most permissive won on the counters: every label containing
    "nantais" was counted as TCN, athletics clubs included.

    Unlike `t2area.py` — which must filter to spare itself 876 requests, and
    **reuses** `core/club.py` for that — this scraper has no reason to know the
    TCN at all: it fills `club` and stops there. So what is forbidden here is
    not "a second implementation" but any mention **in the code**: no label, no
    predicate, not even an import of the module that owns them.

    Derived from `counter_scope.DEFAULT_TCN_CLUB_LABELS` — the labels the code
    ships with. The live list now lives in the database (#95), and a guard that
    read it would only be as strong as the row a test happened to seed.
    """
    litteraux = " | ".join(_litteraux_de_code(sporthive)).lower()
    identifiants = _identifiants_de_code(sporthive)

    for libelle in DEFAULT_TCN_CLUB_LABELS:
        assert libelle.lower() not in litteraux, libelle
    assert "nantais" not in litteraux
    # Neither the predicate, nor its SQL twin, nor the module holding them.
    assert not identifiants & {"is_tcn", "tcn_clause", "normalize_club", "counter_scope", "club"}


# ── T025–T028 (US3) — a link that can't be imported names its cause ──────────


def test_an_unreadable_url_is_refused_before_any_request(monkeypatch):
    """FR-003. The refusal names the expected form, and costs nothing: no
    request goes out, so a bad link in a batch doesn't spend a round trip.
    """
    client = _client_factice(monkeypatch, {})

    with pytest.raises(ValueError, match=r"events/<id>"):
        sporthive.scrape_event_all("https://results.sporthive.com/profile")

    assert client.calls == []


def test_an_unknown_event_is_refused_by_name_not_by_http_error(monkeypatch):
    """A 404 says "this id doesn't exist" — a link problem, so a `ValueError`
    that `import_service` wraps into `ScraperError` and the front shows verbatim.
    A raw `httpx.HTTPError` would read as an outage in the CLI report.
    """
    client = _client_factice(
        monkeypatch,
        {f"/events/{_EVENT_ID}": FakeResponse({"message": "Event with id X is not found"}, 404)},
    )

    with pytest.raises(ValueError, match=r"introuvable"):
        sporthive.scrape_event_all(URL_SHEET)

    # Refused on the metadata call: no ranking was ever requested.
    assert client.calls_containing("/participants") == []


@pytest.mark.parametrize("courses, pages, cas", [
    # Every race truncated: each announces 2, only one is served.
    ([_course(n, annonces=2) for n in range(1, 4)],
     {n: [[_participant(f"{n}01")]] for n in range(1, 4)},
     "toutes tronquées"),
    # Every race announcing zero ranked entrants.
    ([_course(n, annonces=0) for n in range(1, 4)], {}, "toutes à zéro classé"),
    # An event publishing no race at all.
    ([], {}, "aucune course publiée"),
])
def test_an_event_yielding_no_race_is_refused_in_french(monkeypatch, courses, pages, cas):
    """FR-008c / D14. This is the guard that closes the hole opened by dropping
    races one at a time: `import_service._require_event_name` does **not** raise
    on an empty list (`any()` of an empty list is false) and `batch` counts "no
    result" as a legitimate short-circuit. Without it, a wholly truncated event
    would be indistinguishable from a successful import in the report — the
    exact opposite of what `est_echec_total` guarantees at the batch level.

    The message is in **French**: it travels through `ScraperError`, which
    `register_exception_handlers` serialises to `{"detail": …}` and the front
    shows verbatim (mixed `DomainError` case of principle I).
    """
    _client_factice(monkeypatch, _routes(courses, pages))

    with pytest.raises(ValueError, match=r"aucune course importable") as leve:
        sporthive.scrape_event_all(URL_SHEET)

    # French, and it says why rather than just "empty".
    assert "Événement Sporthive" in str(leve.value), cas


def test_no_request_is_ever_made_to_the_race_ordinal_of_the_url(monkeypatch):
    """Trap n°1, locked as a regression test (D1, FR-004). On the real source
    `GET /races/1/participants` answers **200** and returns a 2015 event with
    1 173 finishers: reading the URL's ordinal as a race id would import a
    foreign event under the requested `source_url`, with no error at all.

    The URL under test carries `/races/1`, and the event's real race ids are
    19-digit snowflakes — `id == URL segment` held 0 times out of 32 on the
    panel, `activeRaceId == URL segment` 32 times out of 32.
    """
    courses = _fixture("sporthive_races.json")
    ordinaux = {str(course["activeRaceId"]) for course in courses}
    identifiants = {course["id"] for course in courses}
    assert ordinaux & identifiants == set()

    pages = {course["activeRaceId"]: [[_participant("1")]] for course in courses}
    # `classificationsCount` lowered to 1 so one page per race is enough; the
    # real counts (366, 29, …) belong to the completeness-guard tests.
    for course in courses:
        course["classificationsCount"] = 1
    client = _client_factice(monkeypatch, _routes(courses, pages))

    resultats = sporthive.scrape_event_all(URL_SHEET)

    assert len(resultats) == 6
    for ordinal in ordinaux:
        assert client.calls_containing(f"/races/{ordinal}/participants") == []
    # Symmetrical assertion: every ranking call went to a snowflake.
    for appel in client.calls_containing("/participants"):
        assert any(f"/races/{identifiant}/participants" in appel for identifiant in identifiants)


# ── Fan-out par race (issue #216) — patron Klikego répliqué : la sous-unité de
# cache TTL n'est plus l'événement mais la **race**, identifiée par son
# snowflake `race.id`. Cinq scénarios verrouillent le contrat :
#   1. nominal — trace complète, une entrée `heat_enumerated` par race,
#      `imported`/`cached`/`failures` cohérents ;
#   2. `cache_probe` — une race fraîche est sautée **avant** toute requête
#      réseau, `cached_urls` porte son URL canonique, `on_heat_start` n'est
#      pas notifié pour elle ;
#   3. isolation d'échec — une race qui lève reste dans `failures`, les
#      autres continuent (le refus double du module est préservé) ;
#   4. aucune race — l'événement à zéro course rend une trace vide, sans
#      appel réseau au-delà des métadonnées ;
#   5. `on_heat_start` — `total` = nombre à scraper, jamais le nombre
#      énuméré, sinon la progression sauterait des indices.


def _race_url_for(race: dict) -> str:
    """URL canonique attendue par le fan-out pour une race donnée."""
    return f"https://results.sporthive.com/events/{_EVENT_ID}/races/{race['id']}"


def test_scrape_event_fanout_nominal_returns_trace(monkeypatch):
    """Fan-out sans `cache_probe` : les 3 races énumérées sont toutes scrapées,
    la trace remonte les compteurs cohérents.

    `heats_imported` reste à 0 côté scraper — dérivé par `import_service` via
    l'invariant `enumerated = imported + cached + len(failures)`.
    """
    courses = [_course(n, annonces=1) for n in range(1, 4)]
    pages = {n: [[_participant(f"{n}01")]] for n in range(1, 4)}
    client = _client_factice(monkeypatch, _routes(courses, pages))

    resultats, trace = sporthive.scrape_event_fanout(URL_SHEET)

    assert len(resultats) == 3
    assert trace.heats_enumerated == 3
    assert trace.heats_cached == 0
    assert trace.heats_imported == 0  # dérivé par import_service
    assert trace.failures == []
    assert trace.cached_urls == []
    # Toutes les races ont été paginées : 3 appels de classement.
    assert len(client.calls_containing("/participants")) == 3
    # Chaque participation porte l'URL canonique par-race, pas l'URL de l'event.
    urls = {r.source_url for r in resultats}
    assert urls == {_race_url_for(c) for c in courses}


def test_scrape_event_fanout_cache_probe_skips_races(monkeypatch):
    """`cache_probe(race_url) == True` → la race est sautée **avant** toute
    requête réseau, comptée dans `heats_cached` et `cached_urls`.

    C'est le point du fan-out : sur un ré-import où k races sur N sont fraîches,
    on économise k × ~100 requêtes de pagination.
    """
    courses = [_course(n, annonces=1) for n in range(1, 4)]
    pages = {n: [[_participant(f"{n}01")]] for n in range(1, 4)}
    client = _client_factice(monkeypatch, _routes(courses, pages))

    cached_urls = {_race_url_for(courses[0]), _race_url_for(courses[2])}

    def probe(race_url: str) -> bool:
        return race_url in cached_urls

    resultats, trace = sporthive.scrape_event_fanout(URL_SHEET, cache_probe=probe)

    assert len(resultats) == 1
    assert trace.heats_enumerated == 3
    assert trace.heats_cached == 2
    assert set(trace.cached_urls) == cached_urls
    assert trace.failures == []
    # Seule la race non cachée a paginé son classement.
    assert len(client.calls_containing("/participants")) == 1
    assert client.calls_containing(f"/races/{courses[0]['id']}/participants") == []
    assert client.calls_containing(f"/races/{courses[2]['id']}/participants") == []


def test_scrape_event_fanout_race_failure_isolated(monkeypatch, caplog):
    """Une race qui lève est capturée dans `trace.failures` ; les autres passent.

    Le refus double du module est préservé : une race incomplète est droppée
    (comptée en `failure`), les autres continuent. Un `ValueError` d'une race
    n'annule pas l'événement.
    """
    courses = [_course(n, annonces=1) for n in range(1, 4)]
    # La 2e race annonce 3 classés mais la source n'en publie qu'un → drop.
    courses[1]["classificationsCount"] = 3
    pages = {
        1: [[_participant("101")]],
        2: [[_participant("201")]],
        3: [[_participant("301")]],
    }
    _client_factice(monkeypatch, _routes(courses, pages))

    with caplog.at_level(logging.WARNING, logger=sporthive.__name__):
        resultats, trace = sporthive.scrape_event_fanout(URL_SHEET)

    assert len(resultats) == 2  # races 1 et 3, la 2 est droppée
    assert trace.heats_enumerated == 3
    assert trace.heats_cached == 0
    assert len(trace.failures) == 1
    assert trace.failures[0]["heat_slug"] == str(courses[1]["id"])
    assert "tronqué" in trace.failures[0]["reason"]
    # La cause est journalisée en clair — même contrat que Klikego.
    assert any(courses[1]["raceName"] in message for message in caplog.messages)


def test_scrape_event_fanout_no_races_returns_empty(monkeypatch):
    """Événement sans race publiée : trace vide, aucune erreur levée.

    C'est le fan-out qui remonte l'événement vide au caller (via
    `heats_enumerated=0`) — le refus event-scoped (`ValueError` « aucune course
    importable ») ne s'applique qu'à `scrape_event_all`. Le fan-out laisse la
    décision à `import_service`, qui compte l'événement en cache/succès selon
    la présence de courses en base.
    """
    _client_factice(monkeypatch, _routes([], {}))

    resultats, trace = sporthive.scrape_event_fanout(URL_SHEET)

    assert resultats == []
    assert trace.heats_enumerated == 0
    assert trace.heats_cached == 0
    assert trace.failures == []
    assert trace.cached_urls == []


def test_scrape_event_fanout_on_heat_start_notifie_par_race_non_cache(monkeypatch):
    """`on_heat_start` est appelé avant chaque race effectivement scrapée.

    Deux races cachées sur cinq → 3 notifications, index 1..3 sur un total de 3,
    jamais sur les 2 sautées. Sans quoi la progression côté front paraîtrait
    sauter des indices (« 5/5 » alors qu'on n'en scrape que 3).
    """
    courses = [_course(n, annonces=1) for n in range(1, 6)]
    pages = {n: [[_participant(f"{n}01")]] for n in range(1, 6)}
    _client_factice(monkeypatch, _routes(courses, pages))

    # Deux races cachées, trois à scraper.
    cached_urls = {_race_url_for(courses[1]), _race_url_for(courses[3])}

    def probe(race_url: str) -> bool:
        return race_url in cached_urls

    notifications: list[tuple[str, str, int, int]] = []

    def on_heat_start(race_slug, race_label, index, total):
        notifications.append((race_slug, race_label, index, total))

    sporthive.scrape_event_fanout(
        URL_SHEET, cache_probe=probe, on_heat_start=on_heat_start,
    )

    assert len(notifications) == 3, "un appel par race scrapée, pas par race énumérée"
    assert [n[2] for n in notifications] == [1, 2, 3]
    assert all(n[3] == 3 for n in notifications), "total = nombre à scraper, jamais énuméré"
    # Aucune notification pour les slugs des races cachées.
    cached_slugs = {str(courses[1]["id"]), str(courses[3]["id"])}
    assert not any(n[0] in cached_slugs for n in notifications)


# ── Intégration Provider — le fan-out est bien routé par le registre (issue #216)


def test_sporthive_provider_exposes_last_trace_after_fanout(monkeypatch):
    """`SporthiveProvider.scrape_event_all` en mode nominal délègue au fan-out
    et pose `self.last_trace` — c'est ce que `import_service` lit pour peupler
    les 5 compteurs du SSE `done`.
    """
    from app.scrapers.registry import SporthiveProvider

    courses = [_course(n, annonces=1) for n in range(1, 3)]
    pages = {n: [[_participant(f"{n}01")]] for n in range(1, 3)}
    _client_factice(monkeypatch, _routes(courses, pages))

    provider = SporthiveProvider()
    resultats = provider.scrape_event_all(URL_SHEET)

    assert len(resultats) == 2
    assert provider.last_trace is not None
    assert provider.last_trace.heats_enumerated == 2
    assert provider.last_trace.heats_cached == 0
    assert provider.last_trace.failures == []


def test_sporthive_provider_single_heat_falls_back_to_event_scoped(monkeypatch):
    """`single_heat=True` retombe sur `scrape_event_all` du module — event-scoped.

    Sporthive n'a pas de `?heat=` dans l'URL, donc l'échappatoire ne cible
    pas une race unique : elle sert de retour au contrat historique, sans
    fan-out ni cache par-race. `last_trace` porte une trace synthétique
    1-heat pour maintenir l'invariant côté `import_service`.
    """
    from app.scrapers.registry import SporthiveProvider

    courses = [_course(n, annonces=1) for n in range(1, 3)]
    pages = {n: [[_participant(f"{n}01")]] for n in range(1, 3)}
    _client_factice(monkeypatch, _routes(courses, pages))

    provider = SporthiveProvider()
    resultats = provider.scrape_event_all(URL_SHEET, single_heat=True)

    assert len(resultats) == 2
    # Contrat event-scoped : les participations portent l'URL d'entrée, pas
    # l'URL canonique par-race.
    assert {r.source_url for r in resultats} == {URL_SHEET}
    assert provider.last_trace is not None
    assert provider.last_trace.heats_enumerated == 1
