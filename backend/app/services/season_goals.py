"""Objectifs de saison privés de l'athlète rattaché (#1373).

Un objectif appartient à un compte et se lit sur sa fiche rattachée (#1325) :
un temps cible sur un format, ou un nombre d'épreuves. La progression se calcule
à la lecture. Un objectif d'un autre compte est introuvable, jamais interdit :
la réponse ne confirme pas qu'il existe.
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.exceptions import DomainError, NotFoundError
from app.models.season_goal import KIND_COUNT, KIND_TIME, SeasonGoal
from app.models.user import User
from app.repositories import participation_repository, season_goal_repository
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


def _check(kind: str, event_type: str | None, target: int) -> None:
    if kind not in (KIND_TIME, KIND_COUNT) or target <= 0:
        raise InvalidGoalError()
    if kind == KIND_TIME and event_type is None:
        raise InvalidGoalError()
    if event_type is not None and event_type not in CANONICAL_TYPES:
        raise InvalidGoalError()


def create(db: Session, user: User, *, season: int, kind: str, event_type: str | None, target: int) -> SeasonGoal:
    if user.athlete_id is None:
        raise NoClaimedAthleteError()
    _check(kind, event_type, target)
    if season_goal_repository.count_for(db, user.id, season) >= MAX_GOALS_PER_SEASON:
        raise TooManyGoalsError()
    return season_goal_repository.create(
        db, user_id=user.id, season=season, kind=kind, event_type=event_type, target=target
    )


def update(db: Session, user: User, goal_id: int, *, kind: str, event_type: str | None, target: int) -> SeasonGoal:
    goal = season_goal_repository.get_for(db, user.id, goal_id)
    if goal is None:
        raise _not_found()
    _check(kind, event_type, target)
    goal.kind, goal.event_type, goal.target = kind, event_type, target
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


def list_with_progress(db: Session, user: User, season: int) -> list[GoalProgress]:
    goals = season_goal_repository.list_for(db, user.id, season)
    return [_progress(db, user.athlete_id, goal) for goal in goals]


def _progress(db: Session, athlete_id: int | None, goal: SeasonGoal) -> GoalProgress:
    if athlete_id is None:
        return GoalProgress(goal=goal, best_time=None, count=None, reached=False)
    if goal.kind == KIND_TIME:
        times = participation_repository.athlete_season_times(db, athlete_id, goal.season, goal.event_type or "")
        readable = [(seconds, text) for text in times if (seconds := parse_duration(text))]
        best = min(readable, default=None)
        return GoalProgress(
            goal=goal, best_time=best[1] if best else None, count=None,
            reached=best is not None and best[0] <= goal.target,
        )
    count = participation_repository.athlete_season_count(db, athlete_id, goal.season, goal.event_type)
    return GoalProgress(goal=goal, best_time=None, count=count, reached=count >= goal.target)
