from datetime import date
from types import SimpleNamespace

from app.core.validation import awaiting_validation_clause, is_actionable_pending, validated_clause
from app.models.participation import Participation
from app.repositories import athlete_repository, course_repository, participation_repository


def test_validated_clause_exclut_les_pendantes(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="X", prenom="Y")
    course = course_repository.get_or_create(
        db_session, name="Tri", event_date=date(2026, 1, 1), event_type="triathlon-m"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1",
        is_pending_validation=True,
    )
    validee = participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="2",
        is_pending_validation=False,
    )
    db_session.flush()

    rows = (
        db_session.query(Participation)
        .filter(validated_clause(Participation.is_pending_validation))
        .all()
    )
    assert [p.id for p in rows] == [validee.id]


def test_awaiting_validation_clause_ne_garde_que_les_pendantes_non_refusees(db_session):
    """#1273 : la lecture d'affichage des lignes en attente écarte validées et refusées."""
    athlete = athlete_repository.get_or_create(db_session, nom="X", prenom="Y")
    course = course_repository.get_or_create(
        db_session, name="Tri", event_date=date(2026, 1, 1), event_type="triathlon-m"
    )
    en_attente = participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1",
        is_pending_validation=True,
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="2",
        is_pending_validation=True, is_rejected=True,
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="3",
        is_pending_validation=False,
    )
    db_session.flush()

    rows = (
        db_session.query(Participation)
        .filter(awaiting_validation_clause(Participation.is_pending_validation, Participation.is_rejected))
        .all()
    )
    assert [p.id for p in rows] == [en_attente.id]


def _participation(pending: bool, rejected: bool):
    return SimpleNamespace(is_pending_validation=pending, is_rejected=rejected)


def test_une_participation_pendante_non_rejetee_est_actionnable():
    assert is_actionable_pending(_participation(True, False)) is True


def test_une_participation_validee_n_est_plus_actionnable():
    assert is_actionable_pending(_participation(False, False)) is False


def test_une_participation_rejetee_n_est_plus_actionnable():
    """#437 : le rejet doit bloquer reassign/rename/édition de champs tant
    qu'elle n'est pas d'abord dé-rejetée."""
    assert is_actionable_pending(_participation(True, True)) is False
