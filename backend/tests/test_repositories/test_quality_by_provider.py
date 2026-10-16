"""`course_repository.quality_by_provider`: reliability per provider (#1366)."""
from sqlalchemy import event

from app.models.course import Course
from app.models.course_source import CourseSource
from app.repositories import course_repository


def _course(db_session, provider: str | None, *, active: bool = True, **columns) -> Course:
    course = Course(name=columns.pop("name", f"Course {provider}"), **columns)
    db_session.add(course)
    db_session.flush()
    if provider is not None:
        db_session.add(
            CourseSource(
                course_id=course.id,
                url=f"https://{provider}/{course.id}",
                provider=provider,
                is_active=active,
            )
        )
        db_session.flush()
    return course


def _by_provider(db_session) -> dict:
    return {row.provider: row for row in course_repository.quality_by_provider(db_session)}


def test_counts_courses_and_unreliable_courses_per_active_provider(db_session):
    _course(db_session, "klikego", is_reliable_computed=True, quality_issues={})
    _course(db_session, "klikego", is_reliable_computed=False, quality_issues={"rank_gap": 3})
    _course(db_session, "klikego")  # never evaluated
    _course(db_session, "wiclax", is_reliable_computed=False, quality_issues={"no_finisher": 1})

    rows = _by_provider(db_session)

    assert (rows["klikego"].course_count, rows["klikego"].unreliable_count) == (3, 1)
    assert (rows["wiclax"].course_count, rows["wiclax"].unreliable_count) == (1, 1)


def test_rows_are_sorted_by_unreliable_count_then_provider(db_session):
    _course(db_session, "b", is_reliable_computed=True)
    _course(db_session, "a", is_reliable_computed=True)
    _course(db_session, "c", is_reliable_computed=False, quality_issues={"rank_gap": 1})

    assert [r.provider for r in course_repository.quality_by_provider(db_session)] == ["c", "a", "b"]


def test_anomalies_count_unreliable_courses_carrying_each_code(db_session):
    _course(db_session, "klikego", is_reliable_computed=False, quality_issues={"rank_gap": 3})
    _course(
        db_session, "klikego", is_reliable_computed=False,
        quality_issues={"rank_gap": 1, "duplicate_bib": 2},
    )

    assert _by_provider(db_session)["klikego"].anomalies == {"rank_gap": 2, "duplicate_bib": 1}


def test_a_human_verdict_wins_over_the_computed_one(db_session):
    _course(
        db_session, "klikego", is_reliable_computed=False, reliability_override=True,
        quality_issues={"rank_gap": 3},
    )
    _course(db_session, "klikego", is_reliable_computed=True, reliability_override=False, quality_issues={})

    row = _by_provider(db_session)["klikego"]

    assert row.unreliable_count == 1
    assert row.anomalies == {}


def test_inactive_sources_and_manual_courses_are_ignored(db_session):
    course = _course(db_session, "klikego", is_reliable_computed=False, quality_issues={"rank_gap": 1})
    db_session.add(
        CourseSource(course_id=course.id, url="https://old/1", provider="wiclax", is_active=False)
    )
    _course(db_session, None, is_reliable_computed=False, quality_issues={"no_participation": 1})
    db_session.flush()

    assert set(_by_provider(db_session)) == {"klikego"}


def test_the_query_count_does_not_grow_with_the_number_of_courses(db_session):
    def queries_for(n: int, marker: str) -> int:
        for i in range(n):
            _course(
                db_session, f"{marker}{i % 3}", name=f"{marker}{i}",
                is_reliable_computed=False, quality_issues={"rank_gap": 1},
            )
        statements: list[str] = []

        def record(conn, cursor, statement, *rest):
            statements.append(statement)

        engine = db_session.get_bind()
        event.listen(engine, "before_cursor_execute", record)
        try:
            course_repository.quality_by_provider(db_session)
        finally:
            event.remove(engine, "before_cursor_execute", record)
        return len(statements)

    assert queries_for(2, "small") == queries_for(30, "large") == 2
