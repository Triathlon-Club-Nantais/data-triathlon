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
