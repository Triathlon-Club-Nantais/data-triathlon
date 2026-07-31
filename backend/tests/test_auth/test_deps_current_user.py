"""Tests for current_user / current_user_optional dependencies (issue #114)."""
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.deps import current_user, current_user_optional
from app.core.database import get_db
from app.repositories import user_repository


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/protected")
    def protected(user=Depends(current_user)):
        return {"id": user.id, "email": user.email}

    @app.get("/optional")
    def optional(user=Depends(current_user_optional)):
        return {"user_id": user.id if user else None}

    return app


def _client(db_session, auth_settings):
    app = _build_app()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app), app


def test_current_user_returns_401_without_cookie(db_session, auth_settings):
    client, _ = _client(db_session, auth_settings)
    assert client.get("/protected").status_code == 401


def test_current_user_returns_401_with_forged_cookie(db_session, auth_settings):
    client, _ = _client(db_session, auth_settings)
    client.cookies.set("tcn_session", "not-a-valid-token")
    assert client.get("/protected").status_code == 401


def test_current_user_returns_401_when_user_row_is_missing(
    db_session, auth_settings
):
    from app.services import auth_service

    client, _ = _client(db_session, auth_settings)
    token = auth_service.sign_session(auth_settings.session_secret_key, user_id=9999)
    client.cookies.set("tcn_session", token)
    assert client.get("/protected").status_code == 401


def test_current_user_returns_200_with_valid_cookie(db_session, auth_settings):
    from app.services import auth_service

    user, _ = user_repository.upsert_from_github(
        db_session, github_id="99", github_login="alice", email="alice@example.com"
    )
    db_session.commit()

    client, _ = _client(db_session, auth_settings)
    token = auth_service.sign_session(auth_settings.session_secret_key, user_id=user.id)
    client.cookies.set("tcn_session", token)

    resp = client.get("/protected")
    assert resp.status_code == 200
    assert resp.json()["email"] == "alice@example.com"


def test_current_user_optional_returns_none_without_cookie(db_session, auth_settings):
    client, _ = _client(db_session, auth_settings)
    resp = client.get("/optional")
    assert resp.status_code == 200
    assert resp.json() == {"user_id": None}


def test_current_user_optional_returns_user_with_valid_cookie(
    db_session, auth_settings
):
    from app.services import auth_service

    user, _ = user_repository.upsert_from_github(
        db_session, github_id="42", github_login="bob", email="bob@example.com"
    )
    db_session.commit()

    client, _ = _client(db_session, auth_settings)
    token = auth_service.sign_session(auth_settings.session_secret_key, user_id=user.id)
    client.cookies.set("tcn_session", token)

    resp = client.get("/optional")
    assert resp.status_code == 200
    assert resp.json() == {"user_id": user.id}


def test_current_user_optional_returns_none_with_forged_cookie(
    db_session, auth_settings
):
    client, _ = _client(db_session, auth_settings)
    client.cookies.set("tcn_session", "forged")
    resp = client.get("/optional")
    assert resp.status_code == 200
    assert resp.json() == {"user_id": None}


def test_session_signed_by_previous_key_is_rejected_after_rotation(
    db_session, auth_settings, monkeypatch
):
    """FR-012 / edge case — rotating SESSION_SECRET_KEY invalidates in-flight sessions."""
    from app.core import config
    from app.services import auth_service

    user, _ = user_repository.upsert_from_github(
        db_session, github_id="123", github_login="carol", email="c@e.com"
    )
    db_session.commit()

    # cookie signed with the ORIGINAL key
    old_token = auth_service.sign_session(
        auth_settings.session_secret_key, user_id=user.id
    )

    # rotate the key
    monkeypatch.setenv("SESSION_SECRET_KEY", "rotated-key")
    config.get_settings.cache_clear()

    client, _ = _client(db_session, config.get_settings())
    client.cookies.set("tcn_session", old_token)
    assert client.get("/protected").status_code == 401
    config.get_settings.cache_clear()
