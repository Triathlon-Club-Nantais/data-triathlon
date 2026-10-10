"""Groupes d'entraînement (#1291), contrat de contracts/api.md section Groupes."""
import pytest

from app.core.permissions import P
from app.models.organisation import Organisation
from app.repositories import profile_repository
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

    assert client.get(BASE).json() == [{"id": group_id, "name": "Benjamins mercredi", "member_count": 1}]
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
    _session_avec(client, db_session, str(P.JEUNES_READ))
    for method, path in READS:
        assert client.request(method, path).status_code in (200, 404)
    for method, path, body in WRITES:
        assert client.request(method, path, json=body).status_code == 403
