"""Result claims over HTTP (#1637)."""
from datetime import date

import pytest

from app.api import deps
from app.core.identity import identity_hash
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation, ParticipationTeammate
from app.models.user import User
from app.repositories import opposition_repository, participation_repository

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


TEAM_SEARCH = "/api/v1/auth/me/team-results"


def _team_relay(db_session, *teammates: Athlete) -> Participation:
    team = Athlete(nom="LES MOLLETS D'ACIER", prenom="")
    db_session.add(team)
    db_session.flush()
    course = Course(name="Relais de Nantes", event_date=date(2026, 6, 1), event_type="triathlon-s", is_relay=True)
    db_session.add(course)
    db_session.flush()
    row = Participation(course_id=course.id, athlete_id=team.id, bib_number="7", rank_overall=2,
                        total_time="1:10:00", status="finisher", is_relay=True)
    db_session.add(row)
    db_session.flush()
    for position, teammate in enumerate(teammates):
        db_session.add(ParticipationTeammate(participation_id=row.id, athlete_id=teammate.id, position=position))
    db_session.commit()
    return row


def _athlete(db_session, nom, prenom) -> Athlete:
    athlete = Athlete(nom=nom, prenom=prenom)
    db_session.add(athlete)
    db_session.flush()
    return athlete


def test_search_team_results_returns_hits(client, db_session, setup):
    row = _team_relay(db_session, _athlete(db_session, "DURAND", "Paul"))

    response = client.get(TEAM_SEARCH, params={"q": "mollets d acier"})

    assert response.status_code == 200
    assert response.json() == [{
        "participation_id": row.id,
        "team_name": "LES MOLLETS D'ACIER",
        "course_id": row.course_id,
        "course_name": "Relais de Nantes",
        "event_date": "2026-06-01",
        "rank_overall": 2,
        "total_time": "1:10:00",
        "teammates": ["Paul DURAND"],
    }]


@pytest.mark.parametrize("q", ["", "ab", "x" * 81])
def test_search_needs_three_characters(client, setup, q):
    assert client.get(TEAM_SEARCH, params={"q": q}).status_code == 422


def test_search_without_claimed_athlete_returns_empty(client, db_session):
    _team_relay(db_session)
    _session_etroite(client, db_session, email="nobody@exemple.fr", slug="sans-fiche")

    response = client.get(TEAM_SEARCH, params={"q": "mollets"})

    assert (response.status_code, response.json()) == (200, [])


def test_search_hides_opposed_identities(client, db_session, setup):
    _team_relay(db_session, _athlete(db_session, "DUPONT", "Jean"))
    opposition_repository.create(
        db_session, identity_hash=identity_hash("DUPONT", "Jean"), requested_on=date(2026, 9, 1),
        applied_by_user_id=None,
    )
    db_session.commit()

    assert client.get(TEAM_SEARCH, params={"q": "mollets"}).json() == []


def test_a_found_team_result_is_claimed_through_the_relay_claim(client, db_session, setup):
    _team_relay(db_session)
    (hit,) = client.get(TEAM_SEARCH, params={"q": "mollets"}).json()

    # #1757's POST, unchanged body: the hit's id is all it needs.
    created = client.post(MINE, json={"participation_id": hit["participation_id"]})
    assert created.status_code == 201
    assert created.json()["status"] == "pending"


def test_search_of_blanks_returns_nothing(client, setup):
    assert client.get(TEAM_SEARCH, params={"q": "   "}).json() == []


def test_search_is_rate_limited(client, setup, monkeypatch):
    monkeypatch.setattr(deps, "TEAM_SEARCH_RATE_LIMIT_MAX_PER_WINDOW", 1)
    assert client.get(TEAM_SEARCH, params={"q": "abc"}).status_code == 200
    assert client.get(TEAM_SEARCH, params={"q": "abc"}).status_code == 429
