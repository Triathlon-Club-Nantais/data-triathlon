"""Logique métier des retours utilisateurs (#267) — honeypot, débit, statut."""
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, TooManyRequestsError
from app.core.time import utcnow
from app.models.user_feedback import UserFeedback
from app.repositories import admin_action_log_repository, feedback_repository


def submit(
    db: Session,
    *,
    type: str,
    title: str,
    body: str,
    page_url: str | None,
    user_agent: str | None,
    ip_address: str | None,
    user_id: int | None,
    honeypot: str | None,
) -> UserFeedback | None:
    """Crée un signalement, ou `None` si le honeypot a été déclenché.

    `None` n'est **pas** une erreur : c'est le signal pour l'appelant de
    répondre le même succès apparent sans avoir rien inséré (research.md §D2).
    """
    if honeypot:
        return None

    if ip_address:
        settings = get_settings()
        since = utcnow() - timedelta(seconds=settings.feedback_rate_limit_window_seconds)
        recent = feedback_repository.count_recent_by_ip(db, ip_address=ip_address, since=since)
        if recent >= settings.feedback_rate_limit_max_per_window:
            raise TooManyRequestsError()

    return feedback_repository.create(
        db,
        type=type,
        title=title,
        body=body,
        page_url=page_url,
        user_agent=user_agent,
        ip_address=ip_address,
        user_id=user_id,
    )


def update(db: Session, *, feedback_id: int, changes: dict, user_id: int) -> UserFeedback:
    """Triage d'un retour (statut, lien GitHub), journalisé dans la **même**
    transaction que l'effet (#1123). Seuls les champs réellement modifiés entrent
    dans le payload `{before, after}` ; un triage sans effet ne laisse aucune
    ligne. Ne commite pas : c'est le rôle de la route."""
    entry = feedback_repository.get(db, feedback_id)
    if entry is None:
        raise NotFoundError("Signalement introuvable")
    avant = {champ: getattr(entry, champ) for champ in changes}
    if "status" in changes:
        feedback_repository.update_status(db, feedback_id, changes["status"])
    if "github_url" in changes:
        feedback_repository.set_github_url(db, feedback_id, changes["github_url"])
    apres = {champ: getattr(entry, champ) for champ in changes}
    modifies = [champ for champ in changes if avant[champ] != apres[champ]]
    if modifies:
        admin_action_log_repository.create(
            db,
            user_id=user_id,
            action="feedback.update",
            entity_type="feedback",
            entity_id=feedback_id,
            payload={
                "before": {champ: avant[champ] for champ in modifies},
                "after": {champ: apres[champ] for champ in modifies},
            },
        )
    return entry
