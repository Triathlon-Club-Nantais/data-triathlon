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


def test_is_relay_makes_distinct_course(db_session):
    solo = course_repository.get_or_create(
        db_session,
        name="Triathlon de Nantes",
        event_date=date(2026, 5, 16),
        event_type="triathlon-m",
        is_relay=False,
    )
    relais = course_repository.get_or_create(
        db_session,
        name="Triathlon de Nantes",
        event_date=date(2026, 5, 16),
        event_type="triathlon-m",
        is_relay=True,
    )
    assert solo.id != relais.id
    assert solo.is_relay is False
    assert relais.is_relay is True


def test_get_by_identity_discriminates_on_is_relay(db_session):
    course_repository.get_or_create(
        db_session,
        name="Tri Y",
        event_date=date(2026, 6, 1),
        event_type="triathlon-s",
        is_relay=True,
    )
    found_solo = course_repository.get_by_identity(
        db_session, "Tri Y", date(2026, 6, 1), "triathlon-s", is_relay=False
    )
    found_relais = course_repository.get_by_identity(
        db_session, "Tri Y", date(2026, 6, 1), "triathlon-s", is_relay=True
    )
    assert found_solo is None
    assert found_relais is not None
    assert found_relais.is_relay is True
