"""Assertions on Set-Cookie attributes — catches silent regressions.

Before this file, retirer `httponly=True` sur `tcn_session` (rendant la
session lisible en JS) passait inaperçu : aucun test ne vérifiait un seul
attribut de cookie. Les 44 tests d'auth d'origine passaient tous, la
feature était cassée. Cf. review B trou de couverture n°1.
"""
from urllib.parse import parse_qs, urlparse


def _login_and_return_setcookie(client, fake_http, github_user_payload) -> str:
    resp = client.get("/api/v1/auth/github/authorize", follow_redirects=False)
    state = parse_qs(urlparse(resp.headers["location"]).query)["state"][0]

    fake_http.queue_token({"access_token": "gho_test"})
    fake_http.queue_user(github_user_payload)

    cb = client.get(
        "/api/v1/auth/github/callback",
        params={"code": "c", "state": state},
        follow_redirects=False,
    )
    # There may be more than one Set-Cookie; find the tcn_session one.
    for header_name, header_value in cb.headers.raw:
        if header_name.lower() == b"set-cookie" and b"tcn_session=" in header_value:
            return header_value.decode()
    raise AssertionError("no tcn_session Set-Cookie in the callback response")


def test_session_cookie_is_httponly(
    client_with_auth, fake_http, github_user_payload
):
    header = _login_and_return_setcookie(
        client_with_auth, fake_http, github_user_payload
    )
    assert "HttpOnly" in header


def test_session_cookie_uses_samesite_lax(
    client_with_auth, fake_http, github_user_payload
):
    header = _login_and_return_setcookie(
        client_with_auth, fake_http, github_user_payload
    )
    assert "samesite=lax" in header.lower()


def test_session_cookie_is_root_path(
    client_with_auth, fake_http, github_user_payload
):
    header = _login_and_return_setcookie(
        client_with_auth, fake_http, github_user_payload
    )
    # exact `Path=/` (avoid matching `Path=/api/...`)
    assert "; Path=/" in header
    assert "; Path=/api" not in header


def test_session_cookie_has_max_age(
    client_with_auth, fake_http, github_user_payload
):
    header = _login_and_return_setcookie(
        client_with_auth, fake_http, github_user_payload
    )
    assert "Max-Age=" in header


def test_state_cookie_is_httponly_and_path_scoped(client_with_auth):
    resp = client_with_auth.get(
        "/api/v1/auth/github/authorize", follow_redirects=False
    )
    for header_name, header_value in resp.headers.raw:
        if header_name.lower() == b"set-cookie" and b"tcn_oauth_state=" in header_value:
            header = header_value.decode()
            assert "HttpOnly" in header
            assert "samesite=lax" in header.lower()
            # State cookie scoped to /api/v1/auth/github/, not /
            assert "Path=/api/v1/auth/github/" in header
            return
    raise AssertionError("no tcn_oauth_state Set-Cookie in the authorize response")


def test_session_cookie_is_not_secure_when_setting_disabled(
    client_with_auth, fake_http, github_user_payload
):
    """The conftest fixture sets SESSION_COOKIE_SECURE=false → no `Secure` flag."""
    header = _login_and_return_setcookie(
        client_with_auth, fake_http, github_user_payload
    )
    assert "Secure" not in header


def test_inactive_user_receives_401(db_session, auth_settings):
    """Setting is_active=False must invalidate the session (no test covered this)."""
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    from app.api.deps import current_user
    from app.core.database import get_db
    from app.repositories import user_repository
    from app.services import auth_service

    app = FastAPI()

    @app.get("/protected")
    def _protected(user=Depends(current_user)):
        return {"id": user.id}

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    user, _ = user_repository.upsert_from_github(
        db_session, github_id="42", github_login="alice", email="a@e.com"
    )
    user.is_active = False
    db_session.commit()

    token = auth_service.sign_session(
        auth_settings.session_secret_key, user_id=user.id, epoch=user.session_epoch
    )
    client = TestClient(app)
    client.cookies.set("tcn_session", token)
    assert client.get("/protected").status_code == 401
