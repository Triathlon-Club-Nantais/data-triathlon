"""B1 — Cross-domain callback breaks the cookie state.

The prod topology is front-on-Vercel / back-on-Render with the front
proxying `/api/*` to the back. Cookies are attributed by the browser to the
origin that answered — i.e. Vercel. If GitHub is told to call back on
Render, the state cookie stays on the Vercel domain and the callback
receives an empty `tcn_oauth_state` → 400 systematic.

These tests exercise the `request.url_for` branch (the one that runs in
prod), which was previously never covered because `conftest.py` always
forced `GITHUB_OAUTH_REDIRECT_URL`.
"""
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def auth_settings_no_redirect(monkeypatch):
    """Like `auth_settings` but with GITHUB_OAUTH_REDIRECT_URL left empty."""
    from app.core import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_SECRET", "test-client-secret")
    monkeypatch.delenv("GITHUB_OAUTH_REDIRECT_URL", raising=False)
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-session-secret-must-be-32-chars-min")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    monkeypatch.setenv("FRONTEND_POST_LOGIN_URL", "http://frontend.local/admin")

    settings = config.get_settings()
    yield settings
    config.get_settings.cache_clear()


@pytest.fixture
def client_no_redirect(db_session, auth_settings_no_redirect, fake_http):
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
        with TestClient(app, base_url="http://vercel-preview.example") as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def test_redirect_uri_defaults_to_request_origin(client_no_redirect):
    """Without an explicit redirect URL, `request.url_for` builds it from the origin."""
    resp = client_no_redirect.get(
        "/api/v1/auth/github/authorize", follow_redirects=False
    )
    assert resp.status_code == 302

    location = resp.headers["location"]
    qs = parse_qs(urlparse(location).query)
    redirect_uri = qs["redirect_uri"][0]
    # The redirect_uri must be built on the origin the browser saw.
    assert redirect_uri.startswith("http://vercel-preview.example/"), redirect_uri
    assert redirect_uri.endswith("/api/v1/auth/github/callback")


def test_state_cookie_follows_the_origin_of_authorize(client_no_redirect):
    """The state cookie must be attributed to the same domain that will handle callback."""
    resp = client_no_redirect.get(
        "/api/v1/auth/github/authorize", follow_redirects=False
    )
    # The cookie is emitted for the origin `vercel-preview.example`.
    set_cookie = resp.headers.get("set-cookie", "")
    assert "tcn_oauth_state=" in set_cookie
    # Domain attribute is not set → host-only cookie for the responding origin.
    assert "Domain=" not in set_cookie
