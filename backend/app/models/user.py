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
    # Incremented at logout — comparing this against the epoch signed into a
    # session token lets us invalidate all outstanding cookies of one user
    # without rotating the global SESSION_SECRET_KEY (which would sign every
    # other user out). Cf. review B4 of PR #159.
    session_epoch: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    athlete_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("athletes.id", ondelete="SET NULL"),
        nullable=True,
    )

    # `lazy="raise"` because nothing on this ticket reads `User.athlete` — the
    # `UserRead` schema doesn't expose it. Any accidental access will raise
    # loudly instead of silently issuing a `LEFT JOIN athletes` on every
    # authenticated request. #117 will flip this back to `joined` (or eager
    # load explicitly) when it actually consumes the relationship.
    athlete: Mapped["Athlete | None"] = relationship(  # noqa: F821
        "Athlete", lazy="raise", passive_deletes=True
    )
