from datetime import date

from app.repositories import athlete_repository, course_repository, participation_repository


def _setup(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean", club="TCN")
    course = course_repository.get_or_create(
        db_session, name="Tri Z", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    return athlete, course


def test_create_and_dedup_by_bib(db_session):
    athlete, course = _setup(db_session)
    participation_repository.create(
        db_session,
        athlete_id=athlete.id,
        course_id=course.id,
        bib_number="42",
        club="TCN",
        total_time="01:59:00",
    )
    assert participation_repository.exists_for_bib(db_session, course.id, "42") is True
    assert participation_repository.exists_for_bib(db_session, course.id, "99") is False
    assert participation_repository.existing_bibs_for_course(db_session, course.id) == {"42"}


def test_list_filters_by_name_and_club(db_session):
    athlete, course = _setup(db_session)
    other = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul", club="ASPTT")
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1", club="TCN"
    )
    participation_repository.create(
        db_session, athlete_id=other.id, course_id=course.id, bib_number="2", club="ASPTT"
    )
    db_session.flush()

    by_name = participation_repository.list_participations(db_session, name="dupont")
    assert len(by_name) == 1
    assert by_name[0].athlete.nom == "DUPONT"

    by_club = participation_repository.list_participations(db_session, club="nantais|tcn")
    assert len(by_club) == 1
    assert by_club[0].club == "TCN"


def test_list_filters_by_course_id(db_session):
    athlete, course = _setup(db_session)
    other_course = course_repository.get_or_create(
        db_session, name="Tri Y", event_date=date(2026, 6, 1), event_type="triathlon-s"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1", club="TCN"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=other_course.id, bib_number="1", club="TCN"
    )
    db_session.flush()

    only = participation_repository.list_participations(db_session, course_id=course.id)
    assert len(only) == 1
    assert only[0].course_id == course.id


def test_event_name_filter_substring_sqlite(db_session):
    """En SQLite (dev) la recherche course reste un ILIKE sous-chaîne."""
    athlete, course = _setup(db_session)  # "Tri Z"
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1", club="TCN"
    )
    db_session.flush()

    page = participation_repository.events_page(db_session, event_name="tri")
    assert page["total_events"] == 1
    assert page["items"][0].event_name == "Tri Z"

    empty = participation_repository.events_page(db_session, event_name="marathon")
    assert empty["total_events"] == 0


def test_events_page_pagination_and_sort(db_session):
    athlete, _ = _setup(db_session)
    c_old = course_repository.get_or_create(
        db_session, name="Alpha", event_date=date(2025, 1, 1), event_type="triathlon-s"
    )
    c_new = course_repository.get_or_create(
        db_session, name="Beta", event_date=date(2026, 1, 1), event_type="triathlon-s"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=c_old.id, bib_number="1", club="TCN"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=c_new.id, bib_number="1", club="TCN"
    )
    db_session.flush()

    first = participation_repository.events_page(db_session, page=1, page_size=1)
    assert first["total_events"] == 2
    assert len(first["items"]) == 1
    # Tri par défaut date_desc → la plus récente en premier.
    assert first["items"][0].event_name == "Beta"

    by_name = participation_repository.events_page(db_session, sort="name")
    assert [r.event_name for r in by_name["items"]] == ["Alpha", "Beta"]
