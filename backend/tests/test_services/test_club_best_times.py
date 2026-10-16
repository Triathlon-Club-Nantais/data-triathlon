"""Club best time per sized format, gender and season (#1588)."""
from datetime import date
from itertools import count

from sqlalchemy import event

from app.repositories import athlete_repository, course_repository, participation_repository
from app.services import club_service

_bibs = count(1)


def _result(
    db, total_time, *, event_type="triathlon-m", day=date(2026, 5, 16), gender="F",
    club="TCN", name=None, course_name=None, course_fields=None, **fields,
):
    athlete = athlete_repository.get_or_create(
        db, nom=name or f"N{next(_bibs)}", prenom="Alex", club="TCN"
    )
    athlete.gender = gender
    course = course_repository.get_or_create(
        db, name=course_name or f"C{next(_bibs)}", event_date=day, event_type=event_type,
        **(course_fields or {}),
    )
    fields.setdefault("status", "finisher")
    participation = participation_repository.create(
        db, athlete_id=athlete.id, course_id=course.id, bib_number=str(next(_bibs)),
        club=club, total_time=total_time, **fields,
    )
    db.flush()
    return participation


def _ids(lines):
    return [line.participation_id for line in lines]


def test_keeps_the_fastest_time_per_format_and_gender(db_session):
    _result(db_session, "02:10:00")
    fastest = _result(db_session, "02:05:30", name="DUPONT")
    man = _result(db_session, "02:20:00", gender="M")

    lines = club_service.get_club_best_times(db_session)

    assert _ids(lines) == [fastest.id, man.id]
    line = lines[0]
    assert line.athlete_name == "Alex DUPONT"
    assert line.gender == "F"
    assert line.event_type == "triathlon-m"
    assert line.total_time == "02:05:30"
    assert line.course_id == fastest.course_id
    assert line.event_date == "2026-05-16"


def test_excludes_what_is_not_a_performance(db_session):
    kept = _result(db_session, "02:30:00")
    _result(db_session, "01:00:00", is_relay=True)
    _result(db_session, "01:00:00", course_fields={"is_relay": True})
    _result(db_session, "01:00:00", is_pending_validation=True)
    _result(db_session, "01:00:00", status="DNF")
    _result(db_session, "01:00:00", status="dsq")
    _result(db_session, "00:00:00")
    _result(db_session, "")
    _result(db_session, "01:00:00", club="Autre club")
    _result(db_session, "01:00:00", gender="")
    unreliable = _result(db_session, "01:00:00")
    unreliable.course.reliability_override = False
    db_session.flush()

    assert _ids(club_service.get_club_best_times(db_session)) == [kept.id]


def test_unknown_reliability_counts(db_session):
    reliable = _result(db_session, "02:00:00")
    reliable.course.is_reliable_computed = True
    unknown = _result(db_session, "01:50:00")
    unknown.course.is_reliable_computed = None
    db_session.flush()

    assert _ids(club_service.get_club_best_times(db_session)) == [unknown.id]


def test_only_sized_formats(db_session):
    _result(db_session, "02:00:00", event_type="triathlon")
    _result(db_session, "00:40:00", event_type="course-a-pied-10k")
    sized = _result(db_session, "01:00:00", event_type="swim-bike-s")

    assert _ids(club_service.get_club_best_times(db_session)) == [sized.id]


def test_tie_goes_to_the_earliest_race(db_session):
    _result(db_session, "02:00:00", day=date(2026, 6, 1))
    first = _result(db_session, "02:00:00", day=date(2026, 5, 1))

    assert _ids(club_service.get_club_best_times(db_session)) == [first.id]


def test_season_filter(db_session):
    _result(db_session, "01:50:00", day=date(2025, 8, 31))
    this_season = _result(db_session, "02:00:00", day=date(2025, 9, 1))

    assert _ids(club_service.get_club_best_times(db_session, season=2025)) == [this_season.id]
    assert club_service.get_club_best_times(db_session, season=2030) == []


def test_federal_only_drops_non_federal_disciplines(db_session, monkeypatch):
    from app.core import counter_scope

    monkeypatch.setattr(counter_scope, "non_federal_disciplines", lambda: frozenset({"duathlon-m"}))
    _result(db_session, "02:00:00", event_type="duathlon-m")
    triathlon = _result(db_session, "02:00:00")

    assert len(club_service.get_club_best_times(db_session)) == 2
    assert _ids(club_service.get_club_best_times(db_session, federal_only=True)) == [triathlon.id]


def test_sorted_by_discipline_then_size_then_gender(db_session):
    tri_m_man = _result(db_session, "02:00:00", gender="M")
    tri_xs = _result(db_session, "00:40:00", event_type="triathlon-xs")
    tri_m_woman = _result(db_session, "02:10:00")
    duathlon = _result(db_session, "02:00:00", event_type="duathlon-l")

    assert _ids(club_service.get_club_best_times(db_session)) == [
        duathlon.id, tri_xs.id, tri_m_woman.id, tri_m_man.id,
    ]


def test_query_count_does_not_grow_with_results(db_session):
    def queries():
        statements = []
        engine = db_session.get_bind()
        listener = lambda *args: statements.append(args[2])  # noqa: E731
        event.listen(engine, "before_cursor_execute", listener)
        try:
            club_service.get_club_best_times(db_session)
        finally:
            event.remove(engine, "before_cursor_execute", listener)
        return len(statements)

    _result(db_session, "02:00:00")
    one = queries()
    _result(db_session, "01:00:00", event_type="triathlon-s")
    _result(db_session, "03:00:00", event_type="triathlon-l", gender="M")

    assert one == queries() == 1
