"""Sessions applicatives — jeton opaque côté navigateur, empreinte en base.

`resolve()` porte l'invariant à trois conditions de FR-013 : la session existe,
n'a pas expiré, **et** son utilisateur est actif. La troisième est une
**jointure**, jamais un cache — c'est elle qui rend la désactivation d'un compte
immédiate (FR-015) sans avoir à parcourir les sessions.
"""
import hashlib
import secrets
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import utcnow
from app.models.user import User
from app.repositories import session_repository

#: `secrets.token_urlsafe(32)` rend 43 caractères pour 256 bits uniformes.
#: C'est cette garde de longueur — et non l'algorithme — qui rend SHA-256 nu
#: suffisant : sans dictionnaire ni faible entropie, un KDF coûterait à **chaque**
#: requête authentifiée pour un gain nul. Le jour où quelqu'un rangerait un code
#: court dans la même colonne, elle deviendrait cassable hors ligne.
TOKEN_MIN_LENGTH = 43


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def open_for(db: Session, user: User) -> str:
    """Ouvre une session et rend le jeton **brut**, qui n'existera nulle part ailleurs.

    Purge au passage les sessions expirées de cet utilisateur : le dépôt n'a
    aucun ordonnanceur, et une commande de purge ne serait lancée par personne
    (FR-019).
    """
    session_repository.delete_expired(db, user_id=user.id)
    return open_with_token(db, user, token=new_token())


def open_with_token(db: Session, user: User, *, token: str) -> str:
    if len(token) < TOKEN_MIN_LENGTH:
        raise ValueError(
            f"session token must be at least {TOKEN_MIN_LENGTH} characters long"
        )
    settings = get_settings()
    session_repository.create(
        db,
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=utcnow() + timedelta(days=settings.auth_session_ttl_days),
    )
    return token


def resolve(db: Session, token: str | None) -> User | None:
    """Utilisateur derrière ce jeton, ou `None`. Invariant à trois conditions."""
    if not token or len(token) < TOKEN_MIN_LENGTH:
        return None

    ligne = session_repository.get_by_token_hash(db, hash_token(token))
    if ligne is None or ligne.expires_at <= utcnow():
        return None
    if not ligne.user or not ligne.user.is_active:
        return None
    return ligne.user


def close(db: Session, token: str | None) -> None:
    """Ferme **cette** session. Sans effet ni erreur si elle n'existe pas (FR-014)."""
    if not token:
        return
    ligne = session_repository.get_by_token_hash(db, hash_token(token))
    if ligne is not None:
        session_repository.delete(db, ligne)
