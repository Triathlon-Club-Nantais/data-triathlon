"""Deux imports concurrents sur des athlètes partagés, sans deadlock (#980).

Le scénario de la reproduction de #980 : deux épreuves multi-heats publient
les mêmes coureurs dans des ordres inverses, sous des clubs différents. Avant
le tri des UPDATE `athletes` par id dans `finalize`, chaque transaction prenait
les verrous de ligne dans l'ordre de son chronométreur, et l'une des deux
échouait sur `40P01`.

`persist_results` est appelé sans le rejeu de `deadlock_retries` : un seul
deadlock fait échouer le test. Un rendez-vous juste avant `apply_updates` fait
partir les deux lots d'UPDATE ensemble : sans lui, le premier import a souvent
commité avant que le second n'écrive, et l'ordre des verrous ne se voit pas.

Le comportement concurrent n'existe que sur PostgreSQL ; ce test ne tourne que
dans le job CI `backend-postgres` (`TEST_POSTGRES_URL`).
"""
import threading
from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation
from app.repositories import athlete_repository
from app.scrapers.base import ScrapedResult
from app.services import import_service

ATHLETES = 400
HEAT_SIZE = ATHLETES // 2
URL_A = "https://www.klikego.com/resultats/event/1"
URL_B = "https://www.wiclax.com/resultats/event/2"


def _results(url: str, provider: str, event: str, club: str, order: list[int]) -> list[ScrapedResult]:
    rows = []
    for heat, indexes in (("XS", order[:HEAT_SIZE]), ("M", order[HEAT_SIZE:])):
        for position, index in enumerate(indexes, start=1):
            rows.append(
                ScrapedResult(
                    source_url=url,
                    provider=provider,
                    athlete_name=f"NOM{index:04d}",
                    athlete_firstname="Prenom",
                    club=club,
                    bib_number=str(position),
                    event_name=f"{event} - {heat}",
                    event_date=date(2026, 6, 1),
                    event_type=f"triathlon-{heat.lower()}",
                    rank_overall=position,
                    total_time="01:00:00",
                )
            )
    return rows


@pytest.fixture
def session_factory(db_session):
    if db_session.get_bind().dialect.name != "postgresql":
        pytest.skip("concurrence de verrous de ligne : PostgreSQL uniquement")
    return sessionmaker(autocommit=False, autoflush=False, bind=db_session.get_bind())


def test_two_multi_heat_imports_sharing_athletes_never_deadlock(
    db_session, session_factory, monkeypatch
):
    db_session.add_all(
        Athlete(nom=f"NOM{index:04d}", prenom="Prenom", club="ANCIEN") for index in range(ATHLETES)
    )
    db_session.commit()

    ascending = list(range(ATHLETES))
    imports = {
        URL_A: _results(URL_A, "klikego", "Triathlon A", "CLUB A", ascending),
        URL_B: _results(URL_B, "wiclax", "Triathlon B", "CLUB B", ascending[::-1]),
    }
    barrier = threading.Barrier(len(imports))
    updates_barrier = threading.Barrier(len(imports))
    errors: dict[str, BaseException] = {}
    apply_updates = athlete_repository.apply_updates

    def apply_updates_together(db, updates):
        updates_barrier.wait(timeout=60)
        apply_updates(db, updates)

    monkeypatch.setattr(athlete_repository, "apply_updates", apply_updates_together)

    def run(url: str) -> None:
        session = None
        try:
            session = session_factory()
            barrier.wait(timeout=60)
            import_service.persist_results(session, url, imports[url])
            session.commit()
        except BaseException as exc:  # noqa: BLE001 — remonté par l'assertion
            errors[url] = exc
            if session is not None:
                session.rollback()
        finally:
            if session is not None:
                session.close()

    threads = [threading.Thread(target=run, args=(url,)) for url in imports]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)

    assert not any(thread.is_alive() for thread in threads)
    assert errors == {}
    db_session.expire_all()
    assert db_session.scalar(select(func.count()).select_from(Course)) == 4
    assert db_session.scalar(select(func.count()).select_from(Participation)) == 2 * ATHLETES
    assert db_session.scalar(select(func.count()).select_from(Athlete)) == ATHLETES
    # Sans changement de club, aucun UPDATE ne prendrait de verrou : le test ne prouverait rien.
    assert set(db_session.scalars(select(Athlete.club).distinct())) <= {"CLUB A", "CLUB B"}
