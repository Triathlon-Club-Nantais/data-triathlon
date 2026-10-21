"""Accès données des demandes d'adhésion (#1785)."""

from datetime import date, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.time import utcnow
from app.models.member_request import STATUS_PENDING, STATUS_REJECTED, MemberRequest
from app.repositories.dialect import dialect_insert


def get_for_user(db: Session, user_id: int, organisation_id: int) -> MemberRequest | None:
    return db.scalar(
        select(MemberRequest).where(
            MemberRequest.user_id == user_id, MemberRequest.organisation_id == organisation_id
        )
    )


def get_pending(db: Session, request_id: int) -> MemberRequest | None:
    """Verrouillée (`FOR UPDATE`, sans effet en SQLite) : deux responsables qui
    décident ensemble ne décident qu'une fois, le second relit une demande qui
    n'est plus en attente."""
    return db.scalar(
        select(MemberRequest)
        .where(MemberRequest.id == request_id, MemberRequest.status == STATUS_PENDING)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def upsert_pending(
    db: Session,
    *,
    user_id: int,
    organisation_id: int,
    first_name: str,
    last_name: str,
    birth_date: date | None,
    phone: str | None,
) -> MemberRequest:
    """La demande en attente du compte, qui remplace la précédente quelle qu'elle soit.

    Un seul `INSERT ... ON CONFLICT DO UPDATE` : une lecture préalable serait
    franchie par deux envois simultanés, et la seconde insertion ferait céder
    `uq_member_request_user_organisation` en 500.
    """
    values = {
        "first_name": first_name,
        "last_name": last_name,
        "birth_date": birth_date,
        "phone": phone,
        "status": STATUS_PENDING,
        "created_at": utcnow(),
        "decided_at": None,
    }
    db.flush()
    db.execute(
        dialect_insert(db)(MemberRequest)
        .values(user_id=user_id, organisation_id=organisation_id, **values)
        .on_conflict_do_update(
            index_elements=[MemberRequest.user_id, MemberRequest.organisation_id], set_=values
        )
    )
    return db.scalars(
        select(MemberRequest)
        .where(MemberRequest.user_id == user_id, MemberRequest.organisation_id == organisation_id)
        .execution_options(populate_existing=True)
    ).one()


def reject(db: Session, request: MemberRequest, *, now: datetime) -> None:
    request.status = STATUS_REJECTED
    request.decided_at = now
    db.flush()


def delete_request(db: Session, request: MemberRequest) -> None:
    db.delete(request)
    db.flush()


def delete_pending_for_user(db: Session, user_id: int, organisation_id: int) -> None:
    db.execute(
        delete(MemberRequest).where(
            MemberRequest.user_id == user_id,
            MemberRequest.organisation_id == organisation_id,
            MemberRequest.status == STATUS_PENDING,
        )
    )


def list_pending(db: Session, organisation_id: int) -> list[MemberRequest]:
    return list(
        db.scalars(
            select(MemberRequest)
            .options(selectinload(MemberRequest.user))
            .where(
                MemberRequest.organisation_id == organisation_id,
                MemberRequest.status == STATUS_PENDING,
            )
            .order_by(MemberRequest.created_at, MemberRequest.id)
        )
    )


def count_pending(db: Session, organisation_id: int) -> int:
    return (
        db.scalar(
            select(func.count(MemberRequest.id)).where(
                MemberRequest.organisation_id == organisation_id,
                MemberRequest.status == STATUS_PENDING,
            )
        )
        or 0
    )


def count_rejected_before(db: Session, cutoff: datetime) -> int:
    return (
        db.scalar(
            select(func.count(MemberRequest.id)).where(
                MemberRequest.status == STATUS_REJECTED, MemberRequest.decided_at < cutoff
            )
        )
        or 0
    )


def delete_rejected_before(db: Session, cutoff: datetime) -> int:
    """Purge de rétention : les refus décidés avant `cutoff`. Rend le nombre supprimé."""
    return db.execute(
        delete(MemberRequest).where(
            MemberRequest.status == STATUS_REJECTED, MemberRequest.decided_at < cutoff
        )
    ).rowcount


def count_pending_before(db: Session, cutoff: datetime) -> int:
    return (
        db.scalar(
            select(func.count(MemberRequest.id)).where(
                MemberRequest.status == STATUS_PENDING, MemberRequest.created_at < cutoff
            )
        )
        or 0
    )


def delete_pending_before(db: Session, cutoff: datetime) -> int:
    """Purge de rétention : les demandes restées en attente depuis avant `cutoff`."""
    return db.execute(
        delete(MemberRequest).where(
            MemberRequest.status == STATUS_PENDING, MemberRequest.created_at < cutoff
        )
    ).rowcount
