"""Accès données des objectifs de saison (#1373). Toujours par compte : un
objectif ne se lit jamais sans son propriétaire."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.season_goal import SeasonGoal


def create(db: Session, *, user_id: int, season: int, kind: str, event_type: str | None, target: int) -> SeasonGoal:
    goal = SeasonGoal(user_id=user_id, season=season, kind=kind, event_type=event_type, target=target)
    db.add(goal)
    db.flush()
    return goal


def list_for(db: Session, user_id: int, season: int) -> list[SeasonGoal]:
    return list(db.scalars(
        select(SeasonGoal).where(SeasonGoal.user_id == user_id, SeasonGoal.season == season).order_by(SeasonGoal.id)
    ))


def get_for(db: Session, user_id: int, goal_id: int) -> SeasonGoal | None:
    return db.scalar(select(SeasonGoal).where(SeasonGoal.id == goal_id, SeasonGoal.user_id == user_id))


def count_for(db: Session, user_id: int, season: int) -> int:
    return db.scalar(
        select(func.count(SeasonGoal.id)).where(SeasonGoal.user_id == user_id, SeasonGoal.season == season)
    ) or 0


def delete(db: Session, goal: SeasonGoal) -> None:
    db.delete(goal)
    db.flush()
