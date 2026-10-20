"""Objectifs de saison privés de l'athlète rattaché (#1373).

Un objectif appartient à un compte et se lit sur sa fiche rattachée (#1325) :
un temps cible sur un format, un nombre d'épreuves, ou une épreuve cible (connue
ou saisie librement, avec un temps visé facultatif). Un seul objectif par saison
peut être « majeur ». La progression se calcule
à la lecture. Un objectif d'un autre compte est introuvable, jamais interdit :
la réponse ne confirme pas qu'il existe.
"""
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.core import season as season_clock
from app.core.exceptions import DomainError, NotFoundError
from app.core.season import current_season, season_of
from app.models.season_goal import KIND_COUNT, KIND_RACE, KIND_TIME, SeasonGoal
from app.models.user import User
from app.repositories import course_repository, participation_repository, season_goal_repository
from app.schemas.season_goal import SeasonGoalWrite
from app.scrapers.classify import CANONICAL_TYPES
from app.services.mapping import parse_duration

MAX_GOALS_PER_SEASON = 10


class NoClaimedAthleteError(DomainError):
    status_code = 409
    message = "Rattachez d'abord votre fiche athlète (« C'est moi » sur votre fiche) pour vous fixer des objectifs."


class TooManyGoalsError(DomainError):
    status_code = 409
    message = f"Vous avez déjà {MAX_GOALS_PER_SEASON} objectifs pour cette saison."


class InvalidGoalError(DomainError):
    status_code = 422
    message = "Objectif incomplet : un temps cible demande une discipline et un format, et la cible doit être positive."


def _not_found() -> NotFoundError:
    return NotFoundError("Objectif introuvable.")


class InvalidRaceGoalError(InvalidGoalError):
    message = "Épreuve cible incomplète : choisissez une épreuve connue, ou indiquez un nom et une date."


class RaceWithoutDateError(InvalidGoalError):
    message = "Cette épreuve n'a pas de date : indiquez le nom et la date vous même."


class RaceOutsideSeasonError(InvalidGoalError):
    message = "L'épreuve cible doit tomber dans la saison en cours."


class RaceTargetNeedsFormatError(InvalidGoalError):
    message = "Un temps visé sur une épreuve cible demande une discipline et un format."


def _fields(db: Session, data: SeasonGoalWrite) -> dict:
    """Valide `data` et rend les colonnes à écrire ; celles qui ne concernent pas la sorte sont à `None`."""
    event_type, target = data.event_type, data.target
    if data.kind not in (KIND_TIME, KIND_COUNT, KIND_RACE) or (target is not None and target <= 0):
        raise InvalidGoalError()
    if data.kind != KIND_RACE:
        if target is None or (data.kind == KIND_TIME and event_type is None):
            raise InvalidGoalError()
        fields = {"course_id": None, "race_name": None, "race_date": None}
    else:
        course_id, race_name, race_date = data.course_id, (data.race_name or "").strip(), data.race_date
        if course_id is not None:
            course = course_repository.get(db, course_id)
            if course is None:
                raise InvalidRaceGoalError()
            if course.event_date is None:
                raise RaceWithoutDateError()
            race_name, race_date = course.name[:200], course.event_date
            event_type = course.event_type or event_type
        elif not race_name or race_date is None:
            raise InvalidRaceGoalError()
        if season_of(race_date) != current_season():
            raise RaceOutsideSeasonError()
        if target is not None and event_type is None:
            raise RaceTargetNeedsFormatError()
        fields = {"course_id": course_id, "race_name": race_name, "race_date": race_date}
    if event_type is not None and event_type not in CANONICAL_TYPES:
        raise InvalidGoalError()
    return {"kind": data.kind, "event_type": event_type, "target": target, "major": data.major, **fields}


def create(db: Session, user: User, data: SeasonGoalWrite) -> SeasonGoal:
    if user.athlete_id is None:
        raise NoClaimedAthleteError()
    fields = _fields(db, data)
    season = season_of(fields["race_date"]) if data.kind == KIND_RACE else current_season()
    if season_goal_repository.count_for(db, user.id, season) >= MAX_GOALS_PER_SEASON:
        raise TooManyGoalsError()
    goal = season_goal_repository.create(db, user_id=user.id, season=season, **fields)
    if goal.major:
        season_goal_repository.clear_major(db, user.id, season, except_id=goal.id)
    return goal


def update(db: Session, user: User, goal_id: int, data: SeasonGoalWrite) -> SeasonGoal:
    goal = season_goal_repository.get_for(db, user.id, goal_id)
    if goal is None:
        raise _not_found()
    fields = _fields(db, data)
    season = season_of(fields["race_date"]) if data.kind == KIND_RACE else goal.season
    if season != goal.season and season_goal_repository.count_for(db, user.id, season) >= MAX_GOALS_PER_SEASON:
        raise TooManyGoalsError()
    for name, value in fields.items():
        setattr(goal, name, value)
    goal.season = season
    if goal.major:
        season_goal_repository.clear_major(db, user.id, goal.season, except_id=goal.id)
    db.flush()
    return goal


def delete(db: Session, user: User, goal_id: int) -> None:
    goal = season_goal_repository.get_for(db, user.id, goal_id)
    if goal is None:
        raise _not_found()
    season_goal_repository.delete(db, goal)


@dataclass(frozen=True)
class GoalProgress:
    goal: SeasonGoal
    #: Meilleur temps de la saison sur le format (objectif temps), sinon `None`.
    best_time: str | None
    #: Nombre d'épreuves de la saison (objectif nombre), sinon `None`.
    count: int | None
    reached: bool
    outcome: Literal["upcoming", "awaiting_results", "reached", "missed"]


def list_with_progress(db: Session, user: User, season: int) -> list[GoalProgress]:
    goals = season_goal_repository.list_for(db, user.id, season)
    return [_progress(db, user.athlete_id, goal) for goal in goals]


def _closed(goal: SeasonGoal, reached: bool) -> str:
    if reached:
        return "reached"
    return "missed" if goal.season < current_season() else "upcoming"


def _race_progress(db: Session, athlete_id: int, goal: SeasonGoal) -> GoalProgress:
    times = participation_repository.athlete_race_times(
        db, athlete_id, course_id=goal.course_id, event_date=goal.race_date, event_type=goal.event_type
    )
    if not times:
        outcome = "upcoming" if goal.race_date >= season_clock.utcnow().date() else "awaiting_results"
        return GoalProgress(goal=goal, best_time=None, count=None, reached=False, outcome=outcome)
    if goal.target is None:
        return GoalProgress(goal=goal, best_time=None, count=None, reached=True, outcome="reached")
    best = min(((seconds, text) for text in times if text and (seconds := parse_duration(text))), default=None)
    if best is None:
        return GoalProgress(goal=goal, best_time=None, count=None, reached=False, outcome="awaiting_results")
    reached = best[0] <= goal.target
    return GoalProgress(
        goal=goal, best_time=best[1], count=None, reached=reached, outcome="reached" if reached else "missed"
    )


def _progress(db: Session, athlete_id: int | None, goal: SeasonGoal) -> GoalProgress:
    if athlete_id is None:
        if goal.kind == KIND_RACE:
            outcome = "upcoming" if goal.race_date >= season_clock.utcnow().date() else "missed"
        else:
            outcome = _closed(goal, False)
        return GoalProgress(goal=goal, best_time=None, count=None, reached=False, outcome=outcome)
    if goal.kind == KIND_RACE:
        return _race_progress(db, athlete_id, goal)
    if goal.kind == KIND_TIME:
        times = participation_repository.athlete_season_times(db, athlete_id, goal.season, goal.event_type or "")
        readable = [(seconds, text) for text in times if (seconds := parse_duration(text))]
        best = min(readable, default=None)
        reached = best is not None and best[0] <= goal.target
        return GoalProgress(
            goal=goal, best_time=best[1] if best else None, count=None, reached=reached,
            outcome=_closed(goal, reached),
        )
    count = participation_repository.athlete_season_count(db, athlete_id, goal.season, goal.event_type)
    reached = count >= goal.target
    return GoalProgress(goal=goal, best_time=None, count=count, reached=reached, outcome=_closed(goal, reached))
