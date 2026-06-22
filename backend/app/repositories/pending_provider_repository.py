"""Accès données pour PendingProvider (providers signalés)."""
from sqlalchemy.orm import Session

from app.models.pending_provider import PendingProvider


def create(db: Session, url: str, provider_hint: str = "") -> PendingProvider:
    entry = PendingProvider(url=url, provider_hint=provider_hint)
    db.add(entry)
    db.flush()
    return entry


def list_unhandled(db: Session) -> list[PendingProvider]:
    return (
        db.query(PendingProvider)
        .filter(PendingProvider.handled.is_(False))
        .order_by(PendingProvider.reported_at.desc())
        .all()
    )


def mark_handled(db: Session, entry_id: int) -> None:
    entry = db.get(PendingProvider, entry_id)
    if entry:
        entry.handled = True
