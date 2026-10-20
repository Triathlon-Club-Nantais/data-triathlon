"""My validated volunteer actions over HTTP (#1696): the linked athlete's only."""
import pytest

from app.models.athlete import Athlete
from app.models.user import User
from app.models.volunteer_action import VolunteerAction

from .test_admin_data_api import _session_etroite

URL = "/api/v1/auth/me/volunteer-actions"


def _action(db, athlete, title, status="validee"):
    action = VolunteerAction(athlete_id=athlete.id, season=2026, title=title, status=status)
    db.add(action)
    db.flush()
    return action


@pytest.fixture
def lea(client, db_session):
    user = _session_etroite(client, db_session, email="lea@exemple.fr", slug="sans-role")
    athlete = Athlete(nom="Martin", prenom="Léa")
    autre = Athlete(nom="Durand", prenom="Paul")
    db_session.add_all([athlete, autre])
    db_session.flush()
    db_session.get(User, user.id).athlete_id = athlete.id
    _action(db_session, athlete, "Buvette")
    _action(db_session, athlete, "Balisage", status="en_attente")
    _action(db_session, autre, "Chrono")
    db_session.commit()
    return user


def test_lists_only_my_validated_actions(client, lea):
    response = client.get(URL)

    assert response.status_code == 200
    assert [a["title"] for a in response.json()] == ["Buvette"]
    assert set(response.json()[0]) == {"id", "season", "title", "description", "status", "created_at"}


def test_unlinked_account_gets_an_empty_list(client, db_session):
    _session_etroite(client, db_session, email="bare@exemple.fr", slug="bare")

    assert client.get(URL).json() == []


def test_requires_a_session(client):
    client.cookies.clear()

    assert client.get(URL).status_code == 401
