"""Accès données des demandes de rattachement à une fiche athlète (#1325)."""
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, selectinload

from app.core.time import utcnow
from app.models.athlete_claim import STATUS_PENDING, STATUS_REJECTED, AthleteClaim


def get_for_user(db: Session, user_id: int) -> AthleteClaim | None:
    return db.scalar(select(AthleteClaim).where(AthleteClaim.user_id == user_id))


def get_pending(db: Session, claim_id: int) -> AthleteClaim | None:
    return db.scalar(
        select(AthleteClaim).where(AthleteClaim.id == claim_id, AthleteClaim.status == STATUS_PENDING)
    )


def replace_pending(db: Session, *, user_id: int, athlete_id: int) -> AthleteClaim:
    """La demande en attente du compte, qui remplace la précédente quelle qu'elle soit."""
    claim = get_for_user(db, user_id) or AthleteClaim(user_id=user_id)
    claim.athlete_id = athlete_id
    claim.status = STATUS_PENDING
    claim.created_at = utcnow()
    claim.decided_at = None
    db.add(claim)
    db.flush()
    return claim


def reject(db: Session, claim: AthleteClaim, *, now: datetime) -> None:
    claim.status = STATUS_REJECTED
    claim.decided_at = now
    db.flush()


def delete_claim(db: Session, claim: AthleteClaim) -> None:
    db.delete(claim)
    db.flush()


def delete_for_user(db: Session, user_id: int) -> None:
    db.execute(delete(AthleteClaim).where(AthleteClaim.user_id == user_id))


def list_pending(db: Session) -> list[AthleteClaim]:
    return list(db.scalars(
        select(AthleteClaim)
        .options(selectinload(AthleteClaim.user), selectinload(AthleteClaim.athlete))
        .where(AthleteClaim.status == STATUS_PENDING)
        .order_by(AthleteClaim.created_at, AthleteClaim.id)
    ))


def count_pending(db: Session) -> int:
    return db.scalar(select(func.count(AthleteClaim.id)).where(AthleteClaim.status == STATUS_PENDING)) or 0


def repoint(db: Session, *, from_athlete_id: int, to_athlete_id: int) -> int:
    """Reporte sur la fiche conservée les demandes d'une fiche absorbée (fusion)."""
    return db.execute(
        update(AthleteClaim).where(AthleteClaim.athlete_id == from_athlete_id).values(athlete_id=to_athlete_id)
    ).rowcount


def delete_for_athlete(db: Session, athlete_id: int) -> None:
    """Explicite : le `ON DELETE CASCADE` est inerte en SQLite."""
    db.execute(delete(AthleteClaim).where(AthleteClaim.athlete_id == athlete_id))
