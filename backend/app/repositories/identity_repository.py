"""Accès données pour Identity — seule couche qui touche la Session pour cette table."""
from sqlalchemy.orm import Session

from app.models.identity import Identity


def get_by_subject(db: Session, *, provider: str, subject: str) -> Identity | None:
    """Résout une identité par son **couple** `(provider, subject)`, et rien d'autre.

    C'est la seule clé de résolution du socle (FR-002) : ni l'adresse, ni le
    login du fournisseur — un login GitHub se renomme, et l'ancien redevient
    enregistrable par un tiers.
    """
    return (
        db.query(Identity)
        .filter(Identity.provider == provider, Identity.subject == subject)
        .first()
    )


def create(db: Session, *, user_id: int, provider: str, subject: str, email: str) -> Identity:
    identity = Identity(user_id=user_id, provider=provider, subject=subject, email=email)
    db.add(identity)
    db.flush()
    return identity


def refresh_email(db: Session, identity: Identity, *, email: str) -> Identity:
    """Aligne l'adresse constatée chez ce fournisseur (FR-008)."""
    if email:
        identity.email = email
    db.flush()
    return identity
