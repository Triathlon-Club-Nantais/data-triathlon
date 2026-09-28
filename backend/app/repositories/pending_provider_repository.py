"""Accès données pour PendingProvider (providers signalés)."""
from sqlalchemy.orm import Session

from app.models.pending_provider import PendingProvider


def create(db: Session, url: str, provider_hint: str = "") -> PendingProvider:
    entry = PendingProvider(url=url, provider_hint=provider_hint)
    db.add(entry)
    db.flush()
    return entry


def report(db: Session, url: str, provider_hint: str = "") -> PendingProvider:
    """Le signalement non traité de cette URL, créé s'il n'existe pas (#1089).

    Un visiteur qui réessaie ne doit pas ajouter une ligne par tentative. Une
    entrée déjà traitée n'absorbe pas un nouveau signalement : il rouvre le sujet.
    """
    existing = (
        db.query(PendingProvider)
        .filter(PendingProvider.url == url, PendingProvider.handled.is_(False))
        .order_by(PendingProvider.id)
        .first()
    )
    return existing or create(db, url, provider_hint)


def list_unhandled(db: Session) -> list[PendingProvider]:
    return (
        db.query(PendingProvider)
        .filter(PendingProvider.handled.is_(False))
        .order_by(PendingProvider.reported_at.desc())
        .all()
    )


def count_unhandled(db: Session) -> int:
    return db.query(PendingProvider).filter(PendingProvider.handled.is_(False)).count()


def mark_handled(db: Session, entry_id: int) -> None:
    entry = db.get(PendingProvider, entry_id)
    if entry:
        entry.handled = True
