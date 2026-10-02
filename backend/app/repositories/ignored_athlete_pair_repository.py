"""Accès données pour IgnoredAthletePair (#908). L'existence de la ligne porte la décision."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ignored_athlete_pair import IgnoredAthletePair


def normalized(athlete_id_a: int, athlete_id_b: int) -> tuple[int, int]:
    return (athlete_id_a, athlete_id_b) if athlete_id_a < athlete_id_b else (athlete_id_b, athlete_id_a)


def create(db: Session, *, athlete_id_a: int, athlete_id_b: int, user_id: int) -> IgnoredAthletePair:
    low, high = normalized(athlete_id_a, athlete_id_b)
    ignored = IgnoredAthletePair(athlete_id_low=low, athlete_id_high=high, ignored_by_user_id=user_id)
    db.add(ignored)
    db.flush()
    return ignored


def exists(db: Session, *, athlete_id_a: int, athlete_id_b: int) -> bool:
    low, high = normalized(athlete_id_a, athlete_id_b)
    return db.scalar(
        select(IgnoredAthletePair.id).where(
            IgnoredAthletePair.athlete_id_low == low, IgnoredAthletePair.athlete_id_high == high
        )
    ) is not None


def all_pairs(db: Session) -> set[tuple[int, int]]:
    return set(db.execute(select(IgnoredAthletePair.athlete_id_low, IgnoredAthletePair.athlete_id_high)).tuples())
