"""Season goals over HTTP (#1373): private to their owner."""
from datetime import date, datetime

import pytest

from app.core import season
from app.core.season import current_season
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.user import User
from app.schemas.season_goal import SeasonGoalWrite
from app.services import season_goals

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
        "course_id": None, "race_name": None, "race_date": None, "major": False, "outcome": "upcoming",
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


@pytest.fixture
def october_2026(monkeypatch):
    monkeypatch.setattr(season, "utcnow", lambda: datetime(2026, 10, 15, 12, 0, 0))


def _race(**fields):
    return {"kind": "race", **fields}


def test_create_known_course_race_goal(client, db_session, lea, october_2026):
    course = Course(name="Triathlon de Nantes", event_date=date(2027, 5, 10), event_type="triathlon-m")
    db_session.add(course)
    db_session.commit()

    created = client.post(URL, json=_race(course_id=course.id))

    assert created.status_code == 201
    goal = created.json()
    assert (goal["kind"], goal["course_id"], goal["race_name"], goal["race_date"]) == (
        "race", course.id, "Triathlon de Nantes", "2027-05-10"
    )
    assert goal["target"] is None
    assert goal["event_type"] == "triathlon-m"
    assert goal["season"] == 2026


def test_create_free_race_goal(client, lea, october_2026):
    created = client.post(
        URL, json=_race(race_name="Triathlon du lac", race_date="2027-06-01", event_type="triathlon-m", target=9000)
    )

    assert created.status_code == 201
    assert (created.json()["course_id"], created.json()["target"]) == (None, 9000)


def test_free_race_goal_without_date_is_422(client, lea, october_2026):
    assert client.post(URL, json=_race(race_name="Triathlon du lac")).status_code == 422


def test_race_goal_outside_current_season_is_422(client, lea, october_2026):
    refused = client.post(URL, json=_race(race_name="Trop tard", race_date="2027-09-01"))

    assert refused.status_code == 422
    assert refused.json()["detail"] == "L'épreuve cible doit tomber dans la saison en cours."


def test_race_target_without_event_type_is_422(client, lea, october_2026):
    refused = client.post(URL, json=_race(race_name="Triathlon du lac", race_date="2027-06-01", target=9000))

    assert refused.status_code == 422


def test_unknown_course_is_422(client, lea, october_2026):
    assert client.post(URL, json=_race(course_id=999_999)).status_code == 422


def test_only_one_major_goal_per_season(client, lea, october_2026):
    first = client.post(URL, json={"kind": "count", "target": 3, "major": True}).json()
    second = client.post(URL, json={"kind": "count", "target": 4}).json()

    assert [g["major"] for g in client.get(URL).json()] == [True, False]
    client.put(f"{URL}/{second['id']}", json={"kind": "count", "target": 4, "major": True})
    assert {g["id"]: g["major"] for g in client.get(URL).json()} == {first["id"]: False, second["id"]: True}
    third = client.post(URL, json={"kind": "count", "target": 5, "major": True})
    assert third.status_code == 201
    assert [g["id"] for g in client.get(URL).json() if g["major"]] == [third.json()["id"]]


def test_change_kind_clears_race_fields(client, lea, october_2026):
    goal = client.post(URL, json=_race(race_name="Triathlon du lac", race_date="2027-06-01")).json()

    updated = client.put(f"{URL}/{goal['id']}", json={"kind": "count", "target": 2}).json()

    assert (updated["course_id"], updated["race_name"], updated["race_date"]) == (None, None, None)


def test_race_goals_count_in_limit(client, lea, october_2026):
    client.post(URL, json=_race(race_name="Triathlon du lac", race_date="2027-06-01"))
    for _ in range(9):
        assert client.post(URL, json={"kind": "count", "target": 2}).status_code == 201

    assert client.post(URL, json={"kind": "count", "target": 2}).status_code == 409


def test_deleted_course_keeps_goal(db_session_fk, october_2026):
    from app.models.athlete import Athlete
    from app.models.season_goal import SeasonGoal
    from app.repositories import course_repository, user_repository

    db = db_session_fk
    athlete = Athlete(nom="Martin", prenom="Léa")
    db.add(athlete)
    course = Course(name="Triathlon de Nantes", event_date=date(2027, 5, 10), event_type="triathlon-m")
    db.add(course)
    user = user_repository.create(db, email="lea@exemple.fr")
    db.flush()
    user.athlete_id = athlete.id
    goal = season_goals.create(db, user, SeasonGoalWrite(kind="race", course_id=course.id))
    db.commit()

    course_repository.delete(db, course)
    db.commit()
    db.expire_all()

    kept = db.get(SeasonGoal, goal.id)
    assert (kept.course_id, kept.race_name) == (None, "Triathlon de Nantes")
