"""Public page settings of the claimed athlete over HTTP (#1692)."""
from datetime import date

import pytest

from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation, ParticipationTeammate
from app.models.user import User
from app.repositories import user_repository

from .test_admin_data_api import _session_etroite

URL = "/api/v1/auth/me/public-page"
DEFAULTS = {
    "hide_best_times": False, "hide_progression": False, "hide_comparison": False,
    "links": [], "pinned_participation_id": None, "shared": False,
}


@pytest.fixture
def lea(client, db_session):
    user = _session_etroite(client, db_session, email="lea@exemple.fr", slug="sans-role")
    athlete = Athlete(nom="Martin", prenom="Léa")
    other = Athlete(nom="Durand", prenom="Paul")
    db_session.add_all([athlete, other])
    db_session.flush()
    db_session.get(User, user.id).athlete_id = athlete.id
    course = Course(name="Tri de Nantes", event_date=date(2026, 6, 7), event_type="triathlon-m", is_relay=False)
    db_session.add(course)
    db_session.flush()
    mine = Participation(course_id=course.id, athlete_id=athlete.id, total_time="2:30:00")
    his = Participation(course_id=course.id, athlete_id=other.id, total_time="2:10:00")
    pending = Participation(course_id=course.id, athlete_id=athlete.id, total_time="2:40:00", is_pending_validation=True)
    rejected = Participation(
        course_id=course.id, athlete_id=athlete.id, total_time="2:50:00", is_pending_validation=True, is_rejected=True
    )
    relay_course = Course(name="Relais de Vertou", event_date=date(2026, 5, 3), event_type="triathlon-s", is_relay=True)
    db_session.add_all([mine, his, pending, rejected, relay_course])
    db_session.flush()
    relay = Participation(course_id=relay_course.id, athlete_id=other.id, total_time="1:20:00", is_relay=True)
    db_session.add(relay)
    db_session.flush()
    db_session.add(ParticipationTeammate(participation_id=relay.id, athlete_id=athlete.id, position=1))
    db_session.commit()
    return {
        "user": user, "athlete_id": athlete.id, "mine": mine.id, "his": his.id, "pending": pending.id,
        "rejected": rejected.id, "relay": relay.id,
    }


def test_defaults_without_row(client, lea):
    assert client.get(URL).json() == DEFAULTS


def test_put_round_trip(client, lea):
    body = {
        "hide_best_times": True, "hide_progression": False, "hide_comparison": True,
        "links": ["https://www.strava.com/athletes/1"], "pinned_participation_id": lea["mine"],
    }
    response = client.put(URL, json=body)
    assert response.status_code == 200
    assert response.json() == {**body, "shared": False}
    assert client.get(URL).json() == {**body, "shared": False}


@pytest.mark.parametrize("links", [
    ["https://strava.com/a", "https://strava.com/b", "https://strava.com/c", "https://strava.com/d"],
    ["https://strava.com/a", "https://strava.com/a"],
    ["http://strava.com/a"],
    ["https://strava.com.evil.example/a"],
])
def test_bad_links_are_refused_and_not_stored(client, lea, links):
    assert client.put(URL, json={"links": links}).status_code == 422
    assert client.get(URL).json() == DEFAULTS


@pytest.mark.parametrize("pin", ["his", "pending", "rejected"])
def test_pin_must_be_a_validated_result_of_my_fiche(client, lea, pin):
    response = client.put(URL, json={"pinned_participation_id": lea[pin]})
    assert response.status_code == 422
    assert client.get(URL).json() == DEFAULTS


def test_unlinked_account_gets_409(client, db_session):
    _session_etroite(client, db_session, email="bare@exemple.fr", slug="bare")
    assert client.put(URL, json={}).status_code == 409


def test_anonymous_gets_401(client):
    client.cookies.clear()
    assert client.get(URL).status_code == 401
    assert client.put(URL, json={}).status_code == 401


def test_shared_when_a_second_account_is_linked(client, db_session, lea):
    second = user_repository.create(db_session, email="bis@exemple.fr")
    second.athlete_id = lea["athlete_id"]
    db_session.commit()
    assert client.get(URL).json()["shared"] is True


def test_pin_accepts_a_relay_where_i_am_a_teammate(client, lea):
    response = client.put(URL, json={"pinned_participation_id": lea["relay"]})
    assert (response.status_code, response.json()["pinned_participation_id"]) == (200, lea["relay"])


@pytest.mark.parametrize("leave", ["reassigned", "pending"])
def test_stale_pin_reads_as_none_and_does_not_block_a_later_save(client, db_session, lea, leave):
    assert client.put(URL, json={"pinned_participation_id": lea["mine"]}).status_code == 200
    mine = db_session.get(Participation, lea["mine"])
    if leave == "reassigned":
        mine.athlete_id = db_session.get(Participation, lea["his"]).athlete_id
    else:
        mine.is_pending_validation = True
    db_session.commit()

    current = client.get(URL).json()
    assert current["pinned_participation_id"] is None
    assert client.put(URL, json={**current, "hide_progression": True}).status_code == 200
