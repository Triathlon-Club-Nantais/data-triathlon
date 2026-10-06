"""Épreuves solo laissées à côté de leur jumelle relais (#1195, #1197)."""
from datetime import date

from app.models.admin_action_log import AdminActionLog
from app.repositories import (
    athlete_repository,
    course_repository,
    participation_repository,
    user_repository,
)
from app.services import relay_twin_cleanup

URL = "https://www.prolivesport.fr/index.php?eventId=1082&race=TREP"
JOUR = date(2025, 6, 22)
NOM = "Triathlon Audencia La Baule 2025 - TREP"


def _epreuve(db, *, is_relay, name=NOM, url=URL):
    return course_repository.get_or_create(
        db, name=name, event_date=JOUR, event_type="triathlon-s", source_url=url,
        provider="prolivesport", is_relay=is_relay,
    )


def _inscrit(db, course, bib, nom):
    athlete = athlete_repository.get_or_create(db, nom=nom, prenom="")
    participation_repository.create(db, athlete_id=athlete.id, course_id=course.id, bib_number=bib)


def test_a_solo_course_fully_covered_by_its_relay_twin_is_listed(db_session):
    solo = _epreuve(db_session, is_relay=False)
    relais = _epreuve(db_session, is_relay=True)
    for bib, nom in (("1", "TEAM MARRIERE"), ("2", "MAZARS 1")):
        _inscrit(db_session, solo, bib, nom)
        _inscrit(db_session, relais, bib, nom)
    _inscrit(db_session, relais, "3", "RSM 1")
    db_session.flush()

    assert [(c.course_id, c.covered_by) for c in relay_twin_cleanup.find_superseded(db_session)] == [
        (solo.id, relais.id)
    ]


def test_a_team_found_only_on_the_solo_course_keeps_it(db_session):
    """Avant le rescrape, 18 équipes de La Baule n'existaient que sur l'épreuve solo."""
    solo = _epreuve(db_session, is_relay=False)
    relais = _epreuve(db_session, is_relay=True)
    _inscrit(db_session, solo, "1", "MAZARS 1")
    _inscrit(db_session, relais, "1", "MAZARS 1")
    _inscrit(db_session, solo, "9", "ESATCO LANDAS 1")
    db_session.flush()

    assert relay_twin_cleanup.find_superseded(db_session) == []


def test_courses_under_other_urls_or_names_are_not_twins(db_session):
    solo = _epreuve(db_session, is_relay=False)
    autre_url = _epreuve(db_session, is_relay=True, url=URL.replace("TREP", "TRGP"))
    autre_nom = _epreuve(db_session, is_relay=True, name=f"{NOM} bis")
    for course in (solo, autre_url, autre_nom):
        _inscrit(db_session, course, "1", "MAZARS 1")
    db_session.flush()

    assert relay_twin_cleanup.find_superseded(db_session) == []


def test_purge_deletes_the_solo_twin_and_logs_the_gesture(db_session):
    auteur = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    solo = _epreuve(db_session, is_relay=False)
    relais = _epreuve(db_session, is_relay=True)
    _inscrit(db_session, solo, "1", "MAZARS 1")
    _inscrit(db_session, relais, "1", "MAZARS 1")
    db_session.flush()

    supprimees = relay_twin_cleanup.purge_superseded(db_session, user_id=auteur.id)

    assert [c.course_id for c in supprimees] == [solo.id]
    assert course_repository.get(db_session, solo.id) is None
    assert course_repository.get(db_session, relais.id) is not None
    journal = db_session.query(AdminActionLog).filter_by(entity_id=solo.id).one()
    assert journal.action == "course.delete"
