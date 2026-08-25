"""Accès données pour UserFeedback (#267)."""
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

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
    colonne = _COLONNES_TRI[sort]
    colonne = colonne.desc() if order == "desc" else colonne.asc()
    requete = db.query(UserFeedback).options(joinedload(UserFeedback.user))
    if status is not None:
        requete = requete.filter(UserFeedback.status == status)
    return requete.order_by(colonne).all()


def count_by_status(db: Session) -> dict[str, int]:
    """Le nombre de signalements par statut, en **une** requête agrégée.

    Ne rend que les statuts présents : compléter les manquants à zéro est une
    décision d'affichage, elle appartient au routeur qui publie la forme.
    """
    lignes = (
        db.query(UserFeedback.status, func.count(UserFeedback.id))
        .group_by(UserFeedback.status)
        .all()
    )
    return {statut: total for statut, total in lignes}


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
