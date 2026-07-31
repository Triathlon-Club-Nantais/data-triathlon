"""FR-020 — missing secrets never take the public API down."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_without_auth_secrets(monkeypatch, db_session):
    """TestClient with all auth secrets forced to empty."""
    from app.core import config
    from app.core.database import get_db
    from app.main import app

    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_ID", "")
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_SECRET", "")
    monkeypatch.setenv("SESSION_SECRET_KEY", "")
    config.get_settings.cache_clear()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        config.get_settings.cache_clear()


def test_authorize_returns_503_without_client_id(client_without_auth_secrets):
    resp = client_without_auth_secrets.get(
        "/api/v1/auth/github/authorize", follow_redirects=False
    )
    assert resp.status_code == 503
    assert "configur" in resp.json()["detail"].lower()


def test_callback_returns_503_without_secrets(client_without_auth_secrets):
    resp = client_without_auth_secrets.get(
        "/api/v1/auth/github/callback",
        params={"code": "c", "state": "s"},
        follow_redirects=False,
    )
    assert resp.status_code == 503


def test_public_endpoints_still_answer_without_auth_secrets(
    client_without_auth_secrets,
):
    resp = client_without_auth_secrets.get("/api/v1/health")
    assert resp.status_code == 200


def test_me_still_returns_401_without_auth_secrets(client_without_auth_secrets):
    """Without secrets, /me cannot recognize anyone — anonymous means 401."""
    resp = client_without_auth_secrets.get("/api/v1/auth/me")
    assert resp.status_code == 401
