from datetime import date

from app.repositories import course_repository


def test_get_or_create_dedups_on_identity(db_session):
    c1 = course_repository.get_or_create(
        db_session,
        name="Triathlon de Nantes",
        event_date=date(2026, 5, 16),
        event_type="triathlon-m",
        provider="klikego",
    )
    c2 = course_repository.get_or_create(
        db_session,
        name="Triathlon de Nantes",
        event_date=date(2026, 5, 16),
        event_type="triathlon-m",
        provider="klikego",
    )
    assert c1.id == c2.id


def test_different_event_type_is_distinct_course(db_session):
    c1 = course_repository.get_or_create(
        db_session, name="Tri X", event_date=date(2026, 5, 16), event_type="triathlon-s"
    )
    c2 = course_repository.get_or_create(
        db_session, name="Tri X", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    assert c1.id != c2.id
