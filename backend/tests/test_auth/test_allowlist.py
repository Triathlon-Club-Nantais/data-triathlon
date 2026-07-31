"""B2 — GITHUB_ALLOWED_LOGINS gates who can open a session."""
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient


def _fetch_state(client) -> str:
    resp = client.get("/api/v1/auth/github/authorize", follow_redirects=False)
    return parse_qs(urlparse(resp.headers["location"]).query)["state"][0]


@pytest.fixture
def auth_settings_with_allowlist(monkeypatch):
    """auth settings with GITHUB_ALLOWED_LOGINS restricted to a single login."""
    from app.core import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv(
        "GITHUB_OAUTH_REDIRECT_URL",
        "http://testserver/api/v1/auth/github/callback",
    )
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-session-secret-must-be-32-chars-min")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    monkeypatch.setenv("FRONTEND_POST_LOGIN_URL", "http://frontend.local/admin")
    monkeypatch.setenv("GITHUB_ALLOWED_LOGINS", "mherrmann,tjarrier")

    settings = config.get_settings()
    yield settings
    config.get_settings.cache_clear()


@pytest.fixture
def client_with_allowlist(db_session, auth_settings_with_allowlist, fake_http):
    from app.api.v1 import auth as auth_router
    from app.core.database import get_db
    from app.main import app

    def _override_get_db():
        yield db_session

    def _override_client_factory():
        return fake_http

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[auth_router.get_http_client] = _override_client_factory
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def test_login_in_allowlist_is_accepted(
    client_with_allowlist, db_session, fake_http, github_user_payload
):
    from app.models import User

    state = _fetch_state(client_with_allowlist)
    fake_http.queue_token({"access_token": "gho_test"})
    # allowed login
    fake_http.queue_user({**github_user_payload, "login": "mherrmann"})

    resp = client_with_allowlist.get(
        "/api/v1/auth/github/callback",
        params={"code": "c", "state": state},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert db_session.query(User).count() == 1


def test_login_not_in_allowlist_is_rejected(
    client_with_allowlist, db_session, fake_http, github_user_payload
):
    from app.models import User

    state = _fetch_state(client_with_allowlist)
    fake_http.queue_token({"access_token": "gho_test"})
    # not in allowlist
    fake_http.queue_user({**github_user_payload, "login": "stranger"})

    resp = client_with_allowlist.get(
        "/api/v1/auth/github/callback",
        params={"code": "c", "state": state},
        follow_redirects=False,
    )
    assert resp.status_code == 403
    assert "autoris" in resp.json()["detail"].lower()
    # No User row was created — the table stays clean.
    assert db_session.query(User).count() == 0
    # No session cookie posed.
    assert "tcn_session" not in resp.cookies


def test_allowlist_is_case_insensitive(
    client_with_allowlist, fake_http, github_user_payload
):
    state = _fetch_state(client_with_allowlist)
    fake_http.queue_token({"access_token": "gho_test"})
    # capitalized version of an allowed login
    fake_http.queue_user({**github_user_payload, "login": "MHerrmann"})

    resp = client_with_allowlist.get(
        "/api/v1/auth/github/callback",
        params={"code": "c", "state": state},
        follow_redirects=False,
    )
    assert resp.status_code == 302


def test_empty_allowlist_accepts_every_login(
    client_with_auth, fake_http, github_user_payload
):
    """The default (`auth_settings` fixture) has no allowlist — behavior unchanged."""
    state = _fetch_state(client_with_auth)
    fake_http.queue_token({"access_token": "gho_test"})
    fake_http.queue_user({**github_user_payload, "login": "any-random-user"})

    resp = client_with_auth.get(
        "/api/v1/auth/github/callback",
        params={"code": "c", "state": state},
        follow_redirects=False,
    )
    assert resp.status_code == 302
