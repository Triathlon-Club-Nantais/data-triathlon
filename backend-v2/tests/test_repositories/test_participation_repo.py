from datetime import date

from app.repositories import athlete_repo, course_repo, participation_repo


def _setup(db_session):
    athlete = athlete_repo.get_or_create(db_session, nom="DUPONT", prenom="Jean", club="TCN")
    course = course_repo.get_or_create(
        db_session, name="Tri Z", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    return athlete, course


def test_create_and_dedup_by_bib(db_session):
    athlete, course = _setup(db_session)
    participation_repo.create(
        db_session,
        athlete_id=athlete.id,
        course_id=course.id,
        bib_number="42",
        club="TCN",
        total_time="01:59:00",
    )
    assert participation_repo.exists_for_bib(db_session, course.id, "42") is True
    assert participation_repo.exists_for_bib(db_session, course.id, "99") is False
    assert participation_repo.existing_bibs_for_course(db_session, course.id) == {"42"}


def test_list_filters_by_name_and_club(db_session):
    athlete, course = _setup(db_session)
    other = athlete_repo.get_or_create(db_session, nom="MARTIN", prenom="Paul", club="ASPTT")
    participation_repo.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1", club="TCN"
    )
    participation_repo.create(
        db_session, athlete_id=other.id, course_id=course.id, bib_number="2", club="ASPTT"
    )
    db_session.flush()

    by_name = participation_repo.list_participations(db_session, name="dupont")
    assert len(by_name) == 1
    assert by_name[0].athlete.nom == "DUPONT"

    by_club = participation_repo.list_participations(db_session, club="nantais|tcn")
    assert len(by_club) == 1
    assert by_club[0].club == "TCN"
