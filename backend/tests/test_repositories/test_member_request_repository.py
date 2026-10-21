"""Join requests, one per account and organisation (#1785)."""

from datetime import date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.member_request import STATUS_PENDING, STATUS_REJECTED, MemberRequest
from app.models.organisation import Organisation
from app.repositories import member_request_repository as repo
from app.repositories import user_repository


def _organisation(db, slug="tcn") -> Organisation:
    row = Organisation(slug=slug, name=slug.upper())
    db.add(row)
    db.flush()
    return row


def _user(db, email="ana@exemple.fr"):
    return user_repository.create(db, email=email, display_name="")


def _request(db, user, organisation, last_name="Lopez"):
    return repo.upsert_pending(
        db,
        user_id=user.id,
        organisation_id=organisation.id,
        first_name="Ana",
        last_name=last_name,
        birth_date=None,
        phone=None,
    )


def test_upsert_pending_replaces_the_previous_request(db_session):
    user, tcn = _user(db_session), _organisation(db_session)
    first = repo.upsert_pending(
        db_session,
        user_id=user.id,
        organisation_id=tcn.id,
        first_name="Ana",
        last_name="Lopez",
        birth_date=None,
        phone="0601020304",
    )
    second = repo.upsert_pending(
        db_session,
        user_id=user.id,
        organisation_id=tcn.id,
        first_name="Ana",
        last_name="López",
        birth_date=date(1990, 5, 1),
        phone=None,
    )
    assert second.id == first.id
    assert (second.last_name, second.birth_date, second.phone, second.status) == (
        "López",
        date(1990, 5, 1),
        None,
        STATUS_PENDING,
    )


def test_upsert_pending_resets_a_rejected_request(db_session):
    user, tcn = _user(db_session), _organisation(db_session)
    request = _request(db_session, user, tcn)
    repo.reject(db_session, request, now=datetime(2026, 10, 21))
    assert (request.status, request.decided_at) == (STATUS_REJECTED, datetime(2026, 10, 21))

    again = _request(db_session, user, tcn)
    assert (again.id, again.status, again.decided_at) == (request.id, STATUS_PENDING, None)


def test_one_request_per_account_and_organisation(db_session):
    user, tcn, other = (
        _user(db_session),
        _organisation(db_session),
        _organisation(db_session, "other"),
    )
    _request(db_session, user, tcn)
    _request(db_session, user, other)
    assert repo.get_for_user(db_session, user.id, other.id) is not None

    with pytest.raises(IntegrityError):
        db_session.add(
            MemberRequest(
                user_id=user.id,
                organisation_id=tcn.id,
                first_name="A",
                last_name="B",
                status=STATUS_PENDING,
            )
        )
        db_session.flush()


def test_list_pending_and_count_skip_rejected(db_session):
    tcn = _organisation(db_session)
    first, second, third = (_user(db_session, f"u{i}@exemple.fr") for i in range(3))
    _request(db_session, first, tcn)
    _request(db_session, second, tcn)
    repo.reject(db_session, _request(db_session, third, tcn), now=datetime(2026, 10, 21))

    pending = repo.list_pending(db_session, tcn.id)
    assert [item.user_id for item in pending] == [first.id, second.id]
    assert pending[0].user.email == "u0@exemple.fr"
    assert repo.count_pending(db_session, tcn.id) == 2


def test_get_pending_ignores_a_rejected_request(db_session):
    user, tcn = _user(db_session), _organisation(db_session)
    request = _request(db_session, user, tcn)
    assert repo.get_pending(db_session, request.id).id == request.id
    repo.reject(db_session, request, now=datetime(2026, 10, 21))
    assert repo.get_pending(db_session, request.id) is None


def test_delete_pending_for_user_keeps_a_rejected_request(db_session):
    tcn = _organisation(db_session)
    pending_user, rejected_user = _user(db_session), _user(db_session, "b@exemple.fr")
    _request(db_session, pending_user, tcn)
    repo.reject(db_session, _request(db_session, rejected_user, tcn), now=datetime(2026, 10, 21))

    repo.delete_pending_for_user(db_session, pending_user.id, tcn.id)
    repo.delete_pending_for_user(db_session, rejected_user.id, tcn.id)

    assert repo.get_for_user(db_session, pending_user.id, tcn.id) is None
    assert repo.get_for_user(db_session, rejected_user.id, tcn.id).status == STATUS_REJECTED


def test_delete_request(db_session):
    user, tcn = _user(db_session), _organisation(db_session)
    repo.delete_request(db_session, _request(db_session, user, tcn))
    assert repo.get_for_user(db_session, user.id, tcn.id) is None


def test_deleting_the_account_deletes_its_requests(db_session):
    user, tcn = _user(db_session), _organisation(db_session)
    _request(db_session, user, tcn)
    db_session.delete(user)
    db_session.flush()
    assert db_session.scalars(select(MemberRequest)).all() == []


def test_retention_counts_match_deletions(db_session):
    tcn = _organisation(db_session)
    old, recent = datetime(2026, 1, 1), datetime(2026, 10, 1)
    cutoff = datetime(2026, 6, 1)
    for index, (status, created) in enumerate(
        [
            (STATUS_REJECTED, old),
            (STATUS_REJECTED, recent),
            (STATUS_PENDING, old),
            (STATUS_PENDING, recent),
        ]
    ):
        request = _request(db_session, _user(db_session, f"r{index}@exemple.fr"), tcn)
        request.status, request.created_at = status, created
        request.decided_at = created if status == STATUS_REJECTED else None
    db_session.flush()

    assert repo.count_rejected_before(db_session, cutoff) == 1
    assert repo.count_pending_before(db_session, cutoff) == 1
    assert repo.delete_rejected_before(db_session, cutoff) == 1
    assert repo.delete_pending_before(db_session, cutoff) == 1
    assert repo.count_pending(db_session, tcn.id) == 1
