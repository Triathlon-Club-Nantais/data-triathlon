"""Logique métier des retours utilisateurs (#267) — honeypot, débit, statut."""
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import TooManyRequestsError
from app.core.time import utcnow
from app.models.user_feedback import UserFeedback
from app.repositories import feedback_repository


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
