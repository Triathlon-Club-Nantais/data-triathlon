"""Private season goals of the claimed athlete (#1373)."""
from datetime import date, datetime

import pytest

from app.core import season
from app.core.exceptions import NotFoundError
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation
from app.models.season_goal import SeasonGoal
from app.models.user import SYSTEM_USER_EMAIL
from app.repositories import participation_repository, user_repository
from app.schemas.season_goal import SeasonGoalWrite
from app.services import season_goals
from app.services.auth import accounts

SEASON = 2025


@pytest.fixture(autouse=True)
def _clock(monkeypatch):
    monkeypatch.setattr(season, "utcnow", lambda: datetime(SEASON, 10, 15, 12, 0, 0))


def _write(**fields) -> SeasonGoalWrite:
    return SeasonGoalWrite.model_construct(**{"event_type": None, "course_id": None, "race_name": None,
                                              "race_date": None, "major": False, **fields})


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
    _result(db_session, athlete, status="DNS", time=None)  # registered, never started: not a race run

    assert participation_repository.athlete_season_count(db_session, athlete.id, SEASON, None) == 3
    assert participation_repository.athlete_season_count(db_session, athlete.id, SEASON, "triathlon-m") == 2


def test_a_time_goal_reports_the_best_time_and_whether_it_is_reached(db_session, lea):
    _result(db_session, db_session.get(Athlete, lea.athlete_id), time="2:35:10")
    missed = season_goals.create(db_session, lea, _write(kind="time", event_type="triathlon-m", target=9000))
    reached = season_goals.create(db_session, lea, _write(kind="time", event_type="triathlon-m", target=9310))

    progress = {p.goal.id: p for p in season_goals.list_with_progress(db_session, lea, SEASON)}

    assert (progress[missed.id].best_time, progress[missed.id].reached) == ("2:35:10", False)
    assert progress[reached.id].reached is True


def test_a_count_goal_reports_the_number_of_races(db_session, lea):
    athlete = db_session.get(Athlete, lea.athlete_id)
    _result(db_session, athlete)
    _result(db_session, athlete, event_type="triathlon-s")
    goal = season_goals.create(db_session, lea, _write(kind="count", event_type=None, target=2))

    (progress,) = season_goals.list_with_progress(db_session, lea, SEASON)

    assert (progress.goal.id, progress.count, progress.reached) == (goal.id, 2, True)


def test_a_goal_needs_a_claimed_athlete(db_session):
    bare = user_repository.create(db_session, email="bare@exemple.fr", display_name="")

    with pytest.raises(season_goals.NoClaimedAthleteError):
        season_goals.create(db_session, bare, _write(kind="count", event_type=None, target=3))


@pytest.mark.parametrize(
    ("kind", "event_type", "target"),
    [("time", None, 9000), ("time", "triathlon-m", 0), ("count", None, -1), ("speed", None, 3), ("count", "nope", 3)],
)
def test_an_inconsistent_goal_is_refused(db_session, lea, kind, event_type, target):
    with pytest.raises(season_goals.InvalidGoalError):
        season_goals.create(db_session, lea, _write(kind=kind, event_type=event_type, target=target))


def test_ten_goals_per_season_at_most(db_session, lea):
    for _ in range(season_goals.MAX_GOALS_PER_SEASON):
        season_goals.create(db_session, lea, _write(kind="count", event_type=None, target=1))

    with pytest.raises(season_goals.TooManyGoalsError):
        season_goals.create(db_session, lea, _write(kind="count", event_type=None, target=1))


def test_the_cap_is_per_season(db_session, lea, monkeypatch):
    for _ in range(season_goals.MAX_GOALS_PER_SEASON):
        season_goals.create(db_session, lea, _write(kind="count", event_type=None, target=1))

    monkeypatch.setattr(season, "utcnow", lambda: datetime(SEASON + 1, 10, 15, 12, 0, 0))
    season_goals.create(db_session, lea, _write(kind="count", event_type=None, target=1))


def test_converting_a_past_goal_to_a_race_respects_the_cap(db_session, lea, monkeypatch):
    old = season_goals.create(db_session, lea, _write(kind="count", event_type=None, target=1))
    monkeypatch.setattr(season, "utcnow", lambda: datetime(SEASON + 1, 10, 15, 12, 0, 0))
    for _ in range(season_goals.MAX_GOALS_PER_SEASON):
        season_goals.create(db_session, lea, _write(kind="count", event_type=None, target=1))

    with pytest.raises(season_goals.TooManyGoalsError):
        season_goals.update(
            db_session, lea, old.id, _write(kind="race", race_name="Lac", race_date=date(SEASON + 2, 5, 1))
        )


def test_only_the_owner_updates_or_deletes(db_session, lea):
    goal = season_goals.create(db_session, lea, _write(kind="count", event_type=None, target=3))
    other = user_repository.create(db_session, email="autre@exemple.fr", display_name="")

    with pytest.raises(NotFoundError):
        season_goals.update(db_session, other, goal.id, _write(kind="count", event_type=None, target=5))
    with pytest.raises(NotFoundError):
        season_goals.delete(db_session, other, goal.id)

    season_goals.update(db_session, lea, goal.id, _write(kind="time", event_type="triathlon-s", target=4000))
    assert (goal.kind, goal.event_type, goal.target) == ("time", "triathlon-s", 4000)
    season_goals.delete(db_session, lea, goal.id)
    assert db_session.get(SeasonGoal, goal.id) is None


def test_goals_go_with_the_account(db_session, lea):
    user_repository.create(db_session, email=SYSTEM_USER_EMAIL, display_name="")  # signs the deletion log
    goal = season_goals.create(db_session, lea, _write(kind="count", event_type=None, target=3))

    accounts.delete_account(db_session, lea, origin="request")

    assert db_session.get(SeasonGoal, goal.id) is None


RACE_DAY = date(2026, 6, 7)


def _race_goal(db, user, **fields):
    return season_goals.create(db, user, _write(kind="race", race_name="Ma course", race_date=RACE_DAY, **fields))


def _progress_of(db, user):
    (progress,) = season_goals.list_with_progress(db, user, SEASON)
    return progress


def test_race_goal_upcoming_then_awaiting(db_session, lea, monkeypatch):
    _race_goal(db_session, lea)
    assert _progress_of(db_session, lea).outcome == "upcoming"
    monkeypatch.setattr(season, "utcnow", lambda: datetime(2026, 6, 8, 12, 0, 0))
    progress = _progress_of(db_session, lea)
    assert (progress.outcome, progress.reached) == ("awaiting_results", False)


def test_race_goal_on_race_day_is_upcoming(db_session, lea, monkeypatch):
    _race_goal(db_session, lea)
    monkeypatch.setattr(season, "utcnow", lambda: datetime(2026, 6, 7, 23, 0, 0))
    assert _progress_of(db_session, lea).outcome == "upcoming"


def test_known_course_goal_closes_on_result(db_session, lea):
    row = _result(db_session, db_session.get(Athlete, lea.athlete_id), day=RACE_DAY)
    season_goals.create(db_session, lea, _write(kind="race", course_id=row.course_id))
    assert _progress_of(db_session, lea).outcome == "reached"


def test_known_course_goal_ignores_other_courses_and_falls_back_on_date_when_deleted(db_session, lea):
    athlete = db_session.get(Athlete, lea.athlete_id)
    mine = _result(db_session, athlete, day=RACE_DAY, time="3:00:00")
    _result(db_session, athlete, day=RACE_DAY, time="2:00:00")
    goal = season_goals.create(db_session, lea, _write(kind="race", course_id=mine.course_id, target=9000))
    progress = _progress_of(db_session, lea)
    assert (progress.outcome, progress.best_time) == ("missed", "3:00:00")
    goal.course_id = None
    db_session.flush()
    progress = _progress_of(db_session, lea)
    assert (progress.outcome, progress.best_time) == ("reached", "2:00:00")


def test_detached_goals_report_their_closed_state(db_session, lea, monkeypatch):
    race = _race_goal(db_session, lea)
    time_goal = season_goals.create(db_session, lea, _write(kind="time", event_type="triathlon-m", target=9000))
    lea.athlete_id = None
    db_session.flush()
    assert {p.goal.id: p.outcome for p in season_goals.list_with_progress(db_session, lea, SEASON)} == {
        race.id: "upcoming", time_goal.id: "upcoming"}
    monkeypatch.setattr(season, "utcnow", lambda: datetime(SEASON + 1, 10, 15, 12, 0, 0))
    assert {p.goal.id: p.outcome for p in season_goals.list_with_progress(db_session, lea, SEASON)} == {
        race.id: "missed", time_goal.id: "missed"}


def test_free_race_goal_closes_by_date(db_session, lea):
    athlete = db_session.get(Athlete, lea.athlete_id)
    _result(db_session, athlete, day=RACE_DAY, time="2:35:10")
    _result(db_session, athlete, day=RACE_DAY, time="2:50:00")
    base = {"event_type": "triathlon-m"}
    season_goals.create(db_session, lea, _write(kind="race", race_name="A", race_date=RACE_DAY, target=9310, **base))
    season_goals.create(db_session, lea, _write(kind="race", race_name="B", race_date=RACE_DAY, target=9000, **base))
    got = {p.goal.race_name: p for p in season_goals.list_with_progress(db_session, lea, SEASON)}
    assert (got["A"].outcome, got["A"].best_time) == ("reached", "2:35:10")
    assert (got["B"].outcome, got["B"].best_time) == ("missed", "2:35:10")


def test_dnf_or_pending_does_not_close(db_session, lea, monkeypatch):
    athlete = db_session.get(Athlete, lea.athlete_id)
    _result(db_session, athlete, day=RACE_DAY, status="DNF", time=None)
    _result(db_session, athlete, day=RACE_DAY, is_pending_validation=True)
    _race_goal(db_session, lea, event_type="triathlon-m")
    monkeypatch.setattr(season, "utcnow", lambda: datetime(2026, 6, 8, 12, 0, 0))
    progress = _progress_of(db_session, lea)
    assert (progress.reached, progress.outcome) == (False, "awaiting_results")


def test_result_without_time_with_target_is_awaiting(db_session, lea):
    _result(db_session, db_session.get(Athlete, lea.athlete_id), day=RACE_DAY, time=None)
    _race_goal(db_session, lea, event_type="triathlon-m", target=9000)
    assert _progress_of(db_session, lea).outcome == "awaiting_results"


def test_past_season_time_goal_is_missed(db_session, lea, monkeypatch):
    season_goals.create(db_session, lea, _write(kind="time", event_type="triathlon-m", target=9000))
    monkeypatch.setattr(season, "utcnow", lambda: datetime(SEASON + 1, 10, 15, 12, 0, 0))
    assert _progress_of(db_session, lea).outcome == "missed"


def test_current_season_unreached_goal_is_upcoming(db_session, lea):
    season_goals.create(db_session, lea, _write(kind="time", event_type="triathlon-m", target=9000))
    assert _progress_of(db_session, lea).outcome == "upcoming"
