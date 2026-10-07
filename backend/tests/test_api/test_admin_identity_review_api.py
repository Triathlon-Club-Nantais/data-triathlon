"""La revue d'identité par l'API admin (#908) : liste, compte, mise à l'écart."""
from datetime import date

import pytest

from app.models.admin_action_log import AdminActionLog
from app.models.athlete import Athlete
from app.repositories import (
    course_repository,
    ignored_athlete_pair_repository,
    participation_repository,
)
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
     ("post", "/api/v1/admin/identity-review/ignore"), ("post", "/api/v1/admin/identity-review/confirm-club")],
)
def test_the_review_needs_a_session_then_the_athletes_write_power(client, db_session, swapped, method, path):
    first, second = swapped

    def call():
        if method == "get":
            return client.get(path)
        if path.endswith("confirm-club"):
            return client.post(path, json={"athlete_id": first.id, "club_key": "asptt"})
        return client.post(path, json={"athlete_id_a": first.id, "athlete_id_b": second.id})

    client.cookies.clear()
    assert call().status_code == 401
    _session_etroite(client, db_session, "athletes:read")
    assert call().status_code == 403


@pytest.fixture
def multi_club(db_session):
    member = Athlete(nom="MARTIN", prenom="Thomas", club="Triathlon Club Nantais")
    db_session.add(member)
    db_session.flush()
    for name, club in (("Tri A", "Triathlon Club Nantais"), ("Tri B", "Vendôme Triathlon")):
        participation_repository.create(
            db_session, athlete_id=member.id, club=club,
            course_id=course_repository.get_or_create(
                db_session, name=name, event_date=date(2026, 5, 16), event_type="triathlon-m"
            ).id,
        )
    db_session.commit()
    return member


def test_a_multi_club_case_lists_its_clubs_and_a_confirmation_closes_it(client, multi_club):
    [candidate] = client.get("/api/v1/admin/identity-review").json()["candidates"]
    assert candidate["reason"] == "multi_club"
    assert candidate["clubs"] == [{"club": "Vendôme Triathlon", "club_key": "vendometriathlon", "results": 1}]

    confirmed = client.post(
        "/api/v1/admin/identity-review/confirm-club",
        json={"athlete_id": multi_club.id, "club_key": "vendometriathlon"},
    )

    assert confirmed.status_code == 201
    assert confirmed.json()["club_key"] == "vendometriathlon"
    assert client.get("/api/v1/admin/identity-review/count").json() == {"total": 0}
    again = client.post(
        "/api/v1/admin/identity-review/confirm-club",
        json={"athlete_id": multi_club.id, "club_key": "vendometriathlon"},
    )
    assert again.status_code == 409


def test_confirming_a_club_refuses_an_unknown_record_a_blank_or_uncarried_club(client, multi_club):
    url = "/api/v1/admin/identity-review/confirm-club"

    assert client.post(url, json={"athlete_id": 99999, "club_key": "vendometriathlon"}).status_code == 404
    assert client.post(url, json={"athlete_id": multi_club.id, "club_key": "  "}).status_code == 400
    assert client.post(url, json={"athlete_id": multi_club.id, "club_key": "asptt"}).status_code == 400
    assert client.post(url, json={"athlete_id": "1", "club_key": "x"}).status_code == 422


def _last_action(db_session) -> str:
    db_session.expire_all()
    return db_session.query(AdminActionLog).order_by(AdminActionLog.id.desc()).first().action


def test_an_ignored_pair_is_listed_then_its_undo_returns_it_to_the_review(client, db_session, swapped):
    first, second = swapped
    client.post("/api/v1/admin/identity-review/ignore", json={"athlete_id_a": first.id, "athlete_id_b": second.id})

    [pair] = client.get("/api/v1/admin/identity-review/ignored").json()["pairs"]
    assert [a["id"] for a in pair["athletes"]] == [first.id, second.id]
    assert (pair["athletes"][0]["nom"], pair["athletes"][0]["prenom"]) == ("DUPONT", "Jean")
    assert pair["ignored_at"]
    assert pair["automatic"] is False

    undone = client.delete(f"/api/v1/admin/identity-review/ignored/{pair['id']}")

    assert undone.status_code == 204
    assert client.get("/api/v1/admin/identity-review/ignored").json() == {"pairs": []}
    assert client.get("/api/v1/admin/identity-review/count").json() == {"total": 1}
    assert _last_action(db_session) == "athlete_identity.unignore"
    assert client.delete(f"/api/v1/admin/identity-review/ignored/{pair['id']}").status_code == 404


def test_a_pair_set_by_the_import_is_listed_as_automatic(client, db_session, swapped):
    first, second = swapped
    ignored_athlete_pair_repository.create(db_session, athlete_id_a=first.id, athlete_id_b=second.id, user_id=None)
    db_session.commit()

    [pair] = client.get("/api/v1/admin/identity-review/ignored").json()["pairs"]

    assert pair["automatic"] is True


def test_a_confirmed_club_is_listed_then_its_undo_returns_the_case(client, db_session, multi_club):
    client.post(
        "/api/v1/admin/identity-review/confirm-club",
        json={"athlete_id": multi_club.id, "club_key": "vendometriathlon"},
    )

    [club] = client.get("/api/v1/admin/identity-review/confirmed-clubs").json()["clubs"]
    assert (club["athlete_id"], club["nom"], club["prenom"], club["club_key"]) == (
        multi_club.id, "MARTIN", "Thomas", "vendometriathlon",
    )

    undone = client.delete(f"/api/v1/admin/identity-review/confirmed-clubs/{club['id']}")

    assert undone.status_code == 204
    assert client.get("/api/v1/admin/identity-review/confirmed-clubs").json() == {"clubs": []}
    assert client.get("/api/v1/admin/identity-review/count").json() == {"total": 1}
    assert _last_action(db_session) == "athlete_identity.unconfirm_club"
    assert client.delete(f"/api/v1/admin/identity-review/confirmed-clubs/{club['id']}").status_code == 404


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", "/api/v1/admin/identity-review/ignored"), ("delete", "/api/v1/admin/identity-review/ignored/1"),
     ("get", "/api/v1/admin/identity-review/confirmed-clubs"),
     ("delete", "/api/v1/admin/identity-review/confirmed-clubs/1")],
)
def test_the_undo_routes_need_the_athletes_write_power(client, db_session, method, path):
    client.cookies.clear()
    assert getattr(client, method)(path).status_code == 401
    _session_etroite(client, db_session, "athletes:read")
    assert getattr(client, method)(path).status_code == 403
