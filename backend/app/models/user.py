"""Modèle User — fiche applicative d'un contributeur du back-office admin (issue #114)."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # github_id stored as String to avoid the 32-bit int overflow trap on some
    # dialects and to keep the door open for a second provider without a
    # migration (YAGNI-safe: no `provider` column added today).
    github_id: Mapped[str] = mapped_column(
        String, nullable=False, unique=True, index=True
    )
    github_login: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    athlete_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("athletes.id", ondelete="SET NULL"),
        nullable=True,
    )

    athlete: Mapped["Athlete | None"] = relationship(  # noqa: F821
        "Athlete", lazy="joined", passive_deletes=True
    )
