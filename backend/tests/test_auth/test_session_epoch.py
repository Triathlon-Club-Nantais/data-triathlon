"""B4 — session_epoch enables per-user revocation on logout.

The session cookie carries `{uid, epoch, v}`. `_resolve_session_user` compares
the epoch against `User.session_epoch`; `POST /auth/logout` increments the
user's row so every outstanding cookie is invalidated for that user, without
touching other users' sessions.
"""
from urllib.parse import parse_qs, urlparse

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.deps import current_user
from app.core.database import get_db
from app.repositories import user_repository


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/protected")
    def protected(user=Depends(current_user)):
        return {"id": user.id, "epoch": user.session_epoch}

    return app


def _client(db_session):
    app = _build_app()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def test_cookie_signed_with_stale_epoch_is_rejected(db_session, auth_settings):
    from app.services import auth_service

    user, _ = user_repository.upsert_from_github(
        db_session, github_id="99", github_login="alice", email="a@e.com"
    )
    db_session.commit()

    # cookie signed with epoch 0 while the user is still at epoch 0 → valid
    good_token = auth_service.sign_session(
        auth_settings.session_secret_key, user_id=user.id, epoch=0
    )
    client = _client(db_session)
    client.cookies.set("tcn_session", good_token)
    assert client.get("/protected").status_code == 200

    # bump the epoch on the user row (as logout would)
    user.session_epoch += 1
    db_session.commit()

    # the same cookie now points to a stale epoch → 401
    client.cookies.set("tcn_session", good_token)
    assert client.get("/protected").status_code == 401


def _fetch_state(client) -> str:
    resp = client.get("/api/v1/auth/github/authorize", follow_redirects=False)
    return parse_qs(urlparse(resp.headers["location"]).query)["state"][0]


def _login(client, fake_http, github_user_payload) -> None:
    state = _fetch_state(client)
    fake_http.queue_token({"access_token": "gho_test"})
    fake_http.queue_user(github_user_payload)
    resp = client.get(
        "/api/v1/auth/github/callback",
        params={"code": "c", "state": state},
        follow_redirects=False,
    )
    assert resp.status_code == 302


def test_logout_increments_session_epoch_and_invalidates_the_cookie(
    client_with_auth, db_session, fake_http, github_user_payload
):
    from app.models import User

    _login(client_with_auth, fake_http, github_user_payload)

    user_before = db_session.query(User).one()
    epoch_before = user_before.session_epoch

    # Snapshot the cookie so we can replay it after logout.
    cookie = client_with_auth.cookies.get("tcn_session")
    assert cookie is not None

    # /me is fine while the cookie matches the DB epoch.
    assert client_with_auth.get("/api/v1/auth/me").status_code == 200

    resp = client_with_auth.post("/api/v1/auth/logout")
    assert resp.status_code == 204

    db_session.expire_all()
    user_after = db_session.query(User).one()
    assert user_after.session_epoch == epoch_before + 1

    # Replay the pre-logout cookie: now stale → 401.
    client_with_auth.cookies.set("tcn_session", cookie)
    assert client_with_auth.get("/api/v1/auth/me").status_code == 401


def test_logout_is_noop_when_no_session(client_with_auth, db_session):
    """Anonymous logout must not touch the database."""
    from app.models import User

    # No user in DB — logout just clears the cookie.
    assert client_with_auth.post("/api/v1/auth/logout").status_code == 204
    assert db_session.query(User).count() == 0
