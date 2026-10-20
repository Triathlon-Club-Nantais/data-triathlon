"""Result claims over HTTP (#1637)."""
from datetime import date

import pytest

from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation
from app.models.user import User
from app.repositories import participation_repository

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


def test_my_result_claims_include_course(client, setup):
    _, _, _, result = setup
    client.post(MINE, json={"participation_id": result.id})

    (claim,) = client.get(MINE).json()
    assert (claim["course_id"], claim["course_name"], claim["event_date"]) == (
        result.course_id, "Tri de Nantes", "2026-06-07")


def test_request_result_claim_returns_course(client, setup):
    _, _, _, result = setup

    claim = client.post(MINE, json={"participation_id": result.id}).json()
    assert (claim["course_id"], claim["course_name"], claim["event_date"]) == (
        result.course_id, "Tri de Nantes", "2026-06-07")


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
    assert (item["participation"]["is_relay"], item["participation"]["teammates"]) == (False, [])
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


def test_a_relay_claim_shows_its_team_and_waits_for_it_to_be_completed(client, db_session, setup):
    """#1739: the queue shows the current team; approval needs the member in it."""
    _, mine, homonym, result = setup
    partner = Athlete(nom="Durand", prenom="Paul")
    db_session.add(partner)
    relay = db_session.get(Participation, result.id)
    relay.is_relay, relay.team_name = True, "Les Dauphins"
    db_session.flush()
    participation_repository.replace_teammates(db_session, relay, [homonym.id, partner.id])
    db_session.commit()
    claim_id = client.post(MINE, json={"participation_id": result.id}).json()["id"]
    _session_etroite(client, db_session, "athlete_claims:review", email="rev@exemple.fr", slug="rev")

    (item,) = client.get(QUEUE).json()
    assert (item["participation"]["is_relay"], item["participation"]["team_name"]) == (True, "Les Dauphins")
    assert [a["id"] for a in item["participation"]["teammates"]] == [homonym.id, partner.id]

    refused = client.post(f"{QUEUE}/{claim_id}/approve")
    assert refused.status_code == 409
    assert "Attribuer aux équipiers" in refused.json()["detail"]
