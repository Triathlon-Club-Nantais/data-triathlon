"""Detach results onto a new homonym record through the admin API (#1209)."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.athlete import Athlete
from app.repositories import course_repository, participation_repository
from app.services import athlete_detach
from tests.test_api.test_admin_data_api import _session_etroite


@pytest.fixture
def shared(db_session):
    athlete = Athlete(nom="MARTIN", prenom="Thomas")
    db_session.add(athlete)
    db_session.flush()
    results = [
        participation_repository.create(
            db_session, athlete_id=athlete.id, club=club,
            course_id=course_repository.get_or_create(
                db_session, name=name, event_date=date(2026, 5, 16), event_type="triathlon-m"
            ).id,
        )
        for name, club in (("Tri A", "Triathlon Club Nantais"), ("Tri B", "Vendôme Triathlon"))
    ]
    db_session.commit()
    return athlete, results


def test_detaching_returns_the_new_record(client, shared):
    athlete, (_, vendome) = shared

    response = client.post(f"/api/v1/admin/athletes/{athlete.id}/detach", json={"participation_ids": [vendome.id]})

    assert response.status_code == 201
    body = response.json()
    assert body["id"] != athlete.id and (body["nom"], body["participations"]) == ("MARTIN", 1)


def test_detaching_every_result_is_refused(client, shared):
    athlete, results = shared

    response = client.post(
        f"/api/v1/admin/athletes/{athlete.id}/detach", json={"participation_ids": [p.id for p in results]}
    )

    assert response.status_code == 400


def test_detaching_needs_both_powers(client, db_session, shared):
    athlete, (_, vendome) = shared
    url = f"/api/v1/admin/athletes/{athlete.id}/detach"

    client.cookies.clear()
    assert client.post(url, json={"participation_ids": [vendome.id]}).status_code == 401
    _session_etroite(client, db_session, "athletes:write", email="w@exemple.fr", slug="only-write")
    assert client.post(url, json={"participation_ids": [vendome.id]}).status_code == 403
    _session_etroite(client, db_session, "participations:reassign", email="r@exemple.fr", slug="only-reassign")
    assert client.post(url, json={"participation_ids": [vendome.id]}).status_code == 403


def test_a_failure_after_the_writes_leaves_nothing_committed(client, db_session, shared, monkeypatch):
    athlete, (_, vendome) = shared

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(athlete_detach.ignored_athlete_pair_repository, "create", boom)

    def rollback_like_get_db():
        # The real get_db closes the session without commit, which rolls back.
        try:
            yield db_session
        finally:
            db_session.rollback()

    app.dependency_overrides[get_db] = rollback_like_get_db
    with TestClient(app, raise_server_exceptions=False, cookies=client.cookies) as failing:
        response = failing.post(
            f"/api/v1/admin/athletes/{athlete.id}/detach", json={"participation_ids": [vendome.id]}
        )

    assert response.status_code == 500
    assert db_session.query(Athlete).count() == 1
    assert participation_repository.count_for_athlete(db_session, athlete.id) == 2
