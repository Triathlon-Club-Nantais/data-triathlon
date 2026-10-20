"""Accès données pour UserFeedback (#267)."""
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.user_feedback import UserFeedback

#: Colonnes de tri autorisées par le contrat (contracts/feedback-api.md).
_SORT_COLUMNS = {
    "created_at": UserFeedback.created_at,
    "type": UserFeedback.type,
    "status": UserFeedback.status,
}


def create(
    db: Session,
    *,
    type: str,
    title: str,
    body: str,
    page_url: str | None = None,
    user_agent: str | None = None,
    ip_address: str | None = None,
    user_id: int | None = None,
) -> UserFeedback:
    entry = UserFeedback(
        type=type,
        title=title,
        body=body,
        page_url=page_url,
        user_agent=user_agent,
        ip_address=ip_address,
        user_id=user_id,
    )
    db.add(entry)
    db.flush()
    return entry


def list_for_user(db: Session, user_id: int) -> list[UserFeedback]:
    """Export du compte (#1674) : ses signalements, du plus récent au plus ancien."""
    return list(
        db.scalars(select(UserFeedback).where(UserFeedback.user_id == user_id).order_by(UserFeedback.created_at.desc()))
    )


def count_recent_by_ip(db: Session, *, ip_address: str, since: datetime) -> int:
    """Signalements de cette IP depuis `since` — fenêtre glissante (research.md §D1)."""
    return (
        db.query(UserFeedback)
        .filter(UserFeedback.ip_address == ip_address, UserFeedback.created_at >= since)
        .count()
    )


def list_sorted(
    db: Session,
    *,
    sort: str = "created_at",
    order: str = "desc",
    status: str | None = None,
) -> list[UserFeedback]:
    """`status=None` rend toute la table — la forme historique de la route.

    Le filtre s'appuie sur `ix_user_feedback_status_created_at`, l'index que le
    modèle porte depuis #267 : (`status`, `created_at`) sert exactement la vue
    par défaut de la file, « les nouveaux, du plus récent au plus ancien ».
    """
    sort_column = _SORT_COLUMNS[sort]
    sort_column = sort_column.desc() if order == "desc" else sort_column.asc()
    query = db.query(UserFeedback).options(joinedload(UserFeedback.user))
    if status is not None:
        query = query.filter(UserFeedback.status == status)
    return query.order_by(sort_column).all()


def count_by_status(db: Session) -> dict[str, int]:
    """Le nombre de signalements par statut, en **une** requête agrégée.

    Ne rend que les statuts présents : compléter les manquants à zéro est une
    décision d'affichage, elle appartient au routeur qui publie la forme.
    """
    rows = (
        db.query(UserFeedback.status, func.count(UserFeedback.id))
        .group_by(UserFeedback.status)
        .all()
    )
    return {status_value: total for status_value, total in rows}


def get(db: Session, feedback_id: int) -> UserFeedback | None:
    return (
        db.query(UserFeedback)
        .options(joinedload(UserFeedback.user))
        .filter(UserFeedback.id == feedback_id)
        .first()
    )


def update_status(db: Session, feedback_id: int, status: str) -> UserFeedback | None:
    entry = db.get(UserFeedback, feedback_id)
    if entry:
        entry.status = status
        db.flush()
    return entry


def set_github_url(db: Session, feedback_id: int, github_url: str) -> UserFeedback | None:
    entry = db.get(UserFeedback, feedback_id)
    if entry:
        entry.github_url = github_url
        db.flush()
    return entry


def count_created_before(db: Session, cutoff: datetime) -> int:
    return db.scalar(select(func.count()).select_from(UserFeedback).where(UserFeedback.created_at < cutoff))


def delete_created_before(db: Session, cutoff: datetime) -> int:
    """Purge de rétention (#1158), adresse IP comprise. Rend le nombre de signalements supprimés."""
    return db.execute(delete(UserFeedback).where(UserFeedback.created_at < cutoff)).rowcount
