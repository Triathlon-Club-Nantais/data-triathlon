"""Tables Challenge (#1008) : identité, liens vers N épreuves, lignes classées."""
from datetime import date

from app.models.athlete import Athlete
from app.models.course import Course
from app.repositories import challenge_repository

DAY = date(2026, 5, 13)


def _course(db, name):
    course = Course(name=name, event_date=DAY, event_type="triathlon-m")
    db.add(course)
    db.flush()
    return course


def _athlete(db, nom):
    athlete = Athlete(nom=nom, prenom="Jean")
    db.add(athlete)
    db.flush()
    return athlete


def test_upsert_is_idempotent_on_name_and_date(db_session):
    first = challenge_repository.upsert(db_session, name="START CHALLENGE", event_date=DAY, source_url="u")
    again = challenge_repository.upsert(db_session, name="START CHALLENGE", event_date=DAY, source_url="u2")
    assert first.id == again.id
    assert again.source_url == "u2"


def test_links_and_results_round_trip(db_session):
    xs, m = _course(db_session, "XS"), _course(db_session, "M")
    athlete = _athlete(db_session, "DUPONT")
    challenge = challenge_repository.upsert(db_session, name="START CHALLENGE", event_date=DAY, source_url="u")
    challenge_repository.replace_links(db_session, challenge, [xs.id, m.id])
    challenge_repository.upsert_result(
        db_session, challenge, athlete_id=athlete.id, bib_number="12",
        rank_overall=1, rank_gender=1, rank_category=None,
        total_time="06:50:33", status="finisher", raw_data={},
    )
    challenge_repository.upsert_result(
        db_session, challenge, athlete_id=athlete.id, bib_number="12",
        rank_overall=2, rank_gender=1, rank_category=None,
        total_time="06:50:34", status="finisher", raw_data={},
    )
    db_session.flush()

    assert [c.id for c in challenge_repository.list_for_course(db_session, xs.id)] == [challenge.id]
    rows = challenge_repository.list_for_athlete(db_session, athlete.id)
    assert [(r.rank_overall, r.total_time) for r in rows] == [(2, "06:50:34")]
    assert challenge_repository.ranked_counts(db_session, [challenge.id]) == {challenge.id: 1}

    challenge_repository.replace_links(db_session, challenge, [m.id])
    assert challenge_repository.list_for_course(db_session, xs.id) == []


def test_delete_all_removes_challenges_and_rows(db_session):
    challenge = challenge_repository.upsert(db_session, name="C", event_date=DAY, source_url="u")
    athlete = _athlete(db_session, "MARTIN")
    challenge_repository.upsert_result(
        db_session, challenge, athlete_id=athlete.id, bib_number="1", rank_overall=1,
        rank_gender=None, rank_category=None, total_time="01:00:00", status="finisher", raw_data={},
    )
    assert challenge_repository.delete_all(db_session) == 1
    assert challenge_repository.list_for_athlete(db_session, athlete.id) == []
