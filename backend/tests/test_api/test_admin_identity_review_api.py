"""La revue d'identité par l'API admin (#908) : liste, compte, mise à l'écart."""
import pytest

from app.models.athlete import Athlete
from tests.test_api.test_admin_data_api import _session_etroite


@pytest.fixture
def swapped(db_session):
    first = Athlete(nom="DUPONT", prenom="Jean", club="A", gender="M")
    second = Athlete(nom="JEAN", prenom="Dupont", club="B", gender="F")
    db_session.add_all([first, second])
    db_session.commit()
    return first, second


def test_the_review_lists_the_cases_and_counts_them(client, swapped):
    first, second = swapped

    listed = client.get("/api/v1/admin/identity-review")
    counted = client.get("/api/v1/admin/identity-review/count")

    assert listed.status_code == 200
    [candidate] = listed.json()["candidates"]
    assert (candidate["reason"], [a["id"] for a in candidate["athletes"]]) == ("swapped", [first.id, second.id])
    assert counted.json() == {"total": 1}


def test_an_ignored_pair_leaves_the_review(client, swapped):
    first, second = swapped

    ignored = client.post(
        "/api/v1/admin/identity-review/ignore", json={"athlete_id_a": second.id, "athlete_id_b": first.id}
    )

    assert ignored.status_code == 201
    assert (ignored.json()["athlete_id_a"], ignored.json()["athlete_id_b"]) == (first.id, second.id)
    assert client.get("/api/v1/admin/identity-review/count").json() == {"total": 0}
    again = client.post(
        "/api/v1/admin/identity-review/ignore", json={"athlete_id_a": first.id, "athlete_id_b": second.id}
    )
    assert again.status_code == 409


def test_ignoring_refuses_a_single_record_and_an_unknown_one(client, swapped):
    first, _ = swapped
    url = "/api/v1/admin/identity-review/ignore"

    assert client.post(url, json={"athlete_id_a": first.id, "athlete_id_b": first.id}).status_code == 400
    assert client.post(url, json={"athlete_id_a": first.id, "athlete_id_b": 99999}).status_code == 404
    assert client.post(url, json={"athlete_id_a": first.id, "athlete_id_b": "2"}).status_code == 422


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", "/api/v1/admin/identity-review"), ("get", "/api/v1/admin/identity-review/count"),
     ("post", "/api/v1/admin/identity-review/ignore")],
)
def test_the_review_needs_a_session_then_the_athletes_write_power(client, db_session, swapped, method, path):
    first, second = swapped

    def call():
        if method == "get":
            return client.get(path)
        return client.post(path, json={"athlete_id_a": first.id, "athlete_id_b": second.id})

    client.cookies.clear()
    assert call().status_code == 401
    _session_etroite(client, db_session, "athletes:read")
    assert call().status_code == 403
