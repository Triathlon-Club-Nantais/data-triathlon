"""Join request of a signed-in non-member (#1785)."""

from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.core.exceptions import NotFoundError
from app.core.season import current_season
from app.core.time import utcnow
from app.models.admin_action_log import AdminActionLog
from app.models.member_request import STATUS_PENDING, STATUS_REJECTED
from app.models.organisation import Organisation
from app.repositories import member_email_repository, member_request_repository, user_repository
from app.schemas.member_request import MemberRequestCreate
from app.services import member_requests


def _data(**overrides) -> MemberRequestCreate:
    return MemberRequestCreate(
        **{"first_name": "Ana", "last_name": "Lopez", "phone": "06 01 02 03 04", **overrides}
    )


@pytest.fixture(autouse=True)
def _club(db_session):
    db_session.add(Organisation(slug="tcn", name="TCN"))
    db_session.flush()


@pytest.fixture
def ana(db_session):
    return user_repository.create(db_session, email="ana@exemple.fr", display_name="Ana L.")


@pytest.fixture
def reviewer(db_session):
    return user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")


def test_a_member_cannot_ask(db_session, ana):
    member_email_repository.add_manual(db_session, ana.email, current_season())

    with pytest.raises(member_requests.AlreadyMemberError):
        member_requests.request_membership(db_session, ana, _data(), now=utcnow())


def test_a_pending_request_is_replaced(db_session, ana):
    first = member_requests.request_membership(db_session, ana, _data(), now=utcnow())
    second = member_requests.request_membership(
        db_session, ana, _data(last_name="López"), now=utcnow()
    )

    assert second.id == first.id
    assert (second.last_name, second.status) == ("López", STATUS_PENDING)


def test_rejected_less_than_30_days_ago_refuses_with_the_date(db_session, ana):
    now = utcnow()
    request = member_requests.request_membership(db_session, ana, _data(), now=now)
    member_request_repository.reject(db_session, request, now=now - timedelta(days=29))

    with pytest.raises(member_requests.RejectedRecentlyError) as refused:
        member_requests.request_membership(db_session, ana, _data(), now=now)

    again = (now - timedelta(days=29) + member_requests.REQUEST_AGAIN_AFTER).strftime("%d/%m/%Y")
    assert refused.value.message == (
        f"Votre demande a été refusée. Vous pourrez en envoyer une nouvelle à partir du {again}."
    )


def test_rejected_30_days_ago_can_ask_again(db_session, ana):
    now = utcnow()
    request = member_requests.request_membership(db_session, ana, _data(), now=now)
    member_request_repository.reject(db_session, request, now=now - timedelta(days=30))

    again = member_requests.request_membership(db_session, ana, _data(), now=now)

    assert (again.status, again.decided_at) == (STATUS_PENDING, None)


def test_cancel_keeps_a_rejected_request(db_session, ana):
    now = utcnow()
    request = member_requests.request_membership(db_session, ana, _data(), now=now)
    member_request_repository.reject(db_session, request, now=now)

    member_requests.cancel_pending(db_session, ana)

    assert member_requests.current_for(db_session, ana).status == STATUS_REJECTED


def test_cancel_removes_a_pending_request(db_session, ana):
    member_requests.request_membership(db_session, ana, _data(), now=utcnow())

    member_requests.cancel_pending(db_session, ana)

    assert member_requests.current_for(db_session, ana) is None


def test_approve_adds_the_address_for_the_current_season_and_deletes_the_request(
    db_session, ana, reviewer
):
    request = member_requests.request_membership(db_session, ana, _data(), now=utcnow())

    member_requests.approve(db_session, request.id, actor_id=reviewer.id)

    assert member_email_repository.counts(db_session, ana.email, utcnow().date())
    assert member_requests.current_for(db_session, ana) is None
    log = db_session.query(AdminActionLog).filter_by(action="member_request.approve").one()
    assert (log.entity_type, log.entity_id) == ("user", ana.id)
    assert "Ana" not in str(log.payload) and "0601" not in str(log.payload)


def test_approve_succeeds_when_the_address_is_already_listed(db_session, ana, reviewer):
    request = member_requests.request_membership(db_session, ana, _data(), now=utcnow())
    member_email_repository.add_manual(db_session, ana.email, current_season())

    member_requests.approve(db_session, request.id, actor_id=reviewer.id)

    assert member_requests.current_for(db_session, ana) is None


def test_approve_then_reject_the_same_request_raises_not_found(db_session, ana, reviewer):
    request = member_requests.request_membership(db_session, ana, _data(), now=utcnow())
    member_requests.approve(db_session, request.id, actor_id=reviewer.id)

    with pytest.raises(NotFoundError, match="plus en attente"):
        member_requests.reject(db_session, request.id, actor_id=reviewer.id)


def test_reject_sets_status_and_decided_at(db_session, ana, reviewer):
    request = member_requests.request_membership(db_session, ana, _data(), now=utcnow())

    member_requests.reject(db_session, request.id, actor_id=reviewer.id)

    rejected = member_requests.current_for(db_session, ana)
    assert (rejected.status, rejected.decided_at is not None) == (STATUS_REJECTED, True)
    assert db_session.query(AdminActionLog).filter_by(action="member_request.reject").count() == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"first_name": "  "},
        {"last_name": "x" * 101},
        {"phone": None},
        {"phone": "abc"},
        {"phone": None, "birth_date": "1899-12-31"},
        {"phone": None, "birth_date": "2999-01-01"},
    ],
)
def test_create_validation(overrides):
    with pytest.raises(ValidationError):
        _data(**overrides)
