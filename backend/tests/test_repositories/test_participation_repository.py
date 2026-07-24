from datetime import date

from app.models.athlete import Athlete
from app.models.course import Course
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


def test_count_for_course_inclut_les_participations_sans_dossard(db_session):
    athlete, course = _setup(db_session)
    other = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul", club="TCN")
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="42", club="TCN"
    )
    participation_repository.create(
        db_session, athlete_id=other.id, course_id=course.id, bib_number=None, club="TCN"
    )
    db_session.flush()

    assert participation_repository.count_for_course(db_session, course.id) == 2
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


def test_for_stats_filtre_par_saison_unique(db_session):
    athlete, course_2025 = _setup(db_session)  # course "Tri Z" le 2026-05-16 → saison 2025
    c_autre = course_repository.get_or_create(
        db_session, name="Tri Automne", event_date=date(2024, 10, 1), event_type="triathlon-s"
    )  # saison 2024
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course_2025.id, bib_number="1", club="TCN"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=c_autre.id, bib_number="2", club="TCN"
    )
    db_session.flush()

    only_2025 = participation_repository.for_stats(db_session, seasons=[2025])
    assert {p.course.name for p in only_2025} == {"Tri Z"}


def test_for_stats_multi_saisons_non_contigues(db_session):
    athlete, course_2025 = _setup(db_session)  # "Tri Z" 2026-05-16 → saison 2025
    c_2023 = course_repository.get_or_create(
        db_session, name="Tri 2023", event_date=date(2023, 10, 1), event_type="triathlon-s"
    )  # saison 2023
    c_2024 = course_repository.get_or_create(
        db_session, name="Tri 2024", event_date=date(2024, 10, 1), event_type="triathlon-s"
    )  # saison 2024
    for i, c in enumerate((course_2025, c_2023, c_2024)):
        participation_repository.create(
            db_session, athlete_id=athlete.id, course_id=c.id, bib_number=str(i), club="TCN"
        )
    db_session.flush()

    rows = participation_repository.for_stats(db_session, seasons=[2025, 2023])
    assert {p.course.name for p in rows} == {"Tri Z", "Tri 2023"}


def test_events_page_filtre_par_saison_exclut_sans_date(db_session):
    athlete, course_2025 = _setup(db_session)  # "Tri Z" → saison 2025
    c_sans_date = course_repository.get_or_create(
        db_session, name="Sans Date", event_date=None, event_type="triathlon-s"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course_2025.id, bib_number="1", club="TCN"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=c_sans_date.id, bib_number="2", club="TCN"
    )
    db_session.flush()

    page = participation_repository.events_page(db_session, seasons=[2025])
    assert page["total_events"] == 1
    assert page["items"][0].event_name == "Tri Z"


def test_distinct_seasons_compte_et_exclut_epreuves_sans_date(db_session):
    athlete, course_2025 = _setup(db_session)  # saison 2025
    c_2023 = course_repository.get_or_create(
        db_session, name="Tri 2023", event_date=date(2023, 10, 1), event_type="triathlon-s"
    )
    c_sans_date = course_repository.get_or_create(
        db_session, name="Sans Date", event_date=None, event_type="triathlon-s"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course_2025.id, bib_number="1", club="TCN"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=c_2023.id, bib_number="2", club="TCN"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=c_sans_date.id, bib_number="3", club="TCN"
    )
    db_session.flush()

    rows = participation_repository.distinct_seasons(db_session)
    by_year = {r["start_year"]: r for r in rows}
    assert set(by_year) == {2025, 2023}  # épreuve sans date exclue
    assert by_year[2025]["event_count"] == 1
    assert by_year[2025]["participation_count"] == 1


def _athlete_course(db):
    athlete = Athlete(nom="DUPONT", prenom="Jean")
    course = Course(name="Triathlon de Nantes", event_type="triathlon-m", source_url="http://x")
    db.add_all([athlete, course])
    db.flush()
    return athlete, course


def test_update_ecrit_les_champs_fournis(db_session):
    athlete, course = _athlete_course(db_session)
    p = participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id,
        bib_number="1", total_time="01:00:00", status="finisher",
    )

    participation_repository.update(db_session, p, total_time="00:59:00", rank_overall=3)

    refreshed = participation_repository.get(db_session, p.id)
    assert refreshed.total_time == "00:59:00"
    assert refreshed.rank_overall == 3
    assert refreshed.bib_number == "1"  # champ non fourni → inchangé
