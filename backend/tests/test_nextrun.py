"""
nextrun.fr scraper tests (#1224).

Fixtures: real responses of the Défi-Swimrun de Lancieux 2026 (06/10/2026),
trimmed: the edition keeps 3 of its 7 races (one unpublished), the XS duo keeps
its first three teams, the XS solo is split in two pages to cover pagination.
"""
import json
from datetime import date
from pathlib import Path

import pytest

from app.scrapers import nextrun, registry
from app.scrapers.base import STATUS_DNF, STATUS_FINISHER

FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://nextrun.fr/events/defi-swimrun-de-lancieux/editions/2026/results"
DUO = "019b4c56-c27d-7720-a959-2a1ab4a56c9e"
SOLO = "019b5095-16e8-730a-b2ec-12d449b4740c"
KIDS = "019b4c59-b370-7e7f-9e61-f294127f2986"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"nextrun_lancieux_2026_{name}.json").read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, routes: dict[str, dict]):
        self.routes = routes
        self.calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url: str, params: dict | None = None):
        key = url if params is None else f"{url}?page={params['page']}"
        self.calls.append(key)
        return FakeResponse(self.routes[key])


ROUTES = {
    "https://nextrun.fr/api/events/defi-swimrun-de-lancieux/editions/2026/results": _fixture("edition"),
    f"https://nextrun.fr/api/races/{DUO}/results/rows?page=1": _fixture("xs_duo"),
    f"https://nextrun.fr/api/races/{SOLO}/results/rows?page=1": _fixture("xs_solo_p1"),
    f"https://nextrun.fr/api/races/{SOLO}/results/rows?page=2": _fixture("xs_solo_p2"),
}


@pytest.fixture
def client(monkeypatch):
    fake = FakeClient(ROUTES)
    monkeypatch.setattr(nextrun.http, "client", lambda **kwargs: fake)
    return fake


def test_registry_routes_nextrun_urls():
    assert registry.detect_provider(URL) == "nextrun"
    assert registry.detect_provider("https://www.nextrun.fr/events/x/editions/2026/results") == "nextrun"
    assert registry.detect_provider("https://evil-nextrun.fr/events/x/editions/2026/results") == ""


def test_url_without_edition_is_rejected():
    with pytest.raises(ValueError, match="nextrun"):
        nextrun.scrape_event_all("https://nextrun.fr/events/defi-swimrun-de-lancieux")


def test_imports_every_published_race_and_skips_unpublished(client):
    results = nextrun.scrape_event_all(URL)

    assert len(results) == 6 + 4
    assert not any(KIDS in call for call in client.calls)
    names = {r.event_name for r in results}
    assert names == {
        "Défi-Swimrun de Lancieux - SwimRun XS - Duo",
        "Défi-Swimrun de Lancieux - SwimRun XS - Solo",
    }
    assert {r.event_type for r in results} == {"swimrun"}
    # 22/08 à Paris : la source publie l'heure en UTC.
    assert {r.event_date for r in results} == {date(2026, 8, 22)}
    assert all(r.provider == "nextrun" and r.source_url == URL for r in results)


def test_pagination_follows_pages_until_total(client):
    results = nextrun.scrape_event_all(URL)

    solo = [r for r in results if r.event_name.endswith("Solo")]
    assert [r.rank_overall for r in solo] == [1, 2, 19, 51]
    assert f"https://nextrun.fr/api/races/{SOLO}/results/rows?page=3" not in client.calls


def test_duo_keeps_one_row_per_teammate(client):
    duo = [r for r in nextrun.scrape_event_all(URL) if r.event_name.endswith("Duo")]

    first, second = duo[0], duo[1]
    assert (first.athlete_name, first.athlete_firstname) == ("GUICHETEAU", "Romain")
    assert (second.athlete_name, second.athlete_firstname) == ("POIGNONEC", "Alan")
    assert (first.bib_number, second.bib_number) == ("336", "335")
    assert (first.rank_overall, second.rank_overall) == (1, 2)
    assert (first.total_time, second.total_time) == ("00:37:54", "00:37:55")
    assert all(r.is_relay for r in duo)
    assert first.raw_data["team_name"] == "Power natation "
    assert first.club == "MORLAIX TRIATHLON"


def test_row_fields_are_mapped(client):
    solo = [r for r in nextrun.scrape_event_all(URL) if r.event_name.endswith("Solo")]

    winner = solo[0]
    assert winner.gender == "M"
    assert winner.category == "S3"
    assert (winner.rank_gender, winner.rank_category) == (1, 1)
    assert winner.status == STATUS_FINISHER
    assert not winner.is_relay
    # « Licence Expérience » est un type de licence, pas un club.
    assert winner.club == ""
    orphan = solo[2]
    assert orphan.category == ""
    assert orphan.rank_category is None


def test_non_finisher_has_no_rank_nor_time():
    row = {
        **_fixture("xs_solo_p2")["rows"][0],
        "status": "dnf", "official_time_ms": None, "scratch_rank": None,
    }
    result = nextrun._result(row, url=URL, event_name="E", event_date=None, event_type="swimrun",
                             is_relay=False, race_id=SOLO)

    assert result.status == STATUS_DNF
    assert result.total_time == ""
    assert result.rank_overall is None


def test_empty_name_gets_an_anonymous_identity():
    row = {**_fixture("xs_solo_p2")["rows"][0], "first_name": "", "last_name": ""}
    result = nextrun._result(row, url=URL, event_name="E", event_date=None, event_type="swimrun",
                             is_relay=False, race_id=SOLO)

    assert result.athlete_name.startswith("Anonyme")
