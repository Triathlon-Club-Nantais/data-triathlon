"""Accès données des objectifs de saison (#1373). Toujours par compte : un
objectif ne se lit jamais sans son propriétaire."""
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.season_goal import SeasonGoal


def create(db: Session, *, user_id: int, **fields) -> SeasonGoal:
    goal = SeasonGoal(user_id=user_id, **fields)
    db.add(goal)
    db.flush()
    return goal


def clear_major(db: Session, user_id: int, season: int, *, except_id: int | None) -> None:
    stmt = update(SeasonGoal).where(
        SeasonGoal.user_id == user_id, SeasonGoal.season == season, SeasonGoal.major.is_(True)
    )
    if except_id is not None:
        stmt = stmt.where(SeasonGoal.id != except_id)
    db.execute(stmt.values(major=False))


def clear_public(db: Session, user_id: int, *, except_id: int) -> None:
    db.execute(
        update(SeasonGoal)
        .where(SeasonGoal.user_id == user_id, SeasonGoal.public.is_(True), SeasonGoal.id != except_id)
        .values(public=False)
    )


def list_for(db: Session, user_id: int, season: int) -> list[SeasonGoal]:
    return list(db.scalars(
        select(SeasonGoal).where(SeasonGoal.user_id == user_id, SeasonGoal.season == season).order_by(SeasonGoal.id)
    ))


def get_public(db: Session, user_id: int, season: int) -> SeasonGoal | None:
    return db.scalar(select(SeasonGoal).where(
        SeasonGoal.user_id == user_id, SeasonGoal.season == season, SeasonGoal.public.is_(True)
    ).order_by(SeasonGoal.id))


def get_for(db: Session, user_id: int, goal_id: int) -> SeasonGoal | None:
    return db.scalar(select(SeasonGoal).where(SeasonGoal.id == goal_id, SeasonGoal.user_id == user_id))


def count_for(db: Session, user_id: int, season: int) -> int:
    return db.scalar(
        select(func.count(SeasonGoal.id)).where(SeasonGoal.user_id == user_id, SeasonGoal.season == season)
    ) or 0


def delete(db: Session, goal: SeasonGoal) -> None:
    db.delete(goal)
    db.flush()
