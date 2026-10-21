"""Join request over HTTP (#1785)."""

from app.core.season import current_season
from app.models.member_request import MemberRequest
from app.repositories import member_email_repository

from .test_admin_data_api import _session_etroite

URL = "/api/v1/auth/me/member-request"
BODY = {"first_name": "Léa", "last_name": "Martin", "birth_date": None, "phone": "06 01 02 03 04"}


def _account(client, db_session):
    return _session_etroite(client, db_session, email="lea@exemple.fr", slug="sans-role")


def test_post_member_request_returns_201_and_shows_in_auth_me(client, db_session):
    _account(client, db_session)

    response = client.post(URL, json=BODY)

    assert response.status_code == 201
    body = response.json()
    assert (body["status"], body["first_name"], body["phone"], body["decided_at"]) == (
        "pending",
        "Léa",
        "06 01 02 03 04",
        None,
    )
    assert body["created_at"].endswith("Z")
    assert client.get("/api/v1/auth/me").json()["member_request"]["id"] == body["id"]


def test_post_member_request_requires_birth_date_or_phone(client, db_session):
    _account(client, db_session)

    assert client.post(URL, json={**BODY, "phone": None}).status_code == 422


def test_post_member_request_rejects_a_future_birth_date(client, db_session):
    _account(client, db_session)

    assert client.post(URL, json={**BODY, "birth_date": "2999-01-01"}).status_code == 422


def test_post_member_request_twice_never_500(client, db_session):
    _account(client, db_session)

    assert client.post(URL, json=BODY).status_code == 201
    assert client.post(URL, json={**BODY, "last_name": "Durand"}).status_code == 201
    rows = db_session.query(MemberRequest).all()
    assert [row.last_name for row in rows] == ["Durand"]


def test_post_member_request_by_a_member_is_409(client, db_session):
    user = _account(client, db_session)
    member_email_repository.add_manual(db_session, user.email, current_season())
    db_session.commit()

    response = client.post(URL, json=BODY)

    assert response.status_code == 409
    assert response.json()["detail"] == "Votre compte est déjà reconnu adhérent."


def test_post_member_request_is_anonymous_401(client):
    client.cookies.clear()

    assert client.post(URL, json=BODY).status_code == 401


def test_delete_member_request_returns_204(client, db_session):
    _account(client, db_session)
    client.post(URL, json=BODY)

    response = client.delete(URL)

    assert response.status_code == 204
    assert client.get("/api/v1/auth/me").json()["member_request"] is None


def test_account_export_includes_the_member_request(client, db_session):
    _account(client, db_session)
    client.post(URL, json=BODY)

    exported = client.get("/api/v1/auth/me/export").json()

    assert exported["member_request"]["first_name"] == "Léa"
