"""Séances récurrentes (#1291), contrat de contracts/api.md section Récurrences."""
from datetime import date, timedelta

from app.core.permissions import P
from tests.test_api.test_admin_training_sessions import _session_avec

BASE = "/api/v1/admin/training-recurrences"
SESSIONS = "/api/v1/admin/training-sessions"


def _body(weeks=3, **fields):
    today = date.today()
    start = today + timedelta(days=(2 - today.weekday()) % 7 or 7)
    return {
        "weekday": 2,
        "start_time": "14:00:00",
        "location": "Piscine",
        "starts_on": start.isoformat(),
        "ends_on": (start + timedelta(weeks=weeks - 1)).isoformat(),
        "group_ids": [],
        **fields,
    }


def test_preview_announces_the_dates(client):
    body = client.post(f"{BASE}/preview", json=_body()).json()

    assert body["occurrence_count"] == 3
    assert len(body["dates"]) == 3


def test_preview_refuses_too_many_occurrences_in_french(client):
    response = client.post(f"{BASE}/preview", json=_body(weeks=54))

    assert response.status_code == 422
    assert "au plus 53 séances" in response.text


def test_full_cycle(client):
    group = client.post("/api/v1/admin/training-groups", json={"name": "Benjamins"}).json()
    created = client.post(BASE, json=_body(group_ids=[group["id"]]))
    assert created.status_code == 201
    recurrence = created.json()
    assert recurrence["created_session_count"] == 3
    assert recurrence["group_ids"] == [group["id"]]
    assert recurrence["upcoming_session_count"] == 3

    sessions = client.get(SESSIONS).json()
    assert [s["recurrence_id"] for s in sessions] == [recurrence["id"]] * 3

    patched = client.patch(f"{BASE}/{recurrence['id']}", json={"location": "Gymnase"})
    assert patched.status_code == 200
    assert patched.json()["location"] == "Gymnase"
    assert {s["location"] for s in client.get(SESSIONS).json()} == {"Gymnase"}

    assert client.get(BASE).json()[0]["id"] == recurrence["id"]

    deleted = client.delete(f"{BASE}/{recurrence['id']}")
    assert deleted.json() == {"deleted_session_count": 3, "kept_session_count": 0}
    assert client.get(SESSIONS).json() == []


def test_a_weekday_out_of_range_is_refused(client):
    assert client.post(BASE, json=_body(weekday=7)).status_code == 422


def test_an_unknown_recurrence_is_a_404(client):
    assert client.patch(f"{BASE}/9999", json={"location": "Lac"}).status_code == 404


READS = [("GET", BASE)]
WRITES = [
    ("POST", f"{BASE}/preview", _body()),
    ("POST", BASE, _body()),
    ("PATCH", f"{BASE}/1", {"location": "Lac"}),
    ("DELETE", f"{BASE}/1", None),
]


def test_anonymous_is_refused(client):
    client.cookies.clear()
    for method, path in READS:
        assert client.request(method, path).status_code == 401
    for method, path, body in WRITES:
        assert client.request(method, path, json=body).status_code == 401


def test_jeunes_read_alone_reads_but_does_not_write(client, db_session):
    _session_avec(client, db_session, str(P.JEUNES_READ))
    for method, path in READS:
        assert client.request(method, path).status_code == 200
    for method, path, body in WRITES:
        assert client.request(method, path, json=body).status_code == 403


def test_a_session_without_privilege_is_refused(client, db_session):
    _session_avec(client, db_session)
    for method, path in READS:
        assert client.request(method, path).status_code == 403
