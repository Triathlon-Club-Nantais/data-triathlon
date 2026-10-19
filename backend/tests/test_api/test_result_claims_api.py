"""Result claims over HTTP (#1637)."""
from datetime import date

import pytest

from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation
from app.models.user import User

from .test_admin_data_api import _session_etroite

MINE = "/api/v1/auth/me/result-claims"
QUEUE = "/api/v1/admin/result-claims"


@pytest.fixture
def setup(client, db_session):
    mine, homonym = Athlete(nom="Martin", prenom="Léa"), Athlete(nom="Martin", prenom="Léa B.")
    db_session.add_all([mine, homonym])
    db_session.flush()
    course = Course(name="Tri de Nantes", event_date=date(2026, 6, 7), event_type="triathlon-m", is_relay=False)
    db_session.add(course)
    db_session.flush()
    result = Participation(course_id=course.id, athlete_id=homonym.id, bib_number="12", total_time="2:30:00",
                           status="finisher")
    db_session.add(result)
    db_session.commit()
    user = _session_etroite(client, db_session, email="lea@exemple.fr", slug="sans-role")
    db_session.get(User, user.id).athlete_id = mine.id
    db_session.commit()
    return user, mine, homonym, result


def test_request_list_cancel(client, setup):
    _, _, _, result = setup

    created = client.post(MINE, json={"participation_id": result.id})
    assert created.status_code == 201
    claim = created.json()
    assert (claim["participation_id"], claim["status"]) == (result.id, "pending")
    assert [c["id"] for c in client.get(MINE).json()] == [claim["id"]]
    assert client.delete(f"{MINE}/{claim['id']}").status_code == 204
    assert client.get(MINE).json() == []


def test_own_result_is_refused(client, db_session, setup):
    _, mine, _, result = setup
    db_session.get(Participation, result.id).athlete_id = mine.id
    db_session.commit()

    assert client.post(MINE, json={"participation_id": result.id}).status_code == 409


def test_the_queue_approves_and_moves_the_result(client, db_session, setup):
    user, mine, homonym, result = setup
    claim_id = client.post(MINE, json={"participation_id": result.id}).json()["id"]
    _session_etroite(client, db_session, "athlete_claims:review", email="rev@exemple.fr", slug="rev")

    assert client.get("/api/v1/admin/badge-counts").json()["claims"] == 1
    (item,) = client.get(QUEUE).json()
    assert item["participation"]["course_name"] == "Tri de Nantes"
    assert item["current_athlete"]["id"] == homonym.id
    assert (item["current_athlete_results"], item["claimant_athlete"]["id"]) == (1, mine.id)

    assert client.post(f"{QUEUE}/{claim_id}/approve").status_code == 204
    db_session.expire_all()
    assert db_session.get(Participation, result.id).athlete_id == mine.id
    assert client.post(f"{QUEUE}/{claim_id}/approve").status_code == 404


def test_the_queue_rejects(client, db_session, setup):
    _, _, homonym, result = setup
    claim_id = client.post(MINE, json={"participation_id": result.id}).json()["id"]
    _session_etroite(client, db_session, "athlete_claims:review", email="rev@exemple.fr", slug="rev")

    assert client.post(f"{QUEUE}/{claim_id}/reject").status_code == 204
    db_session.expire_all()
    assert db_session.get(Participation, result.id).athlete_id == homonym.id


def test_permissions_and_sessions(client, db_session):
    _session_etroite(client, db_session, "member_emails:manage")
    assert client.get(QUEUE).status_code == 403
    assert client.post(f"{QUEUE}/1/approve").status_code == 403
    client.cookies.clear()
    assert client.get(MINE).status_code == 401
    assert client.post(MINE, json={"participation_id": 1}).status_code == 401
