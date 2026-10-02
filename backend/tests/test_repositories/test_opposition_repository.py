"""Le registre des oppositions (#334)."""
from datetime import date, datetime

from app.repositories import opposition_repository


def test_an_opposition_is_found_by_its_hash(db_session):
    creee = opposition_repository.create(
        db_session, identity_hash="a" * 64, requested_on=date(2026, 9, 20), applied_by_user_id=None
    )

    assert opposition_repository.get_by_hash(db_session, "a" * 64).id == creee.id
    assert opposition_repository.get_by_hash(db_session, "b" * 64) is None


def test_all_hashes_are_loaded_at_once(db_session):
    for lettre in "ab":
        opposition_repository.create(
            db_session, identity_hash=lettre * 64, requested_on=date(2026, 9, 20), applied_by_user_id=None
        )

    assert opposition_repository.all_hashes(db_session) == {"a" * 64, "b" * 64}


def test_the_list_comes_out_most_recent_first(db_session):
    ancienne = opposition_repository.create(
        db_session, identity_hash="a" * 64, requested_on=date(2026, 1, 2), applied_by_user_id=None
    )
    ancienne.applied_at = datetime(2026, 1, 5)
    recente = opposition_repository.create(
        db_session, identity_hash="b" * 64, requested_on=date(2026, 9, 2), applied_by_user_id=None
    )
    recente.applied_at = datetime(2026, 9, 5)
    db_session.flush()

    assert [o.id for o in opposition_repository.list_recent(db_session)] == [recente.id, ancienne.id]
