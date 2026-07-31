"""Shared fixtures for auth tests (issue #114)."""
import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def github_user_payload() -> dict:
    return json.loads((FIXTURES_DIR / "github_user.json").read_text())


@pytest.fixture
def github_user_emails_payload() -> list[dict]:
    return json.loads((FIXTURES_DIR / "github_user_emails.json").read_text())


@pytest.fixture
def auth_settings(monkeypatch):
    """Return a Settings object with valid auth values, wired into get_settings()."""
    from app.core import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv(
        "GITHUB_OAUTH_REDIRECT_URL",
        "http://testserver/api/v1/auth/github/callback",
    )
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-session-secret")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    monkeypatch.setenv("FRONTEND_POST_LOGIN_URL", "http://frontend.local/admin")

    settings = config.get_settings()
    yield settings
    config.get_settings.cache_clear()


class FakeGithubHttp:
    """A stand-in for httpx.Client used by auth_service.

    Records outbound calls and returns queued responses. Injected into the
    router via a client_factory dependency override.
    """

    def __init__(self):
        self.calls: list[tuple[str, str, dict]] = []
        self._token_response: dict | None = None
        self._user_response: dict | None = None
        self._emails_response: list[dict] | None = None
        self._token_status: int = 200
        self._user_status: int = 200
        self._emails_status: int = 200

    def queue_token(self, payload: dict, status: int = 200):
        self._token_response = payload
        self._token_status = status
        return self

    def queue_user(self, payload: dict, status: int = 200):
        self._user_response = payload
        self._user_status = status
        return self

    def queue_emails(self, payload: list[dict], status: int = 200):
        self._emails_response = payload
        self._emails_status = status
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return None

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return _FakeResponse(self._token_status, self._token_response)

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        if url.endswith("/user/emails"):
            return _FakeResponse(self._emails_status, self._emails_response)
        return _FakeResponse(self._user_status, self._user_response)


class _FakeResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300


@pytest.fixture
def fake_http():
    """Empty FakeGithubHttp — each test queues its own responses."""
    return FakeGithubHttp()


@pytest.fixture
def client_with_auth(db_session, auth_settings, fake_http):
    """TestClient wired with an in-memory DB and a fake GitHub client."""
    from fastapi.testclient import TestClient

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
