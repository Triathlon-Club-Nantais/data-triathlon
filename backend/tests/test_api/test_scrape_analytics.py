"""#1367 : l'import SSE rapporte son issue à PostHog, avec le fournisseur, sans donnée personnelle."""
from unittest.mock import MagicMock

import pytest

from app.core import analytics
from app.core.analytics import ANALYTICS_CONSENT_COOKIE, ANONYMOUS_DISTINCT_ID
from app.services import import_service

URL = "https://www.klikego.com/resultats/x/42?nom=DUPONT"


@pytest.fixture
def posthog(monkeypatch):
    fake = MagicMock()
    monkeypatch.setattr(analytics, "posthog_client", fake)
    return fake


def _stream(client, monkeypatch, *events, raises=None, url=URL):
    def fake_iter_import_event(db, url, settings, **kwargs):
        yield from events
        if raises:
            raise raises

    monkeypatch.setattr(import_service, "iter_import_event", fake_iter_import_event)
    with client.stream("POST", "/api/v1/scrape/event/stream", json={"url": url}) as resp:
        assert resp.status_code == 200
        "".join(resp.iter_text())


def _captures(posthog):
    return [call.kwargs for call in posthog.capture.call_args_list]


DONE = {
    "phase": "done", "imported": 3, "updated": 1, "skipped": 2, "total": 6,
    "courses": [{"id": 1, "name": "Triathlon de Nantes"}],
}


def test_successful_import_emits_event_scraped_once(client, monkeypatch, posthog):
    _stream(client, monkeypatch, {"phase": "scraping"}, {"phase": "saving", "total": 6}, DONE)

    assert _captures(posthog) == [{
        "distinct_id": ANONYMOUS_DISTINCT_ID,
        "event": "event_scraped",
        "properties": {
            "provider": "klikego", "imported": 3, "updated": 1, "skipped": 2, "cached": False,
        },
    }]


def test_cache_hit_is_flagged_as_cached(client, monkeypatch, posthog):
    _stream(client, monkeypatch, {**DONE, "imported": 0, "updated": 0, "skipped": 6, "cached": True})

    assert _captures(posthog)[0]["properties"]["cached"] is True


def test_blocking_route_flags_cache_hits_too(client, monkeypatch, posthog):
    monkeypatch.setattr(import_service, "import_event", lambda *a, **k: {
        "imported": 0, "updated": 0, "skipped": 6, "cached": True, "total": 6, "courses": [],
    })

    client.post("/api/v1/scrape/event", json={"url": URL})

    assert _captures(posthog)[0]["properties"]["cached"] is True


def test_failed_import_emits_event_scrape_failed_with_its_kind(client, monkeypatch, posthog):
    _stream(
        client, monkeypatch, {"phase": "scraping"},
        {"phase": "error", "message": "Erreur lors de l'import : DUPONT", "error_kind": "scraper"},
    )

    assert _captures(posthog) == [{
        "distinct_id": ANONYMOUS_DISTINCT_ID,
        "event": "event_scrape_failed",
        "properties": {"provider": "klikego", "error_kind": "scraper"},
    }]


def test_unexpected_crash_is_reported_as_unexpected(client, monkeypatch, posthog):
    _stream(client, monkeypatch, {"phase": "scraping"}, raises=RuntimeError("boom"))

    assert _captures(posthog) == [{
        "distinct_id": ANONYMOUS_DISTINCT_ID,
        "event": "event_scrape_failed",
        "properties": {"provider": "klikego", "error_kind": "unexpected"},
    }]


def test_unknown_provider_is_reported_as_empty_slug(client, monkeypatch, posthog):
    _stream(
        client, monkeypatch,
        {"phase": "error", "message": "x", "error_kind": "unsupported_provider"},
        url="https://example.org/r?nom=DUPONT",
    )

    assert _captures(posthog)[0]["properties"] == {"provider": "", "error_kind": "unsupported_provider"}


def test_outcome_stays_anonymous_even_with_consent(client, monkeypatch, posthog):
    client.cookies.set(ANALYTICS_CONSENT_COOKIE, "granted")

    _stream(client, monkeypatch, DONE)

    assert _captures(posthog)[0]["distinct_id"] == ANONYMOUS_DISTINCT_ID
