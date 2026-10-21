"""Groupes d'entraînement (#1291), contrat de contracts/api.md section Groupes."""
from datetime import date, datetime

import pytest

from app.core.permissions import P
from app.models.organisation import Organisation
from app.repositories import (
    profile_repository,
    training_group_repository,
    training_session_repository,
)
from app.services import training_group_service
from tests.test_api.test_admin_training_sessions import _session_avec

BASE = "/api/v1/admin/training-groups"


@pytest.fixture
def profile_id(db_session) -> int:
    organisation = db_session.query(Organisation).filter_by(slug="tcn").one()
    profile = profile_repository.create(
        db_session, organisation_id=organisation.id, first_name="Alix", last_name="Martin"
    )
    db_session.commit()
    return profile.id


def test_full_cycle(client, profile_id):
    created = client.post(BASE, json={"name": "Benjamins mercredi"})
    assert created.status_code == 201
    group_id = created.json()["id"]
    assert created.json() == {"id": group_id, "name": "Benjamins mercredi", "members": []}

    detail = client.post(f"{BASE}/{group_id}/members", json={"profile_id": profile_id}).json()
    again = client.post(f"{BASE}/{group_id}/members", json={"profile_id": profile_id}).json()
    assert [m["id"] for m in detail["members"]] == [m["id"] for m in again["members"]] == [profile_id]

    assert client.get(BASE).json() == [{"id": group_id, "name": "Benjamins mercredi", "member_count": 1, "attended": 0, "pointed": 0}]
    assert client.patch(f"{BASE}/{group_id}", json={"name": "Benjamins"}).json()["name"] == "Benjamins"

    removed = client.delete(f"{BASE}/{group_id}/members/{profile_id}")
    assert removed.status_code == 200
    assert removed.json()["members"] == []

    assert client.delete(f"{BASE}/{group_id}").status_code == 204
    assert client.get(f"{BASE}/{group_id}").status_code == 404


def test_a_taken_or_empty_name_is_a_422_in_french(client):
    client.post(BASE, json={"name": "Benjamins"})
    other = client.post(BASE, json={"name": "Minimes"}).json()

    taken = client.patch(f"{BASE}/{other['id']}", json={"name": "Benjamins"})
    empty = client.post(BASE, json={"name": "  "})

    assert taken.status_code == empty.status_code == 422
    assert "Un groupe porte déjà ce nom." in taken.text
    assert "Le nom du groupe est obligatoire." in empty.text


def test_list_reports_the_season_attendance_of_each_group(client, db_session, profile_id, monkeypatch):
    monkeypatch.setattr(training_group_service, "utcnow", lambda: datetime(2026, 10, 15, 12, 0))
    group_id = client.post(BASE, json={"name": "Benjamins"}).json()["id"]
    group = training_group_repository.get(db_session, group_id)
    for day, present in ((date(2026, 9, 2), True), (date(2026, 10, 22), False)):
        session = training_session_repository.create(db_session, date=day)
        training_session_repository.set_groups(db_session, session, [group])
        training_session_repository.add_participant(
            db_session, training_session_id=session.id, profile_id=profile_id, present=present
        )
    db_session.commit()

    (item,) = client.get(BASE).json()

    assert (item["attended"], item["pointed"]) == (1, 1)


def test_adding_an_unknown_profile_is_a_404(client):
    group = client.post(BASE, json={"name": "Benjamins"}).json()

    assert client.post(f"{BASE}/{group['id']}/members", json={"profile_id": 9999}).status_code == 404


READS = [("GET", BASE), ("GET", f"{BASE}/1")]
WRITES = [
    ("POST", BASE, {"name": "Benjamins"}),
    ("PATCH", f"{BASE}/1", {"name": "Minimes"}),
    ("DELETE", f"{BASE}/1", None),
    ("POST", f"{BASE}/1/members", {"profile_id": 1}),
    ("DELETE", f"{BASE}/1/members/1", None),
]


def test_anonymous_is_refused(client):
    client.cookies.clear()
    for method, path in READS:
        assert client.request(method, path).status_code == 401
    for method, path, body in WRITES:
        assert client.request(method, path, json=body).status_code == 401


def test_a_session_without_privilege_is_refused(client, db_session):
    _session_avec(client, db_session)
    for method, path in READS:
        assert client.request(method, path).status_code == 403
    for method, path, body in WRITES:
        assert client.request(method, path, json=body).status_code == 403


def test_jeunes_read_alone_reads_but_does_not_write(client, db_session):
    _session_avec(client, db_session, str(P.YOUTH_READ))
    for method, path in READS:
        assert client.request(method, path).status_code in (200, 404)
    for method, path, body in WRITES:
        assert client.request(method, path, json=body).status_code == 403
