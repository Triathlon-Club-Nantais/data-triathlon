"""Fournisseurs signalés par les utilisateurs, traités depuis le back-office."""
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import pending_provider_repository
from app.services import audit


def mark_handled(db: Session, actor: User, entry_id: int) -> None:
    """Marque le signalement traité, et le journalise (#935)."""
    pending_provider_repository.mark_handled(db, entry_id)
    audit.record(
        db, actor.id, action="pending_provider.handle", entity_type="pending_provider",
        entity_id=entry_id,
    )
