"""Private season goals of the claimed athlete (#1373)."""
from datetime import date

import pytest

from app.core.exceptions import NotFoundError
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation
from app.models.season_goal import SeasonGoal
from app.models.user import SYSTEM_USER_EMAIL
from app.repositories import participation_repository, user_repository
from app.services import season_goals
from app.services.auth import accounts

SEASON = 2025


def _athlete(db, nom="Martin") -> Athlete:
    athlete = Athlete(nom=nom, prenom="Léa")
    db.add(athlete)
    db.flush()
    return athlete


_NUMBER = iter(range(1, 10_000))


def _result(db, athlete, *, day=date(2026, 6, 7), event_type="triathlon-m", time="2:35:10", **extra):
    course = Course(name=f"Épreuve {next(_NUMBER)}", event_date=day, event_type=event_type,
                    is_relay=extra.pop("course_relay", False), reliability_override=extra.pop("reliable", None))
    db.add(course)
    db.flush()
    row = Participation(course_id=course.id, athlete_id=athlete.id, bib_number=str(course.id), total_time=time,
                        status=extra.pop("status", "finisher"), is_relay=extra.pop("is_relay", False), **extra)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def lea(db_session):
    user = user_repository.create(db_session, email="lea@exemple.fr", display_name="Léa")
    user.athlete_id = _athlete(db_session).id
    db_session.flush()
    return user


def test_best_time_ignores_relays_unreliable_unclassified_pending_and_other_seasons(db_session, lea):
    athlete = db_session.get(Athlete, lea.athlete_id)
    _result(db_session, athlete, time="2:35:10")
    _result(db_session, athlete, time="2:20:00", is_relay=True)
    _result(db_session, athlete, time="2:21:00", reliable=False)
    _result(db_session, athlete, time="2:22:00", status="DNF")
    _result(db_session, athlete, time="2:23:00", is_pending_validation=True)
    _result(db_session, athlete, time="2:24:00", day=date(2025, 6, 1))
    _result(db_session, athlete, time="1:10:00", event_type="triathlon-s")

    times = participation_repository.athlete_season_times(db_session, athlete.id, SEASON, "triathlon-m")

    assert times == ["2:35:10"]


def test_count_includes_relays_and_filters_by_format_when_asked(db_session, lea):
    athlete = db_session.get(Athlete, lea.athlete_id)
    _result(db_session, athlete)
    _result(db_session, athlete, is_relay=True)
    _result(db_session, athlete, event_type="triathlon-s")
    _result(db_session, athlete, is_pending_validation=True)

    assert participation_repository.athlete_season_count(db_session, athlete.id, SEASON, None) == 3
    assert participation_repository.athlete_season_count(db_session, athlete.id, SEASON, "triathlon-m") == 2


def test_a_time_goal_reports_the_best_time_and_whether_it_is_reached(db_session, lea):
    _result(db_session, db_session.get(Athlete, lea.athlete_id), time="2:35:10")
    missed = season_goals.create(db_session, lea, season=SEASON, kind="time", event_type="triathlon-m", target=9000)
    reached = season_goals.create(db_session, lea, season=SEASON, kind="time", event_type="triathlon-m", target=9310)

    progress = {p.goal.id: p for p in season_goals.list_with_progress(db_session, lea, SEASON)}

    assert (progress[missed.id].best_time, progress[missed.id].reached) == ("2:35:10", False)
    assert progress[reached.id].reached is True


def test_a_count_goal_reports_the_number_of_races(db_session, lea):
    athlete = db_session.get(Athlete, lea.athlete_id)
    _result(db_session, athlete)
    _result(db_session, athlete, event_type="triathlon-s")
    goal = season_goals.create(db_session, lea, season=SEASON, kind="count", event_type=None, target=2)

    (progress,) = season_goals.list_with_progress(db_session, lea, SEASON)

    assert (progress.goal.id, progress.count, progress.reached) == (goal.id, 2, True)


def test_a_goal_needs_a_claimed_athlete(db_session):
    bare = user_repository.create(db_session, email="bare@exemple.fr", display_name="")

    with pytest.raises(season_goals.NoClaimedAthleteError):
        season_goals.create(db_session, bare, season=SEASON, kind="count", event_type=None, target=3)


@pytest.mark.parametrize(
    ("kind", "event_type", "target"),
    [("time", None, 9000), ("time", "triathlon-m", 0), ("count", None, -1), ("speed", None, 3), ("count", "nope", 3)],
)
def test_an_inconsistent_goal_is_refused(db_session, lea, kind, event_type, target):
    with pytest.raises(season_goals.InvalidGoalError):
        season_goals.create(db_session, lea, season=SEASON, kind=kind, event_type=event_type, target=target)


def test_ten_goals_per_season_at_most(db_session, lea):
    for _ in range(season_goals.MAX_GOALS_PER_SEASON):
        season_goals.create(db_session, lea, season=SEASON, kind="count", event_type=None, target=1)

    with pytest.raises(season_goals.TooManyGoalsError):
        season_goals.create(db_session, lea, season=SEASON, kind="count", event_type=None, target=1)
    season_goals.create(db_session, lea, season=SEASON + 1, kind="count", event_type=None, target=1)


def test_only_the_owner_updates_or_deletes(db_session, lea):
    goal = season_goals.create(db_session, lea, season=SEASON, kind="count", event_type=None, target=3)
    other = user_repository.create(db_session, email="autre@exemple.fr", display_name="")

    with pytest.raises(NotFoundError):
        season_goals.update(db_session, other, goal.id, kind="count", event_type=None, target=5)
    with pytest.raises(NotFoundError):
        season_goals.delete(db_session, other, goal.id)

    season_goals.update(db_session, lea, goal.id, kind="time", event_type="triathlon-s", target=4000)
    assert (goal.kind, goal.event_type, goal.target) == ("time", "triathlon-s", 4000)
    season_goals.delete(db_session, lea, goal.id)
    assert db_session.get(SeasonGoal, goal.id) is None


def test_goals_go_with_the_account(db_session, lea):
    user_repository.create(db_session, email=SYSTEM_USER_EMAIL, display_name="")  # signs the deletion log
    goal = season_goals.create(db_session, lea, season=SEASON, kind="count", event_type=None, target=3)

    accounts.delete_account(db_session, lea, origin="request")

    assert db_session.get(SeasonGoal, goal.id) is None
