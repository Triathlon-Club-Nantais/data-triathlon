"""Accès données pour UserSession — seule couche qui touche la Session pour cette table."""
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import distinct, func
from sqlalchemy.orm import Query, Session, joinedload

from app.core.time import utcnow
from app.models.user import User
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


def _revoke(db: Session, requete: Query[UserSession]) -> tuple[int, int]:
    """Supprime les sessions de cette requête. Rend (sessions, comptes) **vivants**.

    **On supprime tout, on ne compte que ce qui était ouvert**, et l'écart entre
    les deux est délibéré. Supprimer une ligne expirée est de l'hygiène gratuite ;
    l'annoncer comme « fermée » serait un mensonge, et un mensonge coûteux : elle
    était déjà refusée par `session.resolve`. Faute d'ordonnanceur, ces lignes
    s'accumulent — elles ne sont purgées qu'à la connexion de leur titulaire —,
    donc une base réelle en est pleine, et « 5 sessions fermées » quand une seule
    était vivante empêche l'exploitant de répondre à la seule question qu'il se
    pose en incident.

    Le filtre est celui de `resolve` — non expirée **et** utilisateur actif —,
    la troisième condition étant la même jointure : les sessions d'un compte
    retiré (#170) sont déjà mortes, les compter ferait passer le retrait pour
    défait. Les comptes sont comptés sur ces sessions-là, jamais sur les comptes
    visés : dire « 3 comptes » quand deux dormaient donnerait à un geste dans le
    vide l'air d'un geste utile.
    """
    vivantes = requete.join(User).filter(
        UserSession.expires_at > utcnow(), User.is_active.is_(True)
    )
    sessions, comptes = vivantes.with_entities(
        func.count(UserSession.id), func.count(distinct(UserSession.user_id))
    ).one()
    requete.delete(synchronize_session="fetch")
    db.flush()
    return sessions, comptes


def delete_all(db: Session) -> tuple[int, int]:
    """Supprime **toutes** les sessions, tous comptes confondus (#169).

    La révocation d'urgence, et le seul écrivain de cette table qui ignore
    `user_id`. À distinguer de la désactivation d'un compte, qui ferme par la
    jointure sans rien effacer.
    """
    return _revoke(db, db.query(UserSession))


def delete_for_users(db: Session, user_ids: Sequence[int]) -> tuple[int, int]:
    """Supprime les sessions de ces comptes. Sans effet sur une liste vide."""
    if not user_ids:
        return 0, 0
    return _revoke(db, db.query(UserSession).filter(UserSession.user_id.in_(user_ids)))


def delete_expired(db: Session, *, user_id: int) -> int:
    """Supprime les sessions expirées de cet utilisateur. Renvoie le nombre supprimé.

    Hygiène opportuniste, appelée à l'ouverture d'une session (FR-019) : le dépôt
    n'a aucun ordonnanceur, et une commande de purge ne serait lancée par
    personne. Une session expirée est de toute façon déjà refusée en lecture —
    sa suppression physique est de l'hygiène, pas de la sécurité.

    Bornée à **un** utilisateur : c'est celui qui vient de se connecter, et un
    balayage global ferait payer à sa connexion la taille de toute la table.
    """
    deleted = (
        db.query(UserSession)
        .filter(UserSession.user_id == user_id, UserSession.expires_at <= utcnow())
        .delete(synchronize_session="fetch")
    )
    db.flush()
    return deleted
