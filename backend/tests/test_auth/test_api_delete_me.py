"""`DELETE /auth/me`: a signed-in user deletes his own account (#1326, contracts/auth-delete-me.md)."""
import pytest

from app.api.v1.auth import LOGGED_IN_COOKIE, session_cookie_name
from app.core.config import get_settings
from app.models.athlete import Athlete
from app.models.season_validation import SeasonValidation
from app.models.user import SYSTEM_USER_EMAIL, User
from app.models.user_session import UserSession
from app.repositories import user_repository
from app.services.auth import session


@pytest.fixture(autouse=True)
def system_user(db_session):
    user = user_repository.create(db_session, email=SYSTEM_USER_EMAIL)
    db_session.commit()
    return user


def _signed_in(client, db_session) -> User:
    user = user_repository.create(db_session, email="alix@exemple.fr", display_name="Alix")
    session.open_for(db_session, user)
    token = session.open_for(db_session, user)
    db_session.commit()
    client.cookies.set(session_cookie_name(get_settings()), token)
    return user


def test_delete_me_removes_the_account_and_clears_the_cookies(client, db_session):
    user = _signed_in(client, db_session)
    user_id = user.id

    response = client.delete("/api/v1/auth/me")

    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["cache-control"] == "no-store"
    set_cookie = response.headers.get_list("set-cookie")
    assert any(c.startswith(f"{session_cookie_name(get_settings())}=") and "Max-Age=0" in c for c in set_cookie)
    assert any(c.startswith(f"{LOGGED_IN_COOKIE}=") and "Max-Age=0" in c for c in set_cookie)
    db_session.expire_all()
    assert db_session.get(User, user_id) is None
    assert db_session.query(UserSession).filter_by(user_id=user_id).count() == 0


def test_the_session_is_worthless_after_deletion(client, db_session):
    _signed_in(client, db_session)
    token = client.cookies.get(session_cookie_name(get_settings()))
    client.delete("/api/v1/auth/me")

    client.cookies.set(session_cookie_name(get_settings()), token)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_delete_me_is_401_when_anonymous(client):
    response = client.delete("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"


def test_delete_me_is_409_when_a_required_reference_cites_the_account(client, db_session):
    user = _signed_in(client, db_session)
    athlete = Athlete(nom="Martin", prenom="Alix")
    db_session.add(athlete)
    db_session.flush()
    db_session.add(SeasonValidation(athlete_id=athlete.id, season=2026, validated_by_user_id=user.id))
    db_session.commit()

    response = client.delete("/api/v1/auth/me")

    assert response.status_code == 409
    assert "Contactez le club" in response.json()["detail"]
    db_session.expire_all()
    assert db_session.get(User, user.id) is not None


def test_delete_me_is_409_for_the_last_administrator(client, db_session, ouvrir_session):
    user = ouvrir_session(superutilisateur=True)

    response = client.delete("/api/v1/auth/me")

    assert response.status_code == 409
    assert "administrateur" in response.json()["detail"]
    db_session.expire_all()
    assert db_session.get(User, user.id) is not None
