"""Accès données des demandes de rattachement à une fiche athlète (#1325)."""
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, selectinload

from app.core.time import utcnow
from app.models.athlete import Athlete
from app.models.athlete_claim import STATUS_PENDING, STATUS_REJECTED, AthleteClaim
from app.repositories.dialect import dialect_insert


def get_for_user(db: Session, user_id: int) -> AthleteClaim | None:
    return db.scalar(select(AthleteClaim).where(AthleteClaim.user_id == user_id))


def get_pending(db: Session, claim_id: int) -> AthleteClaim | None:
    """Verrouillée (`FOR UPDATE`, sans effet en SQLite) : deux responsables qui
    valident et refusent ensemble ne décident qu'une fois, le second relit une
    demande qui n'est plus en attente."""
    return db.scalar(
        select(AthleteClaim)
        .where(AthleteClaim.id == claim_id, AthleteClaim.status == STATUS_PENDING)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def replace_pending(db: Session, *, user_id: int, athlete_id: int) -> AthleteClaim:
    """La demande en attente du compte, qui remplace la précédente quelle qu'elle soit.

    Un seul `INSERT ... ON CONFLICT (user_id) DO UPDATE` : une lecture préalable
    serait franchie par deux demandes simultanées (double clic), et la seconde
    insertion ferait céder `uq_athlete_claim_user` en 500.
    """
    values = {"athlete_id": athlete_id, "status": STATUS_PENDING, "created_at": utcnow(), "decided_at": None}
    db.flush()
    db.execute(
        dialect_insert(db)(AthleteClaim)
        .values(user_id=user_id, **values)
        .on_conflict_do_update(index_elements=[AthleteClaim.user_id], set_=values)
    )
    return db.scalars(
        select(AthleteClaim).where(AthleteClaim.user_id == user_id).execution_options(populate_existing=True)
    ).one()


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
        # Jointure : une demande dont la fiche a disparu sans cascade (SQLite) n'est pas rendue.
        .join(Athlete, Athlete.id == AthleteClaim.athlete_id)
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
