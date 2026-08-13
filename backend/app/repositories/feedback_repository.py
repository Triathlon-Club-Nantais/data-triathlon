"""Accès données pour UserFeedback (#267)."""
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.user_feedback import UserFeedback

#: Colonnes de tri autorisées par le contrat (contracts/feedback-api.md).
_COLONNES_TRI = {
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


def count_recent_by_ip(db: Session, *, ip_address: str, since: datetime) -> int:
    """Signalements de cette IP depuis `since` — fenêtre glissante (research.md §D1)."""
    return (
        db.query(UserFeedback)
        .filter(UserFeedback.ip_address == ip_address, UserFeedback.created_at >= since)
        .count()
    )


def list_sorted(db: Session, *, sort: str = "created_at", order: str = "desc") -> list[UserFeedback]:
    colonne = _COLONNES_TRI[sort]
    colonne = colonne.desc() if order == "desc" else colonne.asc()
    return db.query(UserFeedback).order_by(colonne).all()


def get(db: Session, feedback_id: int) -> UserFeedback | None:
    return db.get(UserFeedback, feedback_id)


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
