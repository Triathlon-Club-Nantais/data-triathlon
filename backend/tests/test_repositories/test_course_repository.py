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


def test_iter_all_filtre_par_provider_et_anciennete(db_session):
    from datetime import timedelta

    from app.core.time import utcnow

    vieux = course_repository.get_or_create(
        db_session, name="Vieux", event_date=date(2025, 1, 1),
        event_type="triathlon-m", provider="klikego",
    )
    vieux.scraped_at = utcnow() - timedelta(days=40)
    frais = course_repository.get_or_create(
        db_session, name="Frais", event_date=date(2026, 1, 1),
        event_type="triathlon-m", provider="timepulse",
    )
    frais.scraped_at = utcnow()
    db_session.flush()

    tous = course_repository.iter_all(db_session)
    assert {c.name for c in tous} == {"Vieux", "Frais"}

    klikego = course_repository.iter_all(db_session, provider="klikego")
    assert {c.name for c in klikego} == {"Vieux"}

    anciens = course_repository.iter_all(db_session, older_than_days=30)
    assert {c.name for c in anciens} == {"Vieux"}
