"""Athlete creation under concurrent imports (#981, epic #1146): two sessions.

Only PostgreSQL shows the behaviour; these tests run in the `backend-postgres`
CI job (`TEST_POSTGRES_URL`).
"""
import threading
import time

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import DomainError
from app.models.athlete import Athlete
from app.repositories import athlete_repository, user_repository
from app.services import admin_actions


@pytest.fixture
def other_session(db_session):
    if db_session.get_bind().dialect.name != "postgresql":
        pytest.skip("concurrency: PostgreSQL only")
    session = sessionmaker(bind=db_session.get_bind())()
    # A thread stuck on a lock must fail the test, not hang the CI job at teardown.
    session.execute(text("SET lock_timeout = '10s'"))
    yield session
    session.rollback()
    session.close()


def _fields(run: int, spelling: str) -> list[dict]:
    return [{"nom": f"NEUF{run}X{i:03d}", "prenom": spelling} for i in range(300)]


def _backend_pid(session) -> int:
    return session.scalar(select(func.pg_backend_pid()))


def _wait_until_blocked(observer, pid: int) -> None:
    """Bounded wait until backend `pid` waits on a lock, so the test really
    covers an INSERT that conflicts with an uncommitted row."""
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        waiting = observer.scalar(
            text("SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid"), {"pid": pid}
        )
        if waiting == "Lock":
            return
        time.sleep(0.02)
    pytest.fail("the second transaction never waited on the first one")


def _run(target) -> tuple[threading.Thread, list[BaseException]]:
    errors: list[BaseException] = []

    def guarded():
        try:
            target()
        except BaseException as exc:  # noqa: BLE001 — reported to the main thread
            errors.append(exc)

    thread = threading.Thread(target=guarded)
    thread.start()
    return thread, errors


def _count(session, run: int) -> int:
    return session.scalar(select(func.count()).select_from(Athlete).where(Athlete.nom.like(f"NEUF{run}X%")))


@pytest.mark.parametrize("run", range(10))
def test_an_insert_waits_for_the_uncommitted_one_then_finds_its_records(db_session, other_session, run):
    first, inserted = athlete_repository.create_batch(db_session, _fields(run, "Léo"))
    assert len(inserted) == 300
    pid = _backend_pid(other_session)
    second: list[Athlete] = []
    second_inserted: set[int] = set()

    def concurrent():
        athletes, ids = athlete_repository.create_batch(other_session, _fields(run, "Leo"))
        second.extend(athletes)
        second_inserted.update(ids)
        other_session.commit()

    thread, errors = _run(concurrent)
    observer = sessionmaker(bind=db_session.get_bind())()
    try:
        _wait_until_blocked(observer, pid)
    finally:
        observer.close()
    db_session.commit()
    thread.join(timeout=30)

    assert not thread.is_alive()
    assert errors == []
    assert sorted(a.id for a in second) == sorted(a.id for a in first)
    assert second_inserted == set()
    assert _count(db_session, run) == 300


def test_two_imports_inserting_the_same_runners_in_opposite_orders_do_not_deadlock(db_session, other_session):
    """Les lignes partent triées par clé : deux épreuves qui listent les mêmes
    inconnus dans des ordres inverses prennent leurs verrous dans le même ordre."""
    run = 99
    forward = _fields(run, "Paul")
    barrier = threading.Barrier(2)
    results: dict[str, list[Athlete]] = {}

    def insert(session, fields, label):
        barrier.wait(timeout=10)
        results[label] = athlete_repository.create_batch(session, fields)[0]
        session.commit()

    thread, errors = _run(lambda: insert(other_session, list(reversed(forward)), "reverse"))
    insert(db_session, forward, "forward")
    thread.join(timeout=30)

    assert not thread.is_alive()
    assert errors == []
    assert _count(db_session, run) == 300


def test_resolution_holds_the_record_against_a_merge(db_session, other_session):
    """`FOR KEY SHARE` : une fusion ne supprime pas une fiche qu'un import vient de résoudre."""
    [athlete], _ = athlete_repository.create_batch(db_session, [{"nom": "TENU", "prenom": "Paul"}])
    db_session.commit()

    athlete_repository.get_by_identity_keys_batch(db_session, [("tenu", "paul")])

    with pytest.raises(OperationalError):
        other_session.execute(select(Athlete).where(Athlete.id == athlete.id).with_for_update(nowait=True))
    db_session.rollback()


def test_resolution_does_not_block_a_club_update(db_session, other_session):
    [athlete], _ = athlete_repository.create_batch(db_session, [{"nom": "CLUB", "prenom": "Libre"}])
    db_session.commit()

    athlete_repository.get_by_identity_keys_batch(db_session, [("club", "libre")])

    other_session.execute(text("SET LOCAL lock_timeout = '1s'"))
    other_session.execute(update(Athlete).where(Athlete.id == athlete.id).values(club="NOUVEAU"))
    other_session.commit()
    db_session.rollback()


def test_an_admin_rename_of_a_record_held_by_an_import_is_refused_quickly(db_session, other_session):
    [athlete], _ = athlete_repository.create_batch(db_session, [{"nom": "TENU", "prenom": "Lea"}])
    admin = user_repository.create(db_session, email="admin@exemple.fr")
    db_session.commit()

    athlete_repository.get_by_identity_keys_batch(db_session, [("tenu", "lea")])

    started = time.monotonic()
    with pytest.raises(DomainError) as refused:
        admin_actions.update_athlete(
            other_session, athlete_id=athlete.id, champs={"nom": "TENUE"}, user_id=admin.id
        )
    assert refused.value.status_code == 409
    assert time.monotonic() - started < 9
    db_session.rollback()


def test_a_merge_waits_for_an_import_then_moves_its_new_results(db_session, other_session):
    """T043 : l'import résout B et y rattache un résultat ; la fusion de B dans A
    attend son commit, puis déplace aussi ce résultat. Aucune clé étrangère violée."""
    from datetime import date

    from app.models.participation import Participation
    from app.repositories import course_repository, participation_repository
    from app.services import athlete_merge

    (kept, absorbed), _ = athlete_repository.create_batch(
        db_session, [{"nom": "GARDEE", "prenom": "Ana"}, {"nom": "ABSORBEE", "prenom": "Ana"}]
    )
    admin = user_repository.create(db_session, email="fusion@exemple.fr")
    course = course_repository.get_or_create(
        db_session, name="Concurrence", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    db_session.commit()
    kept_id, absorbed_id, admin_id = kept.id, absorbed.id, admin.id

    athlete_repository.get_by_identity_keys_batch(db_session, [("absorbee", "ana")])
    result = participation_repository.create(
        db_session, athlete_id=absorbed_id, course_id=course.id, bib_number="1", status="finisher"
    )
    pid = _backend_pid(other_session)

    def merge():
        athlete_merge.merge_athletes(other_session, kept_id=kept_id, absorbed_id=absorbed_id, user_id=admin_id)
        other_session.commit()

    thread, errors = _run(merge)
    observer = sessionmaker(bind=db_session.get_bind())()
    try:
        _wait_until_blocked(observer, pid)
    finally:
        observer.close()
    db_session.commit()
    thread.join(timeout=30)

    assert not thread.is_alive()
    assert errors == []
    db_session.expire_all()
    assert db_session.get(Participation, result.id).athlete_id == kept_id
    assert db_session.get(Athlete, absorbed_id) is None
