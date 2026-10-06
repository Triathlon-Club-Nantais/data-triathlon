"""Every counting reader follows `counts_for_tcn`, not the bare label (#1206)."""
from datetime import date

import pytest

from app.core import counter_scope
from app.repositories import (
    athlete_repository,
    course_repository,
    participation_repository,
    tcn_count_repository,
)
from app.schemas.participation import ParticipationOut
from app.services import stats_service


@pytest.fixture
def narbonne_and_nantes(db_session):
    """Same race: a Narbonne athlete written `TCN`, a Nantes athlete written
    `TCN` whose other result says `Triathlon Club Nantais`."""
    counter_scope.load(
        disciplines=counter_scope.non_federal_disciplines(),
        club_labels=counter_scope.tcn_club_labels(),
        ambiguous_club_labels={"tcn"},
    )
    race = course_repository.get_or_create(
        db_session, name="Tri de Narbonne", event_date=date(2026, 5, 18), event_type="triathlon-m"
    )
    other = course_repository.get_or_create(
        db_session, name="Tri de Nantes", event_date=date(2026, 4, 1), event_type="triathlon-m"
    )
    narbonne = athlete_repository.get_or_create(db_session, nom="SUD", prenom="Leo")
    nantes = athlete_repository.get_or_create(db_session, nom="OUEST", prenom="Lea")
    participation_repository.create(
        db_session, athlete_id=narbonne.id, course_id=race.id, bib_number="1", club="TCN",
        status="finisher", rank_overall=1,
    )
    participation_repository.create(
        db_session, athlete_id=nantes.id, course_id=race.id, bib_number="2", club="TCN",
        status="finisher", rank_overall=2,
    )
    participation_repository.create(
        db_session, athlete_id=nantes.id, course_id=other.id, bib_number="1",
        club="Triathlon Club Nantais", status="finisher", rank_overall=5,
    )
    course_repository.recount(db_session, race)
    course_repository.recount(db_session, other)
    tcn_count_repository.recompute_counts_for_tcn(db_session)
    db_session.commit()
    yield race, narbonne, nantes
    counter_scope.reset()


def test_the_club_scope_keeps_only_the_nantes_athlete(db_session, narbonne_and_nantes):
    race, _, nantes = narbonne_and_nantes

    rows = participation_repository.list_participations(
        db_session, club_only=True, page_size=100, course_id=race.id
    )

    assert [r.athlete_id for r in rows] == [nantes.id]


def test_the_course_summary_counts_one_club_result(db_session, narbonne_and_nantes):
    race, _, _ = narbonne_and_nantes

    summary = stats_service.course_summary(db_session, race.id)

    assert summary["tcn_count"] == 1
    clubs = {c["name"]: c for c in summary["clubs"]}
    assert clubs["Triathlon Club Nantais"] == {"name": "Triathlon Club Nantais", "count": 1, "is_tcn": True}
    assert clubs["TCN"] == {"name": "TCN", "count": 1, "is_tcn": False}


def test_the_events_page_and_its_fast_path_agree(db_session, narbonne_and_nantes):
    race, _, _ = narbonne_and_nantes
    db_session.expire_all()

    fast = {i.course_id: i for i in participation_repository.events_page(db_session)["items"]}
    grouped = {
        i.course_id: i
        for i in participation_repository.events_page(db_session, name="o")["items"]
    }

    assert course_repository.get(db_session, race.id).tcn_count == 1
    assert fast[race.id].tcn_count == 1
    assert grouped[race.id].tcn_count == 1


def test_the_badge_reads_the_stored_verdict(db_session, narbonne_and_nantes):
    race, narbonne, nantes = narbonne_and_nantes
    rows = participation_repository.list_participations(
        db_session, page_size=100, course_id=race.id
    )

    badges = {r.athlete_id: ParticipationOut.model_validate(r).is_tcn for r in rows}

    assert badges == {narbonne.id: False, nantes.id: True}
