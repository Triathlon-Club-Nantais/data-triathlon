"""Accès données pour UserSession — seule couche qui touche la Session pour cette table."""
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.core.time import utcnow
from app.models.user_session import UserSession


def get_by_token_hash(db: Session, token_hash: str) -> UserSession | None:
    """Résout une session par l'empreinte du jeton présenté.

    L'utilisateur est chargé dans la même requête : l'invariant de validité
    (FR-013) le lit systématiquement, et une seconde requête par appel
    authentifié serait payée sur chaque page.
    """
    return (
        db.query(UserSession)
        .options(joinedload(UserSession.user))
        .filter(UserSession.token_hash == token_hash)
        .first()
    )


def create(db: Session, *, user_id: int, token_hash: str, expires_at: datetime) -> UserSession:
    session = UserSession(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    db.add(session)
    db.flush()
    return session


def delete(db: Session, session: UserSession) -> None:
    """Supprime **cette** ligne. Les autres appareils survivent (FR-014)."""
    db.delete(session)
    db.flush()


def delete_expired(db: Session, *, user_id: int) -> int:
    """Supprime les sessions expirées de cet utilisateur. Renvoie le nombre supprimé.

    Hygiène opportuniste, appelée à l'ouverture d'une session (FR-019) : le dépôt
    n'a aucun ordonnanceur, et une commande de purge ne serait lancée par
    personne. Une session expirée est de toute façon déjà refusée en lecture —
    sa suppression physique est de l'hygiène, pas de la sécurité.

    Bornée à **un** utilisateur : c'est celui qui vient de se connecter, et un
    balayage global ferait payer à sa connexion la taille de toute la table.
    """
    supprimees = (
        db.query(UserSession)
        .filter(UserSession.user_id == user_id, UserSession.expires_at <= utcnow())
        .delete(synchronize_session="fetch")
    )
    db.flush()
    return supprimees
