"""#1359 : sans accord à la mesure détaillée, la connexion ne part pas sous l'identifiant du compte."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.core import analytics
from app.core.analytics import ANALYTICS_CONSENT_COOKIE, ANONYMOUS_DISTINCT_ID
from app.models.user import User
from app.services.auth import state


@pytest.fixture
def posthog(monkeypatch):
    fake = MagicMock()
    monkeypatch.setattr(analytics, "posthog_client", fake)
    return fake


def _login(client):
    from app.api.v1.auth import state_cookie_name
    from app.core.config import get_settings

    client.get("/api/v1/auth/doublure/authorize", follow_redirects=False)
    charge = state.read(client.cookies[state_cookie_name(get_settings())])
    client.get(f"/api/v1/auth/doublure/callback?code=code-1&state={charge.state}", follow_redirects=False)


def test_login_with_consent_is_tied_to_the_user(client, doublure, db_session, posthog):
    client.cookies.set(ANALYTICS_CONSENT_COOKIE, "granted")

    _login(client)

    user_id = str(db_session.query(User).one().id)
    assert posthog.capture.call_args.kwargs["distinct_id"] == user_id
    posthog.set.assert_called_once()
    assert posthog.set.call_args.kwargs["distinct_id"] == user_id


@pytest.mark.parametrize("cookie", [None, "denied", "pending"])
def test_login_without_consent_stays_anonymous(client, doublure, posthog, cookie):
    if cookie:
        client.cookies.set(ANALYTICS_CONSENT_COOKIE, cookie)

    _login(client)

    assert posthog.capture.call_args.kwargs["event"] == "user_logged_in"
    assert posthog.capture.call_args.kwargs["distinct_id"] == ANONYMOUS_DISTINCT_ID
    posthog.set.assert_not_called()


def test_capture_outside_a_request_stays_anonymous(posthog):
    """Hors requête (tâche de fond, CLI), aucun accord n'est connu."""
    analytics.capture_event("some_event", distinct_id="42")
    analytics.set_person_properties("42", {"is_staff": True})

    assert posthog.capture.call_args.kwargs["distinct_id"] == ANONYMOUS_DISTINCT_ID
    posthog.set.assert_not_called()


def test_the_frontend_writes_the_cookie_the_backend_reads():
    constants = Path(__file__).resolve().parents[3] / "frontend" / "lib" / "constants.ts"
    assert f'"{ANALYTICS_CONSENT_COOKIE}"' in constants.read_text(encoding="utf-8")
