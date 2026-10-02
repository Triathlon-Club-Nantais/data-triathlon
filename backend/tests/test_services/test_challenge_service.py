"""Appariement d'un heat Challenge aux épreuves du même jour (#1008)."""
from datetime import date

from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation
from app.repositories import challenge_repository
from app.services import challenge_service
from app.services.challenge_service import ChallengeRow

DAY = date(2026, 5, 13)


def _course(db, name, day=DAY):
    course = Course(name=name, event_date=day, event_type="triathlon-m")
    db.add(course)
    db.flush()
    return course


def _runner(db, nom, *courses):
    athlete = Athlete(nom=nom, prenom="Jean")
    db.add(athlete)
    db.flush()
    for i, course in enumerate(courses):
        db.add(Participation(athlete_id=athlete.id, course_id=course.id, bib_number=f"{nom}-{i}"))
    db.flush()
    return athlete


def _row(nom, prenom="Jean", bib=None, rank=1):
    return ChallengeRow(
        nom=nom, prenom=prenom, bib_number=bib or nom, rank_overall=rank, rank_gender=None,
        rank_category=None, total_time="06:50:33", status="finisher", raw_data={},
    )


def _field(db, size=10):
    xs, m, large = _course(db, "XS"), _course(db, "M"), _course(db, "L")
    names = [f"NOM{i}" for i in range(size)]
    for nom in names:
        _runner(db, nom, xs, m, large)
    return (xs, m, large), names


def test_full_overlap_is_a_challenge_linked_to_every_course(db_session):
    (xs, m, large), names = _field(db_session)
    found = challenge_service.match(db_session, [_row(n) for n in names], event_date=DAY)
    assert found is not None
    assert found.course_ids == sorted([xs.id, m.id, large.id])
    assert len(found.athlete_ids) == 10


def test_ninety_percent_is_enough_less_is_not(db_session):
    _, names = _field(db_session, size=9)
    rows = [_row(n) for n in names] + [_row("INCONNU")]
    assert challenge_service.match(db_session, rows, event_date=DAY) is not None
    rows.append(_row("AUTRE"))
    assert challenge_service.match(db_session, rows, event_date=DAY) is None


def test_athletes_on_a_single_course_do_not_count(db_session):
    solo = _course(db_session, "Relais")
    names = [f"NOM{i}" for i in range(5)]
    for nom in names:
        _runner(db_session, nom, solo)
    assert challenge_service.match(db_session, [_row(n) for n in names], event_date=DAY) is None


def test_other_days_and_challenge_courses_are_not_candidates(db_session):
    other_day = _course(db_session, "XS", day=date(2026, 5, 14))
    m = _course(db_session, "M")
    old_challenge = _course(db_session, "START CHALLENGE")
    for nom in ("A", "B"):
        _runner(db_session, nom, other_day, m, old_challenge)
    assert challenge_service.match(db_session, [_row("A"), _row("B")], event_date=DAY) is None


def test_reversed_names_match(db_session):
    xs, m = _course(db_session, "XS"), _course(db_session, "M")
    _runner(db_session, "DUPONT", xs, m)
    found = challenge_service.match(db_session, [_row("Jean", prenom="DUPONT")], event_date=DAY)
    assert found is not None


def test_link_threshold_keeps_only_courses_with_half_the_field(db_session):
    (xs, m, large), names = _field(db_session)
    extra = _course(db_session, "Kids")
    _runner(db_session, "SEUL", extra, xs)
    rows = [_row(n) for n in names] + [_row("SEUL")]
    found = challenge_service.match(db_session, rows, event_date=DAY)
    assert found is not None
    assert extra.id not in found.course_ids
    assert xs.id in found.course_ids


def test_save_writes_challenge_results_and_links(db_session):
    (xs, m, large), names = _field(db_session, size=3)
    rows = [_row(n, rank=i + 1) for i, n in enumerate(names)]
    found = challenge_service.match(db_session, rows, event_date=DAY)
    challenge = challenge_service.save(
        db_session, name="START CHALLENGE", event_date=DAY, source_url="u", rows=rows, found=found
    )
    assert sorted(link.course_id for link in challenge.links) == sorted([xs.id, m.id, large.id])
    assert sorted(r.rank_overall for r in challenge.results) == [1, 2, 3]
    assert challenge_repository.ranked_counts(db_session, [challenge.id]) == {challenge.id: 3}


def test_unmatched_rows_are_not_saved(db_session):
    _, names = _field(db_session)
    rows = [_row(n) for n in names] + [_row("INCONNU", bib="999")]
    found = challenge_service.match(db_session, rows, event_date=DAY)
    challenge = challenge_service.save(
        db_session, name="C", event_date=DAY, source_url="u", rows=rows, found=found
    )
    assert "999" not in {r.bib_number for r in challenge.results}
