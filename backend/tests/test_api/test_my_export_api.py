"""Export of the session account's data over HTTP (#1674): its own data only, never a secret."""
import json
from datetime import date

import pytest

from app.models.athlete import Athlete
from app.models.athlete_claim import AthleteClaim
from app.models.course import Course
from app.models.identity import Identity
from app.models.participation import Participation, ParticipationTeammate
from app.models.public_page_settings import PublicPageSettings
from app.models.result_claim import ResultClaim
from app.models.season_goal import SeasonGoal
from app.models.user import User
from app.models.user_feedback import UserFeedback
from app.models.volunteer_action import VolunteerAction
from app.repositories import user_repository

from .test_admin_data_api import _session_etroite

URL = "/api/v1/auth/me/export"


@pytest.fixture
def two_accounts(client, db_session):
    other = _session_etroite(client, db_session, email="autre@exemple.fr", slug="autre")
    mine = _session_etroite(client, db_session, email="moi@exemple.fr", slug="moi")
    lea = Athlete(nom="Martin", prenom="Léa", gender="F", birth_date=date(1990, 5, 1))
    paul = Athlete(nom="Durand", prenom="Paul")
    zoe = Athlete(nom="Bernard", prenom="Zoé")
    db_session.add_all([lea, paul, zoe])
    db_session.flush()
    course = Course(name="Tri de Nantes", event_date=date(2026, 6, 7), event_type="triathlon-m", is_relay=False)
    relay = Course(name="Relais de Vertou", event_date=date(2026, 5, 3), event_type="triathlon-s", is_relay=True)
    db_session.add_all([course, relay])
    db_session.flush()
    # Léa court en équipière d'un relais porté par Zoé : le nom de Zoé ne doit pas sortir.
    relay_result = Participation(course_id=relay.id, athlete_id=zoe.id, total_time="1:20:00", is_relay=True)
    db_session.add(relay_result)
    db_session.flush()
    db_session.add_all([
        ParticipationTeammate(participation_id=relay_result.id, athlete_id=zoe.id, position=0),
        ParticipationTeammate(participation_id=relay_result.id, athlete_id=lea.id, position=1),
    ])
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
        UserFeedback(user_id=mine.id, type="bug", title="Temps faux", body="Mon temps", page_url="/athletes/1",
                     ip_address="203.0.113.7", user_agent="Firefox", github_url="https://github.com/x/1"),
        UserFeedback(user_id=other.id, type="idee", title="Idée d'autrui", body="b"),
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
    assert body["result_claims"] == [{
        "participation_id": his_result.id, "status": "rejected", "created_at": body["result_claims"][0]["created_at"],
        "course_name": "Tri de Nantes", "event_date": "2026-06-07", "total_time": "2:10:00",
    }]
    assert [(g["season"], g["target"]) for g in body["season_goals"]] == [(2025, 5)]
    assert sorted((a["title"], a["for_my_athlete"]) for a in body["volunteer_actions"]) == [
        ("Balisage", False), ("Buvette", True),
    ]
    assert sorted(r["total_time"] for r in body["results"]) == ["1:20:00", "2:30:00", "2:40:00"]
    assert {r["course"]["name"] for r in body["results"]} == {"Tri de Nantes", "Relais de Vertou"}
    assert body["feedback"] == [{
        "type": "bug", "title": "Temps faux", "body": "Mon temps", "page_url": "/athletes/1", "status": "nouveau",
        "created_at": body["feedback"][0]["created_at"],
    }]


def test_export_never_carries_a_secret_or_another_person(client, two_accounts):
    raw = client.get(URL).text

    for leaked in ('"subject"', '"secret_hash"', "autre@exemple.fr", "Durand", "Paul", "Chrono", "Bernard", "Zoé",
                   '"teammates"', '"raw_data"', '"declared_by', "203.0.113.7", "Firefox", "github.com", "autrui"):
        assert leaked not in raw
    assert json.loads(raw)["volunteer_actions"][0].keys() == {
        "season", "title", "description", "status", "created_at", "for_my_athlete",
    }


def test_unlinked_account_exports_its_declarations_for_others(client, db_session):
    mine = _session_etroite(client, db_session, email="moi@exemple.fr", slug="moi")
    paul = Athlete(nom="Durand", prenom="Paul")
    db_session.add(paul)
    db_session.flush()
    db_session.add_all([
        VolunteerAction(athlete_id=paul.id, season=2026, title="Balisage", declared_by_user_id=mine.id),
        VolunteerAction(athlete_id=paul.id, season=2026, title="Chrono"),
    ])
    db_session.commit()

    actions = client.get(URL).json()["volunteer_actions"]

    assert [(a["title"], a["for_my_athlete"]) for a in actions] == [("Balisage", False)]


#: Tables owned by the account that the export leaves out on purpose: sessions are
#: technical, roles and groups are the club's organisation rather than the member's data.
EXCLUDED_OWNED_TABLES = {"user_sessions", "user_roles", "user_groups"}
EXPORTED_OWNED_TABLES = {
    "identities": "identities", "athlete_claims": "athlete_claim", "member_requests": "member_request",
    "season_goals": "season_goals", "result_claims": "result_claims", "public_page_settings": "public_page",
}


def test_every_owned_table_is_exported_or_explicitly_excluded(client, db_session):
    _session_etroite(client, db_session, email="moi@exemple.fr", slug="moi")

    body = client.get(URL).json()

    assert user_repository._OWNED_TABLES == EXCLUDED_OWNED_TABLES | EXPORTED_OWNED_TABLES.keys()
    assert set(EXPORTED_OWNED_TABLES.values()) <= body.keys()


def test_export_holds_the_public_page_settings(client, db_session):
    me = _session_etroite(client, db_session, email="moi@exemple.fr", slug="moi")
    assert client.get(URL).json()["public_page"] is None

    db_session.add(PublicPageSettings(user_id=me.id, hide_comparison=True, links=["https://strava.com/a"]))
    db_session.commit()

    assert client.get(URL).json()["public_page"] == {
        "hide_best_times": False, "hide_progression": False, "hide_comparison": True,
        "links": ["https://strava.com/a"], "pinned_participation_id": None,
    }


def test_export_succeeds_for_a_race_goal_without_target_time(client, db_session):
    me = _session_etroite(client, db_session, email="moi@exemple.fr", slug="moi")
    db_session.add(SeasonGoal(user_id=me.id, season=2026, kind="race", target=None, race_name="Tri", race_date=date(2027, 5, 1)))
    db_session.commit()

    response = client.get(URL)

    assert response.status_code == 200
    assert [(g["target"], g["public"]) for g in response.json()["season_goals"]] == [(None, False)]
