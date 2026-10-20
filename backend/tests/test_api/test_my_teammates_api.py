"""Race teammates over HTTP (#1701): club members who raced the same events as me."""
from datetime import date

import pytest

from app.core.identity import identity_hash
from app.models.athlete import Athlete
from app.models.athlete_opposition import AthleteOpposition
from app.models.course import Course
from app.models.participation import Participation
from app.models.user import User

from .test_admin_data_api import _session_etroite

URL = "/api/v1/auth/me/teammates"


def _race(db, athlete, course, club="TCN", status="finisher"):
    db.add(Participation(course_id=course.id, athlete_id=athlete.id, status=status, club=club,
                         total_time="1:00:00"))


@pytest.fixture
def lea(client, db_session):
    user = _session_etroite(client, db_session, email="lea@exemple.fr", slug="sans-role")
    names = ["Martin", "Durand", "Bernard", "Petit", "Roux", "Opposé"]
    athletes = [Athlete(nom=n, prenom="Léa" if n == "Martin" else "Ami") for n in names]
    db_session.add_all(athletes)
    db_session.flush()
    db_session.get(User, user.id).athlete_id = athletes[0].id
    courses = [Course(name=f"Tri {i}", event_date=date(2026 if i < 3 else 2025, 6, 7 + i), event_type="triathlon-m",
                      is_relay=False) for i in range(4)]
    db_session.add_all(courses)
    db_session.flush()
    me, durand, bernard, petit, roux, oppose = athletes
    for course in courses:
        _race(db_session, me, course)
    for course in courses[1:]:
        _race(db_session, durand, course)
    for course in courses[:2]:
        _race(db_session, bernard, course)
        _race(db_session, oppose, course)
    _race(db_session, petit, courses[0])
    _race(db_session, roux, courses[0], club="Autre club")
    db_session.add(AthleteOpposition(identity_hash=identity_hash("Opposé", "Ami"), requested_on=date(2026, 1, 1)))
    db_session.commit()
    return athletes


def test_top_three_by_common_races_club_only_without_oppositions(client, lea):
    response = client.get(URL)

    assert response.status_code == 200
    assert [(t["nom"], t["courses_communes"]) for t in response.json()] == [
        ("Durand", 3), ("Bernard", 2), ("Petit", 1)]
    assert set(response.json()[0]) == {"athlete_id", "prenom", "nom", "courses_communes"}


def test_seasons_filter_narrows_common_races(client, lea):
    assert [(t["nom"], t["courses_communes"]) for t in client.get(URL, params={"seasons": "2024"}).json()] == [
        ("Durand", 1)]


def test_unlinked_account_gets_an_empty_list(client, db_session):
    _session_etroite(client, db_session, email="bare@exemple.fr", slug="bare")

    assert client.get(URL).json() == []


def test_requires_a_session(client):
    client.cookies.clear()

    assert client.get(URL).status_code == 401


def test_dnf_teammate_relay_course_and_non_federal_events_do_not_count(client, db_session, lea):
    me, durand, bernard, petit, *_ = lea
    relay = Course(name="Relais", event_date=date(2026, 6, 20), event_type="triathlon-m", is_relay=True)
    trail = Course(name="Trail", event_date=date(2026, 6, 21), event_type="trail", is_relay=False)
    db_session.add_all([relay, trail])
    db_session.flush()
    for course in (relay, trail):
        _race(db_session, me, course)
        _race(db_session, petit, course)
    _race(db_session, bernard, trail, status="dnf")
    db_session.commit()

    assert [(t["nom"], t["courses_communes"]) for t in client.get(URL).json()] == [
        ("Durand", 3), ("Bernard", 2), ("Petit", 2)]
    federal = client.get(URL, params={"federal_only": "true"}).json()
    assert [(t["nom"], t["courses_communes"]) for t in federal] == [("Durand", 3), ("Bernard", 2), ("Petit", 1)]
    assert all(t["athlete_id"] != me.id for t in federal)
