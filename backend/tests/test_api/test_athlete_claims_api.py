"""Athlete claims over HTTP (#1325): contracts/auth-me-athlete-claim.md and admin-athlete-claims.md."""
import pytest

from app.core.season import current_season
from app.models.admin_action_log import AdminActionLog
from app.models.athlete import Athlete
from app.models.athlete_claim import STATUS_PENDING, STATUS_REJECTED, AthleteClaim
from app.models.user import User
from app.repositories import member_email_repository

from .test_admin_data_api import _session_etroite

MY_CLAIM = "/api/v1/auth/me/athlete-claim"
MY_ATHLETE = "/api/v1/auth/me/athlete"
QUEUE = "/api/v1/admin/athlete-claims"


@pytest.fixture
def athlete(db_session):
    row = Athlete(nom="Martin", prenom="Léa", club="TRIATHLON CLUB NANTAIS")
    db_session.add(row)
    db_session.commit()
    return row


def _account(client, db_session):
    return _session_etroite(client, db_session, email="lea@exemple.fr", slug="sans-role")


def _member(client, db_session):
    user = _account(client, db_session)
    member_email_repository.add_manual(db_session, user.email, current_season())
    db_session.commit()
    return user


def test_request_returns_the_pending_claim_and_me_shows_it(client, db_session, athlete):
    _member(client, db_session)

    response = client.post(MY_CLAIM, json={"athlete_id": athlete.id})

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["athlete"] == {"id": athlete.id, "prenom": "Léa", "nom": "Martin"}
    assert body["created_at"].endswith("Z")
    me = client.get("/api/v1/auth/me").json()
    assert me["athlete"] is None
    assert me["athlete_claim"]["status"] == "pending"


def test_request_errors(client, db_session, athlete):
    user = _member(client, db_session)

    assert client.post(MY_CLAIM, json={"athlete_id": 999_999}).status_code == 404
    db_session.get(User, user.id).athlete_id = athlete.id
    db_session.commit()
    conflict = client.post(MY_CLAIM, json={"athlete_id": athlete.id})
    assert conflict.status_code == 409
    assert "détachez-vous" in conflict.json()["detail"]


def test_cancel_and_detach_are_idempotent(client, db_session, athlete):
    user = _member(client, db_session)
    client.post(MY_CLAIM, json={"athlete_id": athlete.id})

    assert client.delete(MY_CLAIM).status_code == 204
    assert client.delete(MY_CLAIM).status_code == 204
    db_session.get(User, user.id).athlete_id = athlete.id
    db_session.commit()
    assert client.get("/api/v1/auth/me").json()["athlete"]["id"] == athlete.id
    assert client.delete(MY_ATHLETE).status_code == 204
    assert client.delete(MY_ATHLETE).status_code == 204
    me = client.get("/api/v1/auth/me").json()
    assert (me["athlete"], me["athlete_claim"], me["is_member"]) == (None, None, True)


def test_user_routes_require_a_session(client):
    client.cookies.clear()

    assert client.post(MY_CLAIM, json={"athlete_id": 1}).status_code == 401
    assert client.delete(MY_CLAIM).status_code == 401
    assert client.delete(MY_ATHLETE).status_code == 401


def test_the_queue_lists_then_approves(client, db_session, athlete):
    user = _member(client, db_session)
    client.post(MY_CLAIM, json={"athlete_id": athlete.id})
    reviewer = _session_etroite(client, db_session, "athlete_claims:review", email="rev@exemple.fr", slug="rev")

    listed = client.get(QUEUE)
    assert listed.status_code == 200
    (item,) = listed.json()
    assert item["user"] == {"id": user.id, "display_name": "", "email": "lea@exemple.fr"}
    assert item["athlete"]["club"] == "TRIATHLON CLUB NANTAIS"
    assert (item["licensee"], item["email_on_member_list"], item["linked_accounts"]) == (None, True, 0)

    assert client.post(f"{QUEUE}/{item['id']}/approve").status_code == 204
    assert client.post(f"{QUEUE}/{item['id']}/approve").status_code == 404
    db_session.expire_all()
    assert db_session.get(User, user.id).athlete_id == athlete.id
    assert db_session.query(AdminActionLog).filter_by(action="athlete_claim.approve").one().user_id == reviewer.id
    assert client.get("/api/v1/admin/badge-counts").json()["claims"] == 0


def test_the_queue_rejects(client, db_session, athlete):
    _member(client, db_session)
    claim_id = client.post(MY_CLAIM, json={"athlete_id": athlete.id}).json()["id"]
    _session_etroite(client, db_session, "athlete_claims:review", email="rev@exemple.fr", slug="rev")
    assert client.get("/api/v1/admin/badge-counts").json()["claims"] == 1

    assert client.post(f"{QUEUE}/{claim_id}/reject").status_code == 204

    db_session.expire_all()
    assert db_session.get(AthleteClaim, claim_id).status == STATUS_REJECTED
    assert client.get(QUEUE).json() == []


def test_the_queue_requires_the_permission(client, db_session):
    _session_etroite(client, db_session, "member_emails:manage")

    assert client.get(QUEUE).status_code == 403
    assert client.post(f"{QUEUE}/1/approve").status_code == 403
    assert client.post(f"{QUEUE}/1/reject").status_code == 403
    assert "claims" not in client.get("/api/v1/admin/badge-counts").json()


LINKS = "/api/v1/admin/athlete-links"


def test_the_club_lists_and_detaches_linked_accounts(client, db_session, athlete):
    """#1633."""
    user = _member(client, db_session)
    db_session.get(User, user.id).athlete_id = athlete.id
    db_session.commit()
    _session_etroite(client, db_session, "athlete_claims:review", email="rev@exemple.fr", slug="rev")

    (link,) = client.get(LINKS).json()
    assert link == {
        "user": {"id": user.id, "display_name": "", "email": "lea@exemple.fr"},
        "athlete": {"id": athlete.id, "prenom": "Léa", "nom": "Martin", "club": "TRIATHLON CLUB NANTAIS"},
        "licensed_this_season": False,
    }
    assert client.delete(f"{LINKS}/{user.id}").status_code == 204
    assert client.delete(f"{LINKS}/{user.id}").status_code == 404
    assert client.get(LINKS).json() == []


def test_linked_accounts_require_the_permission(client, db_session):
    _session_etroite(client, db_session, "member_emails:manage")

    assert client.get(LINKS).status_code == 403
    assert client.delete(f"{LINKS}/1").status_code == 403
    client.cookies.clear()
    assert client.get(LINKS).status_code == 401


def test_claim_by_a_non_member_is_403(client, db_session, athlete):
    """The response names the athlete: only club members may ask (#1785)."""
    _account(client, db_session)

    response = client.post(MY_CLAIM, json={"athlete_id": athlete.id})

    assert response.status_code == 403
    assert response.json()["detail"].startswith("Réservé aux adhérents du club")
    assert db_session.query(AthleteClaim).count() == 0


def test_claim_by_a_member_still_returns_201(client, db_session, athlete):
    _member(client, db_session)

    assert client.post(MY_CLAIM, json={"athlete_id": athlete.id}).status_code == 201


def test_a_pending_claim_of_a_non_member_can_still_be_approved(client, db_session, athlete):
    user = _account(client, db_session)
    db_session.add(AthleteClaim(user_id=user.id, athlete_id=athlete.id, status=STATUS_PENDING))
    db_session.commit()
    _session_etroite(client, db_session, "athlete_claims:review", email="rev@exemple.fr", slug="rev")
    (item,) = client.get(QUEUE).json()

    assert item["email_on_member_list"] is False
    assert client.post(f"{QUEUE}/{item['id']}/approve").status_code == 204


def test_the_queue_requires_a_session(client):
    client.cookies.clear()

    assert client.get(QUEUE).status_code == 401
    assert client.post(f"{QUEUE}/1/approve").status_code == 401
