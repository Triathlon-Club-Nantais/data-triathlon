"""Accès données pour AthleteOpposition (#334). Ne commite jamais."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.athlete_opposition import AthleteOpposition


def get_by_hash(db: Session, identity_hash: str) -> AthleteOpposition | None:
    return db.scalar(select(AthleteOpposition).where(AthleteOpposition.identity_hash == identity_hash))


def all_hashes(db: Session) -> set[str]:
    """Chargées une fois par import : le filtre teste ensuite chaque ligne en mémoire."""
    return set(db.scalars(select(AthleteOpposition.identity_hash)))


def create(
    db: Session, *, identity_hash: str, requested_on: date, applied_by_user_id: int | None
) -> AthleteOpposition:
    opposition = AthleteOpposition(
        identity_hash=identity_hash, requested_on=requested_on, applied_by_user_id=applied_by_user_id
    )
    db.add(opposition)
    db.flush()
    return opposition


def list_recent(db: Session) -> list[AthleteOpposition]:
    return list(
        db.scalars(
            select(AthleteOpposition)
            .options(joinedload(AthleteOpposition.applied_by))
            .order_by(AthleteOpposition.applied_at.desc(), AthleteOpposition.id.desc())
        )
    )
