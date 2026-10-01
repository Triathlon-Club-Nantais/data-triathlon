"""Athlete creation under concurrent imports (#981, epic #1146): two sessions.

Only PostgreSQL shows the behaviour; these tests run in the `backend-postgres`
CI job (`TEST_POSTGRES_URL`).
"""
import threading

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.models.athlete import Athlete
from app.repositories import athlete_repository


@pytest.fixture
def other_session(db_session):
    if db_session.get_bind().dialect.name != "postgresql":
        pytest.skip("concurrency: PostgreSQL only")
    session = sessionmaker(bind=db_session.get_bind())()
    yield session
    session.rollback()
    session.close()


def _fields(run: int, spelling: str) -> list[dict]:
    return [{"nom": f"NEUF{run}X{i}", "prenom": spelling} for i in range(300)]


@pytest.mark.parametrize("run", range(10))
def test_two_imports_creating_the_same_athletes_end_with_one_record_each(db_session, other_session, run):
    """La seconde transaction attend la première, puis retrouve ses fiches."""
    first = athlete_repository.create_batch(db_session, _fields(run, "Léo"))
    errors: list[BaseException] = []
    second: list[Athlete] = []

    def concurrent():
        try:
            second.extend(athlete_repository.create_batch(other_session, _fields(run, "Leo")))
            other_session.commit()
        except BaseException as exc:  # noqa: BLE001 — reported to the main thread
            errors.append(exc)

    thread = threading.Thread(target=concurrent)
    thread.start()
    thread.join(timeout=0.5)
    assert thread.is_alive(), "the second insert must wait for the first transaction"
    db_session.commit()
    thread.join(timeout=30)

    assert errors == []
    assert sorted(a.id for a in second) == sorted(a.id for a in first)
    count = db_session.scalar(
        select(func.count()).select_from(Athlete).where(Athlete.nom.like(f"NEUF{run}X%"))
    )
    assert count == 300


def test_resolution_holds_the_record_against_a_merge(db_session, other_session):
    """`FOR KEY SHARE` : une fusion ne supprime pas une fiche qu'un import vient de résoudre."""
    [athlete] = athlete_repository.create_batch(db_session, [{"nom": "TENU", "prenom": "Paul"}])
    db_session.commit()

    athlete_repository.get_by_identity_keys_batch(db_session, [("tenu", "paul")])

    with pytest.raises(OperationalError):
        other_session.execute(
            select(Athlete).where(Athlete.id == athlete.id).with_for_update(nowait=True)
        )
    db_session.rollback()
