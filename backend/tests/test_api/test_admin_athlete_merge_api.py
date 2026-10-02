"""Fusion de deux fiches par l'API admin (#908) : aperçu, acte, refus, 409 de renommage."""
from datetime import date

import pytest

from app.models.admin_action_log import AdminActionLog
from app.models.athlete import Athlete
from app.repositories import course_repository, participation_repository
from tests.test_api.test_admin_data_api import _session_etroite


@pytest.fixture
def pair(db_session):
    kept = Athlete(nom="DUPONT", prenom="Jean")
    absorbed = Athlete(nom="DUPOMT", prenom="Jean")
    db_session.add_all([kept, absorbed])
    db_session.flush()
    course = course_repository.get_or_create(
        db_session, name="Tri A", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    participation_repository.create(
        db_session, athlete_id=absorbed.id, course_id=course.id, bib_number="1", status="finisher"
    )
    db_session.commit()
    return kept, absorbed


def test_the_impact_announces_the_merge_without_writing(client, db_session, pair):
    kept, absorbed = pair

    response = client.get(f"/api/v1/admin/athletes/{kept.id}/merge-impact", params={"absorbed_id": absorbed.id})

    assert response.status_code == 200
    body = response.json()
    assert (body["moves"]["participations"], body["alias_added"], body["blocking_reason"]) == (1, True, None)
    assert "birth_date" in body["kept"] and "birth_date" in body["absorbed"]
    assert db_session.get(Athlete, absorbed.id) is not None


def test_the_merge_moves_the_results_and_logs_once(client, db_session, pair):
    kept, absorbed = pair

    response = client.post(f"/api/v1/admin/athletes/{kept.id}/merge", json={"absorbed_id": absorbed.id})

    assert response.status_code == 200
    assert response.json()["participations"] == 1
    db_session.expire_all()
    assert db_session.get(Athlete, absorbed.id) is None
    assert db_session.query(AdminActionLog).filter_by(action="athlete.merge").count() == 1


def test_a_refused_merge_is_a_409_with_its_reason(client, pair):
    kept, _ = pair

    response = client.post(f"/api/v1/admin/athletes/{kept.id}/merge", json={"absorbed_id": kept.id})

    assert response.status_code == 409
    assert response.json()["code"] == "same_athlete"


def test_a_merge_with_an_unknown_record_is_a_404(client, pair):
    kept, _ = pair

    assert client.post(f"/api/v1/admin/athletes/{kept.id}/merge", json={"absorbed_id": 99999}).status_code == 404


def test_the_merge_body_requires_an_integer(client, pair):
    kept, absorbed = pair

    response = client.post(f"/api/v1/admin/athletes/{kept.id}/merge", json={"absorbed_id": str(absorbed.id)})

    assert response.status_code == 422


@pytest.mark.parametrize("method", ["get", "post"])
def test_merge_routes_need_a_session_then_the_athletes_write_power(client, db_session, pair, method):
    kept, absorbed = pair
    url = f"/api/v1/admin/athletes/{kept.id}/merge" + ("-impact" if method == "get" else "")

    def call():
        if method == "get":
            return client.get(url, params={"absorbed_id": absorbed.id})
        return client.post(url, json={"absorbed_id": absorbed.id})

    client.cookies.clear()
    assert call().status_code == 401
    _session_etroite(client, db_session, "athletes:read")
    assert call().status_code == 403


def test_the_impact_also_needs_athletes_read_since_it_shows_birth_dates(client, db_session, pair):
    """La date de naissance ne sort que derrière `athletes:read` (FR-025 de #117)."""
    kept, absorbed = pair
    _session_etroite(client, db_session, "athletes:write")

    response = client.get(f"/api/v1/admin/athletes/{kept.id}/merge-impact", params={"absorbed_id": absorbed.id})

    assert response.status_code == 403


def test_renaming_onto_another_identity_names_the_conflicting_record(client, pair):
    kept, absorbed = pair

    response = client.patch(f"/api/v1/admin/athletes/{absorbed.id}", json={"nom": "DUPONT"})

    assert response.status_code == 409
    assert response.json()["conflicting_athlete_id"] == kept.id
