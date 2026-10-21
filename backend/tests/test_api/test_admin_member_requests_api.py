"""Join request back-office queue over HTTP (#1785)."""

from app.core.time import utcnow
from app.models.member_request import STATUS_PENDING, MemberRequest
from app.models.user import User
from app.repositories import role_repository, user_repository
from app.services import membership

from .test_admin_data_api import _session_etroite

QUEUE = "/api/v1/admin/member-requests"
BADGES = "/api/v1/admin/badge-counts"


def _pending(db_session, email="lea@exemple.fr") -> MemberRequest:
    user = user_repository.create(db_session, email=email)
    db_session.flush()
    request = MemberRequest(
        user_id=user.id,
        organisation_id=role_repository.default_organisation(db_session).id,
        first_name="Léa",
        last_name="Martin",
        phone="06 01 02 03 04",
        status=STATUS_PENDING,
    )
    db_session.add(request)
    db_session.commit()
    return request


def test_list_member_requests_needs_the_permission(client, db_session):
    _session_etroite(client, db_session, "athlete_claims:review")

    assert client.get(QUEUE).status_code == 403


def test_list_member_requests_returns_pending_only_with_the_account(client, db_session):
    _session_etroite(client, db_session, "member_requests:review")
    pending = _pending(db_session)
    rejected = _pending(db_session, "bob@exemple.fr")
    assert client.post(f"{QUEUE}/{rejected.id}/reject").status_code == 204

    body = client.get(QUEUE).json()

    assert [row["id"] for row in body] == [pending.id]
    assert body[0]["first_name"] == "Léa"
    assert body[0]["user"]["email"] == "lea@exemple.fr"
    assert body[0]["created_at"].endswith("Z")


def test_approve_member_request_returns_204_and_makes_a_member(client, db_session):
    request = _pending(db_session)
    requester_id = request.user_id

    assert client.post(f"{QUEUE}/{request.id}/approve").status_code == 204

    assert client.get(QUEUE).json() == []
    assert membership.is_member(db_session, db_session.get(User, requester_id), utcnow().date())


def test_reject_member_request_returns_204(client, db_session):
    request = _pending(db_session)

    assert client.post(f"{QUEUE}/{request.id}/reject").status_code == 204
    assert client.get(QUEUE).json() == []


def test_approve_unknown_request_returns_404(client):
    assert client.post(f"{QUEUE}/999999/approve").status_code == 404
    assert client.post(f"{QUEUE}/999999/reject").status_code == 404


def test_badge_counts_include_member_requests_for_a_reviewer(client, db_session):
    _session_etroite(client, db_session, "member_requests:review")
    _pending(db_session)

    assert client.get(BADGES).json() == {"member_requests": 1}
