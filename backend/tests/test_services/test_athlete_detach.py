"""Detach results of a record onto a new homonym record (#1209)."""
from datetime import date

import pytest

from app.core.exceptions import DomainError, NotFoundError
from app.models.admin_action_log import AdminActionLog
from app.models.athlete import Athlete
from app.models.participation import Participation
from app.repositories import (
    course_repository,
    ignored_athlete_pair_repository,
    participation_repository,
    user_repository,
)
from app.services import athlete_detach


@pytest.fixture
def admin(db_session):
    return user_repository.create(db_session, email="admin@exemple.fr")


def _course(db, name):
    return course_repository.get_or_create(db, name=name, event_date=date(2026, 5, 16), event_type="triathlon-m")


@pytest.fixture
def shared(db_session):
    """Une fiche qui porte les résultats de deux personnes du même nom."""
    athlete = Athlete(nom="MARTIN", prenom="Thomas", gender="M", club="Triathlon Club Nantais")
    db_session.add(athlete)
    db_session.flush()
    results = [
        participation_repository.create(
            db_session, athlete_id=athlete.id, course_id=_course(db_session, name).id, club=club, bib_number=bib
        )
        for name, club, bib in (
            ("Tri Nantes", "Triathlon Club Nantais", "1"),
            ("Tri Vendôme", "Vendôme Triathlon", "2"),
            ("Tri Blois", "Vendôme Triathlon", "3"),
        )
    ]
    return athlete, results


def test_detached_results_move_to_a_new_homonym_judged_distinct(db_session, admin, shared):
    athlete, (nantes, vendome, blois) = shared

    created = athlete_detach.detach_participations(
        db_session, athlete_id=athlete.id, participation_ids=[vendome.id, blois.id], user_id=admin.id
    )

    assert (created.nom, created.prenom, created.homonym_rank) == ("MARTIN", "Thomas", 1)
    assert created.club == "Vendôme Triathlon"
    assert {p.id for p in db_session.query(Participation).filter_by(athlete_id=created.id)} == {vendome.id, blois.id}
    assert db_session.get(Participation, nantes.id).athlete_id == athlete.id
    assert all(db_session.get(Participation, p.id).athlete_locked for p in (vendome, blois))
    assert ignored_athlete_pair_repository.exists(db_session, athlete_id_a=athlete.id, athlete_id_b=created.id)
    [log] = db_session.query(AdminActionLog).filter_by(action="athlete.detach").all()
    assert log.payload == {"from_athlete_id": athlete.id, "to_athlete_id": created.id,
                           "participation_ids": [vendome.id, blois.id]}


def test_detaching_keeps_the_tcn_counting_right_on_both_records(db_session, admin, shared):
    athlete, (nantes, vendome, _) = shared

    athlete_detach.detach_participations(
        db_session, athlete_id=athlete.id, participation_ids=[vendome.id], user_id=admin.id
    )

    assert db_session.get(Participation, nantes.id).counts_for_tcn is True
    assert db_session.get(Participation, vendome.id).counts_for_tcn is False


def test_detaching_refuses_to_empty_the_record_or_take_a_foreign_result(db_session, admin, shared):
    athlete, results = shared
    other = Athlete(nom="DUPONT", prenom="Jean")
    db_session.add(other)
    db_session.flush()
    foreign = participation_repository.create(
        db_session, athlete_id=other.id, course_id=_course(db_session, "Tri X").id
    )

    with pytest.raises(DomainError):
        athlete_detach.detach_participations(
            db_session, athlete_id=athlete.id, participation_ids=[p.id for p in results], user_id=admin.id
        )
    with pytest.raises(DomainError):
        athlete_detach.detach_participations(
            db_session, athlete_id=athlete.id, participation_ids=[foreign.id], user_id=admin.id
        )
    with pytest.raises(DomainError):
        athlete_detach.detach_participations(db_session, athlete_id=athlete.id, participation_ids=[], user_id=admin.id)
    with pytest.raises(NotFoundError):
        athlete_detach.detach_participations(db_session, athlete_id=99999, participation_ids=[1], user_id=admin.id)
    with pytest.raises(NotFoundError):
        athlete_detach.detach_participations(
            db_session, athlete_id=athlete.id, participation_ids=[99999], user_id=admin.id
        )
