"""Accès données des réclamations de résultat (#1637)."""
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.time import utcnow
from app.models.participation import Participation
from app.models.result_claim import STATUS_PENDING, STATUS_REJECTED, ResultClaim
from app.repositories.dialect import dialect_insert


def get_for_user(db: Session, user_id: int, claim_id: int) -> ResultClaim | None:
    return db.scalar(select(ResultClaim).where(ResultClaim.id == claim_id, ResultClaim.user_id == user_id))


def get_for_participation(db: Session, user_id: int, participation_id: int) -> ResultClaim | None:
    return db.scalar(
        select(ResultClaim).where(ResultClaim.user_id == user_id, ResultClaim.participation_id == participation_id)
    )


def delete_for_user(db: Session, user_id: int) -> None:
    db.execute(delete(ResultClaim).where(ResultClaim.user_id == user_id))


def get_pending(db: Session, claim_id: int) -> ResultClaim | None:
    """Verrouillée (`FOR UPDATE`) : deux décisions simultanées n'en font qu'une."""
    return db.scalar(
        select(ResultClaim)
        .where(ResultClaim.id == claim_id, ResultClaim.status == STATUS_PENDING)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def count_pending_for_user(db: Session, user_id: int) -> int:
    return db.scalar(
        select(func.count(ResultClaim.id)).where(ResultClaim.user_id == user_id, ResultClaim.status == STATUS_PENDING)
    ) or 0


def replace_pending(db: Session, *, user_id: int, participation_id: int) -> ResultClaim:
    """La réclamation en attente de ce compte sur ce résultat, remise en attente si refusée."""
    values = {"status": STATUS_PENDING, "created_at": utcnow(), "decided_at": None}
    db.flush()
    db.execute(
        dialect_insert(db)(ResultClaim)
        .values(user_id=user_id, participation_id=participation_id, **values)
        .on_conflict_do_update(index_elements=[ResultClaim.user_id, ResultClaim.participation_id], set_=values)
    )
    return db.scalars(
        select(ResultClaim)
        .where(ResultClaim.user_id == user_id, ResultClaim.participation_id == participation_id)
        .execution_options(populate_existing=True)
    ).one()


def list_for_user(db: Session, user_id: int) -> list[ResultClaim]:
    return list(db.scalars(select(ResultClaim).where(ResultClaim.user_id == user_id).order_by(ResultClaim.id)))


def list_pending(db: Session) -> list[ResultClaim]:
    return list(db.scalars(
        select(ResultClaim)
        # Jointure : une réclamation dont le résultat a disparu sans cascade (SQLite) n'est pas rendue.
        .join(Participation, Participation.id == ResultClaim.participation_id)
        .options(
            selectinload(ResultClaim.user),
            selectinload(ResultClaim.participation).selectinload(Participation.course),
            selectinload(ResultClaim.participation).selectinload(Participation.athlete),
        )
        .where(ResultClaim.status == STATUS_PENDING)
        .order_by(ResultClaim.created_at, ResultClaim.id)
    ))


def count_pending(db: Session) -> int:
    return db.scalar(select(func.count(ResultClaim.id)).where(ResultClaim.status == STATUS_PENDING)) or 0


def reject(db: Session, claim: ResultClaim, *, now: datetime) -> None:
    claim.status = STATUS_REJECTED
    claim.decided_at = now
    db.flush()


def delete_claim(db: Session, claim: ResultClaim) -> None:
    db.delete(claim)
    db.flush()
