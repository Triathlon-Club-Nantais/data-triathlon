"""Rattrapage du sexe vide des fiches existantes (#1201)."""
from datetime import date

from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation
from app.services import gender_backfill


def _fiche(db, nom, *, gender="", resultats=()):
    athlete = Athlete(nom=nom, prenom="Test", gender=gender)
    db.add(athlete)
    db.flush()
    for i, (category, raw_data) in enumerate(resultats):
        course = Course(name=f"{nom} {i}", event_date=date(2026, 1, 1), event_type="triathlon-s")
        db.add(course)
        db.flush()
        db.add(Participation(athlete_id=athlete.id, course_id=course.id, category=category, raw_data=raw_data))
    db.flush()
    return athlete


def test_plan_reads_the_gender_from_the_category_or_the_source_line(db_session):
    par_categorie = _fiche(db_session, "CAT", resultats=[("V1F", None)])
    par_ligne = _fiche(db_session, "LIGNE", resultats=[("", {"sex": "H"})])

    plan = {p.athlete_id: p.gender for p in gender_backfill.plan(db_session)}

    assert plan == {par_categorie.id: "F", par_ligne.id: "M"}


def test_plan_skips_conflicts_unknowns_and_known_genders(db_session):
    _fiche(db_session, "CONFLIT", resultats=[("V1F", None), ("S2M", None)])
    _fiche(db_session, "EQUIPE", resultats=[("EQX", None)])
    _fiche(db_session, "CONNU", gender="M", resultats=[("V1F", None)])
    _fiche(db_session, "SANS")

    assert gender_backfill.plan(db_session) == []


def test_apply_writes_the_planned_genders(db_session):
    fiche = _fiche(db_session, "CAT", resultats=[("SEF", None), ("V1F", None)])

    applied = gender_backfill.apply(db_session)

    assert [(p.athlete_id, p.gender) for p in applied] == [(fiche.id, "F")]
    db_session.refresh(fiche)
    assert fiche.gender == "F"
