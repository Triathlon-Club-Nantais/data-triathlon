"""Résultats en attente affichés sur leur épreuve, jamais comptés (#1273).

`list_pending_for_course` liste les lignes en attente non refusées d'une épreuve,
aux mêmes filtres que le classement ; `list_page_for_course` reste le classement
validé. Les comptes restent sous `validated_clause` (`test_pending_exclusion.py`).
"""
from datetime import date

from app.repositories import athlete_repository, course_repository, participation_repository


def _participation(db, course, nom, bib, *, pending=False, rejected=False, club="ASPTT", category="SEM"):
    athlete = athlete_repository.get_or_create(db, nom=nom, prenom="Test", club=club)
    return participation_repository.create(
        db, athlete_id=athlete.id, course_id=course.id, bib_number=bib, club=club,
        category=category, status="finisher", rank_overall=1, total_time="01:00:00",
        is_pending_validation=pending, is_rejected=rejected,
    )


def _epreuve(db, name="Tri Attente"):
    return course_repository.get_or_create(
        db, name=name, event_date=date(2026, 8, 6), event_type="triathlon-m"
    )


def _trio(db):
    """Une épreuve : une validée, deux en attente (ordre de nom inversé), une refusée."""
    course = _epreuve(db)
    validee = _participation(db, course, "ALPHA", "1")
    zulu = _participation(db, course, "ZULU", "2", pending=True)
    bravo = _participation(db, course, "BRAVO", "3", pending=True, club="TCN", category="V2")
    _participation(db, course, "REFUS", "4", pending=True, rejected=True)
    db.flush()
    return course, validee, bravo, zulu


def test_list_pending_for_course_rend_les_en_attente_non_refusees_triees_par_nom(db_session):
    course, _, bravo, zulu = _trio(db_session)
    autre = _epreuve(db_session, name="Autre")
    _participation(db_session, autre, "AILLEURS", "1", pending=True)
    db_session.flush()

    rows = participation_repository.list_pending_for_course(db_session, course.id)

    assert [p.id for p in rows] == [bravo.id, zulu.id]


def test_list_pending_for_course_applique_les_filtres_du_classement(db_session):
    course, _, bravo, zulu = _trio(db_session)

    def ids(**filtres):
        return [p.id for p in participation_repository.list_pending_for_course(db_session, course.id, **filtres)]

    assert ids(q="zulu") == [zulu.id]
    assert ids(club="TCN") == [bravo.id]
    assert ids(category="V2") == [bravo.id]
    assert ids(q="personne") == []


def test_list_pending_for_course_suit_la_portee_club(db_session):
    course, _, bravo, _ = _trio(db_session)
    bravo.counts_for_tcn = True
    db_session.flush()

    rows = participation_repository.list_pending_for_course(db_session, course.id, club_only=True)

    assert [p.id for p in rows] == [bravo.id]


def test_list_page_for_course_ignore_les_lignes_en_attente(db_session):
    course, validee, _, _ = _trio(db_session)

    rows, total = participation_repository.list_page_for_course(db_session, course.id)

    assert total == 1
    assert [p.id for p in rows] == [validee.id]


def test_une_ligne_validee_apres_coup_quitte_les_en_attente_pour_le_classement(db_session):
    course, validee, bravo, zulu = _trio(db_session)
    participation_repository.update(db_session, bravo, is_pending_validation=False)
    db_session.flush()

    rows, total = participation_repository.list_page_for_course(db_session, course.id)

    assert total == 2
    assert {p.id for p in rows} == {validee.id, bravo.id}
    assert [p.id for p in participation_repository.list_pending_for_course(db_session, course.id)] == [zulu.id]
