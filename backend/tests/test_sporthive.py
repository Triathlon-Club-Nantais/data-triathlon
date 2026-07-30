"""
Test harness for scrapers/sporthive.py (network-free) — T002.

No scraper behaviour test here: at this stage `scrape_event_all` raises
`NotImplementedError` (T001), there is nothing to expect from it yet. This
file lays down the tool the next batches will rely on — fake HTTP client +
per-route call counter — and a single test exercising the harness itself, so a
broken harness doesn't surface later as a fake implementation failure.

JSON fixtures expected under `fixtures/sporthive_*.json` (dropped in batch 2):
loaded via `_fixture`, never read by hand.
"""
import json
from pathlib import Path

import httpx
import pytest

from app.scrapers import sporthive

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


# ---------------------------------------------------------------------------
# URL reading (T006 / T007) — the event id is the only thing the URL carries
# ---------------------------------------------------------------------------

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


@pytest.mark.parametrize("url", [
    "https://results.sporthive.com/events/abc",
    "https://results.sporthive.com/",
    "https://results.sporthive.com/profile",
    "https://sporthive.com/events/s/abc/races/1",
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


# ---------------------------------------------------------------------------
# API client and pagination (T010 / T011)
# ---------------------------------------------------------------------------

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
