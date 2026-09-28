"""Épreuves timepulse d'avant #674 remplacées par leurs parcours qualifiés (#1004)."""
from datetime import date

from app.models.admin_action_log import AdminActionLog
from app.repositories import (
    athlete_repository,
    course_repository,
    participation_repository,
    user_repository,
)
from app.services import timepulse_cleanup

URL = "https://timepulse.fr/epreuves/resultats/3054"
JOUR = date(2025, 5, 4)


def _epreuve(db, name, *, url=URL, provider="timepulse"):
    return course_repository.get_or_create(
        db, name=name, event_date=JOUR, event_type="duathlon-s", source_url=url, provider=provider
    )


def _inscrit(db, course, bib, nom):
    athlete = athlete_repository.get_or_create(db, nom=nom, prenom="Test")
    participation_repository.create(db, athlete_id=athlete.id, course_id=course.id, bib_number=bib)


def _auteur(db):
    user = user_repository.create(db, email="admin@exemple.fr", display_name="Admin")
    db.flush()
    return user


def test_an_unqualified_course_fully_covered_by_its_qualified_courses_is_listed(db_session):
    ancienne = _epreuve(db_session, "DUATHLON COUERON")
    _inscrit(db_session, ancienne, "1", "ALPHA")
    _inscrit(db_session, ancienne, "2", "BRAVO")
    # Entrée fantôme sans nom (#784) : le scraper l'ignore désormais.
    _inscrit(db_session, ancienne, "3", "")
    solo = _epreuve(db_session, "DUATHLON COUERON - Duathlon S")
    relais = _epreuve(db_session, "DUATHLON COUERON - Duathlon S Relais")
    _inscrit(db_session, solo, "1", "ALPHA")
    _inscrit(db_session, relais, "2", "BRAVO")
    db_session.flush()

    remplacees = timepulse_cleanup.find_superseded(db_session)

    assert [(c.course_id, sorted(c.covered_by)) for c in remplacees] == [
        (ancienne.id, sorted([solo.id, relais.id]))
    ]


def test_a_course_with_a_named_bib_found_nowhere_else_is_never_listed(db_session):
    ancienne = _epreuve(db_session, "DUATHLON COUERON")
    _inscrit(db_session, ancienne, "1", "ALPHA")
    _inscrit(db_session, ancienne, "9", "ORPHELIN")
    solo = _epreuve(db_session, "DUATHLON COUERON - Duathlon S")
    _inscrit(db_session, solo, "1", "ALPHA")
    db_session.flush()

    assert timepulse_cleanup.find_superseded(db_session) == []


def test_only_timepulse_courses_sharing_the_url_are_considered(db_session):
    ancienne = _epreuve(db_session, "DUATHLON COUERON", url="https://www.klikego.com/resultats/x/1")
    _inscrit(db_session, ancienne, "1", "ALPHA")
    autre = _epreuve(db_session, "DUATHLON COUERON - Duathlon S", url="https://timepulse.fr/epreuves/resultats/9")
    _inscrit(db_session, autre, "1", "ALPHA")
    db_session.flush()

    assert timepulse_cleanup.find_superseded(db_session) == []


def test_purge_deletes_the_superseded_course_and_logs_the_gesture(db_session):
    auteur = _auteur(db_session)
    ancienne = _epreuve(db_session, "DUATHLON COUERON")
    _inscrit(db_session, ancienne, "1", "ALPHA")
    solo = _epreuve(db_session, "DUATHLON COUERON - Duathlon S")
    _inscrit(db_session, solo, "1", "ALPHA")
    db_session.flush()

    supprimees = timepulse_cleanup.purge_superseded(db_session, user_id=auteur.id)

    assert [c.course_id for c in supprimees] == [ancienne.id]
    assert course_repository.get(db_session, ancienne.id) is None
    assert course_repository.get(db_session, solo.id) is not None
    journal = db_session.query(AdminActionLog).filter_by(entity_id=ancienne.id).one()
    assert journal.action == "course.delete"
