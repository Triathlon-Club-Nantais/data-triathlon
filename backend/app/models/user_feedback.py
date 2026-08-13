"""Modèle UserFeedback — signalements bug/feedback soumis publiquement (#267)."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow

#: Types acceptés — patron `Course.event_type` (chaîne nue, nomenclature en Python).
FEEDBACK_TYPES = ("bug", "feedback")
#: Statuts acceptés, transitions libres dans les deux sens (data-model.md).
FEEDBACK_STATUSES = ("nouveau", "en_cours", "traite", "ignore")


class UserFeedback(Base):
    """Un signalement, créé publiquement, instruit côté admin.

    `user_id` porte une FK **sans `ondelete`**, comme partout dans le dépôt
    (`user.py`, `user_role.py`, `admin_action_log.py`…) : `database.py` n'émet
    aucun `PRAGMA foreign_keys=ON`, la contrainte serait inerte en SQLite (dev
    et tests) et active en PostgreSQL. Aucune suppression d'utilisateur
    n'existe dans l'application — le signalement, comme la trace d'audit,
    n'a pas besoin de disparaître avec son auteur.

    `ip_address` **ne traverse jamais** un schéma de lecture exposé à l'API
    (data-model.md §D4) : il ne sert qu'à `count_recent_by_ip`.
    """

    __tablename__ = "user_feedback"
    __table_args__ = (
        Index("ix_user_feedback_status_created_at", "status", "created_at"),
        Index("ix_user_feedback_ip_address_created_at", "ip_address", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    page_url: Mapped[str | None] = mapped_column(String, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String, nullable=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="nouveau")
    github_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # Sens unique, comme `AllowedEmail.created_by` : `User` ne porte aucune
    # collection de ses signalements (data-model.md — l'admin parcourt les
    # signalements, jamais un historique par utilisateur).
    user: Mapped["User | None"] = relationship()  # noqa: F821
