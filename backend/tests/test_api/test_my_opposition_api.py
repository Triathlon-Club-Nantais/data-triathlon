"""A linked member opposes publication of their own results (#1673)."""
import pytest

from app.models.admin_action_log import AdminActionLog
from app.models.athlete import Athlete
from app.models.athlete_opposition import AthleteOpposition
from app.models.club_member import LINK_AUTO, SOURCE_FFTRI, ClubMember
from app.models.participation import Participation
from app.models.user import User
from app.repositories import athlete_repository, course_repository, participation_repository
from app.services.opposition_service import club_today

from .test_admin_data_api import _session_etroite

PREVIEW = "/api/v1/auth/me/opposition/preview"
APPLY = "/api/v1/auth/me/opposition"
HOMONYMS_MESSAGE = "Votre nom correspond à plusieurs fiches. Écrivez au club pour exercer votre droit d'opposition."


@pytest.fixture
def course(db_session):
    return course_repository.get_or_create(
        db_session, name="Triathlon de Nantes", event_date=club_today(), event_type="triathlon-m",
        source_url="https://k/nantes", provider="klikego",
    )


def _athlete(db_session, course, nom, prenom, bib):
    athlete = athlete_repository.get_or_create(db_session, nom=nom, prenom=prenom)
    participation_repository.create(
        db_session, course_id=course.id, athlete_id=athlete.id, bib_number=bib, rank_overall=1,
        total_time="2:10:00", status="finisher", club="BLAIN TRI", category="SEM", raw_data={},
    )
    db_session.commit()
    return athlete


@pytest.fixture
def lea(db_session, course):
    return _athlete(db_session, course, "MARTIN", "Léa", "1")


@pytest.fixture
def member(client, db_session, lea):
    user = _session_etroite(client, db_session, email="lea@exemple.fr", slug="sans-role")
    user.athlete_id = lea.id
    db_session.commit()
    return user


def test_preview_counts_the_member_own_results(client, member):
    response = client.post(PREVIEW)

    assert response.status_code == 200
    assert response.json() == {"athletes": 1, "results": 1, "already_opposed": False}


def test_unlinked_member_gets_403(client, db_session):
    _session_etroite(client, db_session, email="sans@exemple.fr", slug="sans-role")

    assert client.post(PREVIEW).status_code == 403
    assert client.post(APPLY).status_code == 403


def test_anonymous_gets_401(client):
    client.cookies.clear()

    assert client.post(PREVIEW).status_code == 401
    assert client.post(APPLY).status_code == 401


def test_apply_anonymises_and_detaches(client, db_session, member, lea):
    athlete_id, user_id = lea.id, member.id

    response = client.post(APPLY)

    assert response.status_code == 204
    assert response.headers["cache-control"] == "no-store"
    db_session.expire_all()
    assert db_session.get(Athlete, athlete_id) is None
    assert db_session.get(User, user_id).athlete_id is None
    assert db_session.query(Participation).one().athlete.nom.startswith("Anonyme")
    opposition = db_session.query(AthleteOpposition).one()
    assert opposition.applied_by_user_id == user_id
    assert opposition.requested_on == club_today()


def test_apply_is_logged_with_the_member_as_author(client, db_session, member):
    client.post(APPLY)

    entry = db_session.query(AdminActionLog).filter_by(action="opposition.apply").one()
    assert entry.user_id == member.id


def test_another_athlete_is_never_touched(client, db_session, course, member):
    other = _athlete(db_session, course, "DURAND", "Paul", "2")
    other_id = other.id

    response = client.post(APPLY, json={"athlete_id": other_id})

    assert response.status_code == 204
    db_session.expire_all()
    assert db_session.get(Athlete, other_id).nom == "DURAND"
    assert db_session.query(Participation).filter_by(athlete_id=other_id).count() == 1


def test_homonyms_are_refused_with_write_to_the_club(client, db_session, course, member, lea):
    athlete_repository.create_homonym(db_session, {"nom": "Martin", "prenom": "Léa"})
    db_session.commit()
    athlete_id = lea.id

    assert client.post(PREVIEW).json()["athletes"] == 2
    response = client.post(APPLY)

    assert response.status_code == 409
    assert response.json()["detail"] == HOMONYMS_MESSAGE
    db_session.expire_all()
    assert db_session.get(Athlete, athlete_id) is not None
    assert db_session.get(User, member.id).athlete_id == athlete_id
    assert db_session.query(AthleteOpposition).count() == 0


def _licence(db_session, athlete_id, season, licence_id):
    db_session.add(ClubMember(
        season=season, licence_id=licence_id, nom="Martin", prenom="Léa",
        athlete_id=athlete_id, link_status=LINK_AUTO, source=SOURCE_FFTRI,
    ))


def test_a_homonym_licence_linked_elsewhere_refuses_and_changes_nothing(client, db_session, course, member, lea):
    other = _athlete(db_session, course, "DURAND", "Paul", "2")
    _licence(db_session, other.id, 2025, "L-other")
    db_session.commit()
    athlete_id = lea.id

    response = client.post(APPLY)

    assert response.status_code == 409
    assert response.json()["detail"] == HOMONYMS_MESSAGE
    db_session.expire_all()
    assert db_session.get(Athlete, athlete_id) is not None
    assert db_session.query(ClubMember).count() == 1
    assert db_session.query(AthleteOpposition).count() == 0


def test_the_member_own_licences_do_not_block_and_are_removed(client, db_session, member, lea):
    _licence(db_session, lea.id, 2025, "L-own-1")
    _licence(db_session, None, 2026, "L-own-2")
    db_session.commit()

    assert client.post(APPLY).status_code == 204
    assert db_session.query(ClubMember).count() == 0
