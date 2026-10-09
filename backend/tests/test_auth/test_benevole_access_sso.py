"""SSO bypass of the volunteer password (#1272).

A signed-in user holding `benevole_access:manage` reaches `/benevoles/*`
without the shared-password cookie, and their writes are logged under their
own id. Everyone else keeps the unchanged cookie guard (same 401, never 403).
Spec: `specs/20261009-161930-benevole-sso-bypass/`.
"""
from datetime import date

import pytest

from app.core.permissions import P
from app.models.admin_action_log import AdminActionLog
from app.models.benevole_access_config import BenevoleAccessConfig
from app.models.user import SYSTEM_USER_EMAIL
from app.models.user_role import UserRole
from app.repositories import (
    athlete_repository,
    course_repository,
    participation_repository,
    user_repository,
)
from app.services import benevole_access

PASSWORD = "secret-du-club"
BASE = "/api/v1/benevoles"

READ_ROUTES = [
    "/queue",
    "/queue/count",
    "/queue/history",
    "/rejected",
    "/athletes?name=dupont",
]


@pytest.fixture(autouse=True)
def configured_password(db_session):
    owner = user_repository.create(db_session, email="owner@exemple.fr", display_name="Owner")
    db_session.flush()
    benevole_access.replace_password(db_session, password=PASSWORD, admin_user_id=owner.id)
    db_session.commit()


@pytest.fixture
def system_account(db_session):
    account = user_repository.create(
        db_session, email=SYSTEM_USER_EMAIL, display_name="Bénévoles (accès partagé)"
    )
    db_session.commit()
    return account


@pytest.fixture
def pending_result(db_session):
    course = course_repository.get_or_create(
        db_session, name="Tri SSO", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    athlete = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean", club="TCN")
    row = participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1",
        is_pending_validation=True, total_time="01:00:00",
    )
    db_session.commit()
    return course, athlete, row


@pytest.fixture
def volunteer_cookie(client):
    def _open():
        response = client.post(f"{BASE}/session", json={"password": PASSWORD})
        assert response.status_code == 204

    return _open


def last_log_user_id(db_session) -> int:
    db_session.expire_all()
    return db_session.query(AdminActionLog).order_by(AdminActionLog.id.desc()).first().user_id


# --- US1: holder of the power gets in without the cookie --------------------


@pytest.mark.parametrize("route", READ_ROUTES)
def test_power_holder_reads_without_cookie(client, ouvrir_session, route):
    ouvrir_session(P.BENEVOLE_ACCESS_MANAGE)

    assert client.get(f"{BASE}{route}").status_code == 200


def test_power_holder_validates_without_cookie(
    client, ouvrir_session, pending_result, system_account
):
    _, _, row = pending_result
    ouvrir_session(P.BENEVOLE_ACCESS_MANAGE)

    response = client.post(f"{BASE}/participations/{row.id}/validate")

    assert response.status_code == 200
    assert response.json()["is_pending_validation"] is False


def test_superuser_gets_in_without_cookie(client, ouvrir_session):
    ouvrir_session(superutilisateur=True)

    assert client.get(f"{BASE}/queue").status_code == 200


# --- US2: without the power, nothing changes --------------------------------


def test_signed_in_without_power_gets_the_anonymous_401(client, ouvrir_session):
    anonymous = client.get(f"{BASE}/queue")
    ouvrir_session(P.SITE_ACCESS_MANAGE)

    response = client.get(f"{BASE}/queue")

    assert response.status_code == 401
    assert response.json() == anonymous.json()


def test_signed_in_without_power_still_enters_with_the_cookie(
    client, ouvrir_session, volunteer_cookie
):
    ouvrir_session(P.SITE_ACCESS_MANAGE)
    volunteer_cookie()

    assert client.get(f"{BASE}/queue").status_code == 200


def test_invalid_sso_token_without_cookie_is_401(client):
    from app.api.v1.auth import session_cookie_name
    from app.core.config import get_settings

    client.cookies.set(session_cookie_name(get_settings()), "x" * 43)

    assert client.get(f"{BASE}/queue").status_code == 401


def test_missing_configuration_still_refuses_an_old_cookie(
    client, ouvrir_session, volunteer_cookie, db_session
):
    ouvrir_session(P.SITE_ACCESS_MANAGE)
    volunteer_cookie()
    db_session.query(BenevoleAccessConfig).delete()
    db_session.commit()

    assert client.get(f"{BASE}/queue").status_code == 401


def test_losing_the_power_closes_access_on_the_next_call(client, ouvrir_session, db_session):
    admin = ouvrir_session(P.BENEVOLE_ACCESS_MANAGE)
    assert client.get(f"{BASE}/queue").status_code == 200

    db_session.query(UserRole).filter_by(user_id=admin.id).delete()
    db_session.commit()

    assert client.get(f"{BASE}/queue").status_code == 401


# --- US3: writes are logged under the admin ---------------------------------


def _validate(client, course, athlete, row, db_session):
    return client.post(f"{BASE}/participations/{row.id}/validate")


def _reject(client, course, athlete, row, db_session):
    return client.post(f"{BASE}/participations/{row.id}/reject")


def _unreject(client, course, athlete, row, db_session):
    row.is_rejected = True
    db_session.commit()
    return client.post(f"{BASE}/participations/{row.id}/unreject")


def _update_fields(client, course, athlete, row, db_session):
    return client.patch(f"{BASE}/participations/{row.id}", json={"bib_number": "42"})


def _rename_course(client, course, athlete, row, db_session):
    return client.patch(f"{BASE}/courses/{course.id}", json={"name": "Renommée"})


def _reassign(client, course, athlete, row, db_session):
    target = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul", club="ASPTT")
    db_session.commit()
    return client.post(f"{BASE}/participations/{row.id}/reassign", json={"athlete_id": target.id})


WRITES = [_validate, _reject, _unreject, _update_fields, _rename_course, _reassign]


@pytest.mark.parametrize("write", WRITES, ids=lambda f: f.__name__.lstrip("_"))
def test_power_holder_write_is_logged_under_the_admin(
    client, ouvrir_session, pending_result, system_account, db_session, write
):
    admin = ouvrir_session(P.BENEVOLE_ACCESS_MANAGE)

    response = write(client, *pending_result, db_session)

    assert response.status_code == 200
    assert last_log_user_id(db_session) == admin.id


def test_sso_identity_wins_over_the_cookie(
    client, ouvrir_session, volunteer_cookie, pending_result, system_account, db_session
):
    admin = ouvrir_session(P.BENEVOLE_ACCESS_MANAGE)
    volunteer_cookie()

    assert _validate(client, *pending_result, db_session).status_code == 200
    assert last_log_user_id(db_session) == admin.id


def test_cookie_without_power_is_logged_under_the_system_account(
    client, ouvrir_session, volunteer_cookie, pending_result, system_account, db_session
):
    ouvrir_session(P.SITE_ACCESS_MANAGE)
    volunteer_cookie()

    assert _validate(client, *pending_result, db_session).status_code == 200
    assert last_log_user_id(db_session) == system_account.id
