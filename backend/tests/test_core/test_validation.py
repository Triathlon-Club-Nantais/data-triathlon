from datetime import date

from app.core.validation import is_pending, validated_clause
from app.models.participation import Participation
from app.repositories import athlete_repository, course_repository, participation_repository


class _Faux:
    def __init__(self, is_pending_validation):
        self.is_pending_validation = is_pending_validation


def test_is_pending_lit_le_booleen():
    assert is_pending(_Faux(True)) is True
    assert is_pending(_Faux(False)) is False


def test_is_pending_traite_none_comme_non_pendant():
    """`is_pending_validation` est NOT NULL en base, mais un objet détaché
    (jamais flushé) peut porter `None` avant que le défaut ne s'applique."""
    assert is_pending(_Faux(None)) is False


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
