"""Reprise des épreuves Challenge déjà importées comme des épreuves (#1008)."""
from datetime import date

from app.models.athlete import Athlete
from app.models.challenge import Challenge
from app.models.course import Course
from app.models.participation import Participation
from app.repositories import user_repository
from app.services import challenge_requalification

DAY = date(2026, 5, 13)


def _seed(db):
    xs = Course(name="E - XS", event_date=DAY, event_type="triathlon-xs")
    m = Course(name="E - M", event_date=DAY, event_type="triathlon-m")
    challenge = Course(name="E - START CHALLENGE (XS - M - L)", event_date=DAY, event_type="triathlon-l")
    db.add_all([xs, m, challenge])
    db.flush()
    for i in range(5):
        athlete = Athlete(nom=f"NOM{i}", prenom="Jean")
        db.add(athlete)
        db.flush()
        for course, bib in ((xs, f"x{i}"), (m, f"m{i}"), (challenge, f"c{i}")):
            db.add(Participation(athlete_id=athlete.id, course_id=course.id, bib_number=bib,
                                 rank_overall=i + 1, total_time="02:00:00"))
    db.flush()
    return xs, m, challenge


def test_dry_run_lists_without_writing(db_session):
    xs, m, challenge = _seed(db_session)
    found = challenge_requalification.requalify(db_session, user_id=None)
    assert [(r.course_id, r.linked_course_ids, r.rows) for r in found] == [
        (challenge.id, sorted([xs.id, m.id]), 5)
    ]
    assert db_session.get(Course, challenge.id) is not None
    assert db_session.query(Challenge).count() == 0


def test_apply_converts_and_deletes_the_course(db_session):
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    xs, m, challenge = _seed(db_session)
    challenge_id = challenge.id
    challenge_requalification.requalify(db_session, user_id=admin.id)
    assert db_session.get(Course, challenge_id) is None
    stored = db_session.query(Challenge).one()
    assert stored.name == "E - START CHALLENGE (XS - M - L)"
    assert len(stored.results) == 5
    assert db_session.query(Athlete).count() == 5


def test_courses_that_fail_the_overlap_test_are_left_alone(db_session):
    lone = Course(name="La Baule - Challenge", event_date=DAY, event_type="triathlon-m", is_relay=True)
    db_session.add(lone)
    db_session.flush()
    athlete = Athlete(nom="SOLO", prenom="Jean")
    db_session.add(athlete)
    db_session.flush()
    db_session.add(Participation(athlete_id=athlete.id, course_id=lone.id, bib_number="1"))
    db_session.flush()
    assert challenge_requalification.requalify(db_session, user_id=None) == []
