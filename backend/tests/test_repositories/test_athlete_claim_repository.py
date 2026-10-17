"""Athlete claims, one per account (#1325)."""
from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.athlete import Athlete
from app.models.athlete_claim import STATUS_PENDING, STATUS_REJECTED, AthleteClaim
from app.repositories import athlete_claim_repository, user_repository
from app.repositories.dialect import is_postgres


def _athlete(db, nom="Martin") -> Athlete:
    athlete = Athlete(nom=nom, prenom="Léa")
    db.add(athlete)
    db.flush()
    return athlete


def _user(db, email="lea@exemple.fr"):
    return user_repository.create(db, email=email, display_name="")


def test_one_claim_per_account(db_session):
    user, athlete = _user(db_session), _athlete(db_session)
    db_session.add(AthleteClaim(user_id=user.id, athlete_id=athlete.id, status=STATUS_PENDING))
    db_session.flush()

    with pytest.raises(IntegrityError):
        db_session.add(AthleteClaim(user_id=user.id, athlete_id=athlete.id, status=STATUS_PENDING))
        db_session.flush()


def test_replace_pending_creates_then_replaces_a_pending_or_rejected_claim(db_session):
    user, first, second = _user(db_session), _athlete(db_session), _athlete(db_session, "Durand")

    claim = athlete_claim_repository.replace_pending(db_session, user_id=user.id, athlete_id=first.id)
    assert (claim.athlete_id, claim.status) == (first.id, STATUS_PENDING)

    athlete_claim_repository.reject(db_session, claim, now=datetime(2026, 10, 17))
    again = athlete_claim_repository.replace_pending(db_session, user_id=user.id, athlete_id=second.id)

    assert db_session.query(AthleteClaim).count() == 1
    assert (again.athlete_id, again.status, again.decided_at) == (second.id, STATUS_PENDING, None)


def test_get_for_user_and_delete_for_user(db_session):
    user, athlete = _user(db_session), _athlete(db_session)
    athlete_claim_repository.replace_pending(db_session, user_id=user.id, athlete_id=athlete.id)

    assert athlete_claim_repository.get_for_user(db_session, user.id).athlete_id == athlete.id
    athlete_claim_repository.delete_for_user(db_session, user.id)
    assert athlete_claim_repository.get_for_user(db_session, user.id) is None
    athlete_claim_repository.delete_for_user(db_session, user.id)


def test_list_and_count_pending_oldest_first_without_rejected(db_session):
    athlete = _athlete(db_session)
    newer, older, rejected = _user(db_session, "a@x.fr"), _user(db_session, "b@x.fr"), _user(db_session, "c@x.fr")
    db_session.add_all([
        AthleteClaim(user_id=newer.id, athlete_id=athlete.id, status=STATUS_PENDING, created_at=datetime(2026, 10, 2)),
        AthleteClaim(user_id=older.id, athlete_id=athlete.id, status=STATUS_PENDING, created_at=datetime(2026, 10, 1)),
        AthleteClaim(user_id=rejected.id, athlete_id=athlete.id, status=STATUS_REJECTED),
    ])
    db_session.flush()

    assert [c.user_id for c in athlete_claim_repository.list_pending(db_session)] == [older.id, newer.id]
    assert athlete_claim_repository.count_pending(db_session) == 2


def test_get_pending_ignores_a_rejected_claim(db_session):
    user, athlete = _user(db_session), _athlete(db_session)
    claim = athlete_claim_repository.replace_pending(db_session, user_id=user.id, athlete_id=athlete.id)

    assert athlete_claim_repository.get_pending(db_session, claim.id) is claim
    athlete_claim_repository.reject(db_session, claim, now=datetime(2026, 10, 17))
    assert athlete_claim_repository.get_pending(db_session, claim.id) is None


def test_a_first_claim_survives_a_concurrent_insert(db_session):
    """Review of #1624: a double click on a first claim must not be a 500."""
    user, first, second = _user(db_session), _athlete(db_session), _athlete(db_session, "Durand")
    db_session.add(AthleteClaim(user_id=user.id, athlete_id=first.id, status=STATUS_REJECTED))
    db_session.flush()
    db_session.expunge_all()  # the concurrent row is invisible to the ORM, as in another transaction

    claim = athlete_claim_repository.replace_pending(db_session, user_id=user.id, athlete_id=second.id)

    assert (claim.athlete_id, claim.status) == (second.id, STATUS_PENDING)
    assert db_session.query(AthleteClaim).count() == 1


def test_list_pending_skips_a_claim_whose_athlete_is_gone(db_session):
    """SQLite applies no `ON DELETE CASCADE`: a dangling claim must not break the queue."""
    if is_postgres(db_session):
        pytest.skip("PostgreSQL enforces the foreign key: no dangling claim can exist")
    user = _user(db_session)
    db_session.add(AthleteClaim(user_id=user.id, athlete_id=999_999, status=STATUS_PENDING))
    db_session.flush()

    assert athlete_claim_repository.list_pending(db_session) == []


def test_repoint_and_delete_for_athlete(db_session):
    user, absorbed, kept = _user(db_session), _athlete(db_session), _athlete(db_session, "Durand")
    athlete_claim_repository.replace_pending(db_session, user_id=user.id, athlete_id=absorbed.id)

    athlete_claim_repository.repoint(db_session, from_athlete_id=absorbed.id, to_athlete_id=kept.id)
    assert athlete_claim_repository.get_for_user(db_session, user.id).athlete_id == kept.id

    athlete_claim_repository.delete_for_athlete(db_session, kept.id)
    assert athlete_claim_repository.get_for_user(db_session, user.id) is None
