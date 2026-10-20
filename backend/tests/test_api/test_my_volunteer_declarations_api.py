"""Volunteer declarations made by my account over HTTP (#1672): every status, any athlete."""
import pytest

from app.models.athlete import Athlete
from app.models.user import User
from app.models.volunteer_action import VolunteerAction

from .test_admin_data_api import _session_etroite

URL = "/api/v1/auth/me/volunteer-declarations"


@pytest.fixture
def lea(client, db_session):
    user = _session_etroite(client, db_session, email="lea@exemple.fr", slug="sans-role")
    other_user = User(email="paul@exemple.fr", display_name="Paul")
    athlete = Athlete(nom="Martin", prenom="Léa")
    friend = Athlete(nom="Durand", prenom="Paul")
    db_session.add_all([other_user, athlete, friend])
    db_session.flush()
    db_session.get(User, user.id).athlete_id = athlete.id
    db_session.add_all(
        [
            VolunteerAction(athlete_id=athlete.id, season=2026, title="Buvette", status="validee",
                            declared_by_user_id=user.id),
            VolunteerAction(athlete_id=friend.id, season=2026, title="Balisage", status="en_attente",
                            declared_by_user_id=user.id),
            VolunteerAction(athlete_id=athlete.id, season=2026, title="Chrono", status="validee",
                            declared_by_user_id=other_user.id),
            VolunteerAction(athlete_id=athlete.id, season=2026, title="Anonyme", status="refusee"),
        ]
    )
    db_session.commit()
    return user


def test_lists_only_declarations_made_by_my_account(client, lea):
    response = client.get(URL)

    assert response.status_code == 200
    body = response.json()
    assert sorted((d["title"], d["status"], d["athlete_prenom"]) for d in body) == [
        ("Balisage", "en_attente", "Paul"),
        ("Buvette", "validee", "Léa"),
    ]
    assert set(body[0]) == {
        "id", "athlete_id", "athlete_nom", "athlete_prenom", "season",
        "title", "description", "status", "created_at",
    }


def test_account_without_declaration_gets_an_empty_list(client, db_session):
    _session_etroite(client, db_session, email="bare@exemple.fr", slug="bare")

    assert client.get(URL).json() == []


def test_requires_a_session(client):
    client.cookies.clear()

    assert client.get(URL).status_code == 401
