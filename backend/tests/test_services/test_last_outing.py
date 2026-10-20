from datetime import date, datetime

import pytest

from app.core import season
from app.repositories import athlete_repository, course_repository, participation_repository
from app.services import stats_service


@pytest.fixture(autouse=True)
def _october_2026(monkeypatch):
    monkeypatch.setattr(season, "utcnow", lambda: datetime(2026, 10, 15, 12, 0, 0))


def _race(db, day, *, nom="DUPONT", club="TCN", event_type="triathlon-m", name=None, pending=False, **ranks):
    athlete = athlete_repository.get_or_create(db, nom=nom, prenom="Jean", club=club)
    course = course_repository.get_or_create(
        db, name=name or f"Tri {day.isoformat()} {event_type}", event_date=day, event_type=event_type
    )
    participation_repository.create(
        db, athlete_id=athlete.id, course_id=course.id, bib_number=nom, club=club,
        status="finisher", is_pending_validation=pending, **ranks,
    )
    db.flush()


def test_no_tcn_race_this_season_gives_none(db_session):
    _race(db_session, date(2026, 6, 1))
    _race(db_session, date(2026, 10, 11), club="ASPTT", nom="AUTRE")
    assert stats_service.get_last_outing(db_session) is None


def test_saturday_and_sunday_form_one_outing(db_session):
    _race(db_session, date(2026, 9, 20), nom="ANCIEN")
    _race(db_session, date(2026, 10, 10), nom="SAMEDI")
    _race(db_session, date(2026, 10, 11), nom="DIMANCHE")
    _race(db_session, date(2026, 10, 11), nom="DIMANCHE2", name="Tri du dimanche bis")

    outing = stats_service.get_last_outing(db_session)

    assert outing == {"end_date": date(2026, 10, 11), "events": 3, "athletes": 3, "podiums": 0, "courses": outing["courses"]}


def test_an_isolated_weekday_race_is_its_own_outing(db_session):
    _race(db_session, date(2026, 10, 10), nom="SAMEDI")
    _race(db_session, date(2026, 10, 14), nom="MERCREDI")

    outing = stats_service.get_last_outing(db_session)

    assert outing["end_date"] == date(2026, 10, 14)
    assert (outing["events"], outing["athletes"]) == (1, 1)


def test_pending_results_are_ignored(db_session):
    _race(db_session, date(2026, 10, 11), nom="VALIDE")
    _race(db_session, date(2026, 10, 12), nom="ATTENTE", pending=True)

    assert stats_service.get_last_outing(db_session)["end_date"] == date(2026, 10, 11)


def test_podiums_match_the_all_ranks_counter(db_session):
    _race(db_session, date(2026, 10, 11), nom="PREMIER", rank_overall=2)
    _race(db_session, date(2026, 10, 11), nom="CATEGORIE", rank_category=1, rank_overall=40)
    _race(db_session, date(2026, 10, 11), nom="LOIN", rank_overall=25)

    outing = stats_service.get_last_outing(db_session)
    stats = stats_service.get_stats(db_session, club_only=True, seasons=[2026])

    assert outing["podiums"] == 2 == stats["rank_counters"]["all"]["podiums"]


def test_federal_only_skips_non_federal_races(db_session):
    _race(db_session, date(2026, 10, 11), nom="TRI")
    _race(db_session, date(2026, 10, 12), nom="TRAIL", event_type="trail")

    assert stats_service.get_last_outing(db_session)["end_date"] == date(2026, 10, 12)
    assert stats_service.get_last_outing(db_session, federal_only=True)["end_date"] == date(2026, 10, 11)


def test_last_outing_in_a_past_season(db_session):
    _race(db_session, date(2026, 5, 10), nom="PRINTEMPS")
    _race(db_session, date(2026, 10, 11), nom="AUTOMNE")

    outing = stats_service.get_last_outing(db_session, seasons=[2025])

    assert outing["end_date"] == date(2026, 5, 10)


def test_last_outing_across_several_seasons_takes_the_latest(db_session):
    _race(db_session, date(2026, 5, 10), nom="PRINTEMPS")
    _race(db_session, date(2026, 10, 11), nom="AUTOMNE")

    outing = stats_service.get_last_outing(db_session, seasons=[2025, 2026])

    assert outing["end_date"] == date(2026, 10, 11)


def _team(db, day, name, size, podiums, event_type="triathlon-m"):
    for i in range(size):
        _race(db, day, nom=f"{name}{i}", name=name, event_type=event_type, rank_overall=1 if i < podiums else 30)


def test_courses_are_sorted_by_tcn_count_then_name(db_session):
    day = date(2026, 10, 11)
    _team(db_session, day, "Petite", 5, 1)
    _team(db_session, day, "Grande", 36, 5)
    _team(db_session, day, "Moyenne", 7, 2, event_type="triathlon-s")
    _team(db_session, day, "Aaa", 5, 0)
    _race(db_session, day, nom="AUTRE", club="ASPTT", name="Sans TCN")
    _team(db_session, date(2026, 9, 1), "Hors fenetre", 9, 0)

    courses = stats_service.get_last_outing(db_session)["courses"]

    assert [(c["name"], c["tcn"], c["podiums"]) for c in courses] == [
        ("Grande", 36, 5), ("Moyenne", 7, 2), ("Aaa", 5, 0), ("Petite", 5, 1),
    ]
    assert courses[1]["event_type"] == "triathlon-s" and isinstance(courses[0]["id"], int)


def test_courses_respect_federal_only_and_seasons(db_session):
    _team(db_session, date(2026, 10, 11), "Tri", 2, 0)
    _team(db_session, date(2026, 10, 12), "Trail", 4, 0, event_type="trail")
    _team(db_session, date(2026, 5, 10), "Printemps", 3, 0)

    assert [c["name"] for c in stats_service.get_last_outing(db_session)["courses"]] == ["Trail", "Tri"]
    assert [c["name"] for c in stats_service.get_last_outing(db_session, federal_only=True)["courses"]] == ["Tri"]
    assert [c["name"] for c in stats_service.get_last_outing(db_session, seasons=[2025])["courses"]] == ["Printemps"]
