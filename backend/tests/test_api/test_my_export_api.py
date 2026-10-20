"""Export of the session account's data over HTTP (#1674): its own data only, never a secret."""
import json
from datetime import date

import pytest

from app.models.athlete import Athlete
from app.models.athlete_claim import AthleteClaim
from app.models.course import Course
from app.models.identity import Identity
from app.models.participation import Participation
from app.models.result_claim import ResultClaim
from app.models.season_goal import SeasonGoal
from app.models.user import User
from app.models.volunteer_action import VolunteerAction

from .test_admin_data_api import _session_etroite

URL = "/api/v1/auth/me/export"


@pytest.fixture
def two_accounts(client, db_session):
    other = _session_etroite(client, db_session, email="autre@exemple.fr", slug="autre")
    mine = _session_etroite(client, db_session, email="moi@exemple.fr", slug="moi")
    lea = Athlete(nom="Martin", prenom="Léa", gender="F", birth_date=date(1990, 5, 1))
    paul = Athlete(nom="Durand", prenom="Paul")
    db_session.add_all([lea, paul])
    db_session.flush()
    course = Course(name="Tri de Nantes", event_date=date(2026, 6, 7), event_type="triathlon-m", is_relay=False)
    db_session.add(course)
    db_session.flush()
    my_result = Participation(course_id=course.id, athlete_id=lea.id, total_time="2:30:00", status="finisher")
    pending = Participation(course_id=course.id, athlete_id=lea.id, total_time="2:40:00", is_pending_validation=True)
    his_result = Participation(course_id=course.id, athlete_id=paul.id, total_time="2:10:00", status="finisher")
    db_session.add_all([my_result, pending, his_result])
    db_session.flush()
    db_session.get(User, mine.id).athlete_id = lea.id
    db_session.get(User, other.id).athlete_id = paul.id
    db_session.add_all([
        Identity(user_id=mine.id, provider="github", subject="42", email="moi@exemple.fr", secret_hash="h"),
        Identity(user_id=other.id, provider="github", subject="43", email="autre@exemple.fr"),
        AthleteClaim(user_id=other.id, athlete_id=lea.id, status="pending"),
        ResultClaim(user_id=mine.id, participation_id=his_result.id, status="rejected"),
        ResultClaim(user_id=other.id, participation_id=my_result.id, status="pending"),
        SeasonGoal(user_id=mine.id, season=2025, kind="count", target=5),
        SeasonGoal(user_id=other.id, season=2026, kind="count", target=9),
        VolunteerAction(athlete_id=lea.id, season=2026, title="Buvette", declared_by_user_id=other.id),
        VolunteerAction(athlete_id=paul.id, season=2026, title="Balisage", declared_by_user_id=mine.id),
        VolunteerAction(athlete_id=paul.id, season=2026, title="Chrono", declared_by_user_id=other.id),
    ])
    db_session.commit()
    return mine, lea, my_result, his_result


def test_export_requires_session(client):
    client.cookies.clear()

    assert client.get(URL).status_code == 401


def test_export_is_a_json_attachment(client, db_session):
    _session_etroite(client, db_session, email="moi@exemple.fr", slug="moi")

    response = client.get(URL)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["content-disposition"] == 'attachment; filename="mes-donnees-tcn.json"'
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["athlete"] is None
    assert body["results"] == []


def test_export_holds_only_the_session_accounts_data(client, two_accounts):
    mine, lea, my_result, his_result = two_accounts

    body = client.get(URL).json()

    assert body["account"]["email"] == "moi@exemple.fr"
    assert [i["email"] for i in body["identities"]] == ["moi@exemple.fr"]
    assert body["athlete"] == {
        "nom": "Martin", "prenom": "Léa", "gender": "F", "birth_date": "1990-05-01", "club": None,
    }
    assert body["athlete_claim"] is None
    assert [(c["participation_id"], c["status"]) for c in body["result_claims"]] == [(his_result.id, "rejected")]
    assert [(g["season"], g["target"]) for g in body["season_goals"]] == [(2025, 5)]
    assert sorted((a["title"], a["for_my_athlete"]) for a in body["volunteer_actions"]) == [
        ("Balisage", False), ("Buvette", True),
    ]
    assert sorted(r["total_time"] for r in body["results"]) == ["2:30:00", "2:40:00"]
    assert {r["course"]["name"] for r in body["results"]} == {"Tri de Nantes"}


def test_export_never_carries_a_secret_or_another_person(client, two_accounts):
    raw = client.get(URL).text

    for leaked in ('"subject"', '"secret_hash"', "autre@exemple.fr", "Durand", "Paul", "Chrono",
                   '"teammates"', '"raw_data"', '"declared_by'):
        assert leaked not in raw
    assert json.loads(raw)["volunteer_actions"][0].keys() == {
        "season", "title", "description", "status", "created_at", "for_my_athlete",
    }
