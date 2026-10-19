"""Season goals over HTTP (#1373): private to their owner."""
import pytest

from app.core.season import current_season
from app.models.athlete import Athlete
from app.models.user import User

from .test_admin_data_api import _session_etroite

URL = "/api/v1/auth/me/goals"


@pytest.fixture
def lea(client, db_session):
    user = _session_etroite(client, db_session, email="lea@exemple.fr", slug="sans-role")
    athlete = Athlete(nom="Martin", prenom="Léa")
    db_session.add(athlete)
    db_session.flush()
    db_session.get(User, user.id).athlete_id = athlete.id
    db_session.commit()
    return user


def test_create_list_update_delete(client, lea):
    created = client.post(URL, json={"kind": "time", "event_type": "triathlon-m", "target": 9000})
    assert created.status_code == 201
    goal = created.json()
    assert goal == {
        "id": goal["id"], "season": current_season(), "kind": "time", "event_type": "triathlon-m",
        "target": 9000, "best_time": None, "count": None, "reached": False,
    }

    assert [g["id"] for g in client.get(URL).json()] == [goal["id"]]
    updated = client.put(f"{URL}/{goal['id']}", json={"kind": "count", "event_type": None, "target": 4})
    assert (updated.status_code, updated.json()["count"]) == (200, 0)
    assert client.delete(f"{URL}/{goal['id']}").status_code == 204
    assert client.get(URL).json() == []


def test_another_account_sees_nothing_and_gets_404(client, db_session, lea):
    goal_id = client.post(URL, json={"kind": "count", "event_type": None, "target": 3}).json()["id"]
    _session_etroite(client, db_session, email="autre@exemple.fr", slug="autre")

    assert client.get(URL).json() == []
    assert client.put(f"{URL}/{goal_id}", json={"kind": "count", "event_type": None, "target": 5}).status_code == 404
    assert client.delete(f"{URL}/{goal_id}").status_code == 404


def test_refusals(client, db_session, lea):
    assert client.post(URL, json={"kind": "time", "event_type": None, "target": 9000}).status_code == 422
    assert client.post(URL, json={"kind": "count", "event_type": None, "target": 0}).status_code == 422
    _session_etroite(client, db_session, email="bare@exemple.fr", slug="bare")
    refused = client.post(URL, json={"kind": "count", "event_type": None, "target": 3})
    assert refused.status_code == 409
    assert "C'est moi" in refused.json()["detail"]


def test_routes_require_a_session(client):
    client.cookies.clear()

    assert client.get(URL).status_code == 401
    assert client.post(URL, json={"kind": "count", "event_type": None, "target": 3}).status_code == 401
    assert client.put(f"{URL}/1", json={"kind": "count", "event_type": None, "target": 3}).status_code == 401
    assert client.delete(f"{URL}/1").status_code == 401
