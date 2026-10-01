"""Verrous consultatifs (#982, #1024) : deux transactions, deux sessions.

Le comportement concurrent n'existe que sur PostgreSQL : sous SQLite, ces
verrous sont sans effet par construction, et ces tests ne tournent que dans le
job CI `backend-postgres` (`TEST_POSTGRES_URL`).
"""
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.repositories import lock_repository


@pytest.fixture
def autre_session(db_session):
    if db_session.get_bind().dialect.name != "postgresql":
        pytest.skip("verrous consultatifs : PostgreSQL uniquement")
    session = sessionmaker(bind=db_session.get_bind())()
    yield session
    session.rollback()
    session.close()


def test_a_course_lock_refuses_a_second_transaction_until_commit(db_session, autre_session):
    assert lock_repository.try_lock_course(db_session, 42) is True

    assert lock_repository.try_lock_course(autre_session, 42) is False
    assert lock_repository.try_lock_course(autre_session, 43) is True

    db_session.commit()
    autre_session.rollback()
    assert lock_repository.try_lock_course(autre_session, 42) is True


def test_a_wipe_and_a_course_gesture_exclude_each_other(db_session, autre_session):
    assert lock_repository.try_lock_course(db_session, 42) is True

    assert lock_repository.try_lock_all_courses(autre_session) is False

    db_session.commit()
    autre_session.rollback()
    assert lock_repository.try_lock_all_courses(autre_session) is True
    assert lock_repository.try_lock_course(db_session, 7) is False


def test_the_import_url_lock_is_held_until_the_end_of_the_transaction(db_session, autre_session):
    url = "https://www.klikego.com/resultats/event/123"
    lock_repository.lock_import_url(db_session, url)

    tenu = autre_session.scalar(
        select(func.pg_try_advisory_xact_lock(lock_repository._IMPORT_URL, func.hashtext(url)))
    )

    assert tenu is False
    db_session.rollback()


def test_locks_are_a_no_op_outside_postgresql(db_session):
    if db_session.get_bind().dialect.name == "postgresql":
        pytest.skip("SQLite uniquement")

    assert lock_repository.try_lock_course(db_session, 42) is True
    assert lock_repository.try_lock_course(db_session, 42) is True
    assert lock_repository.try_lock_all_courses(db_session) is True
    lock_repository.lock_course(db_session, 42)
    lock_repository.lock_import_url(db_session, "https://x.test")
