"""Modèle VolunteerAction — journal des actions de bénévolat déclarées (#709).

Plusieurs lignes peuvent coexister pour le même `(athlete_id, season)` :
c'est un journal, pas un indicateur unique (research.md D4) — le barème de
validation de saison est satisfait dès qu'il en existe au moins une.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class VolunteerAction(Base):
    __tablename__ = "volunteer_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    declared_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    declared_by: Mapped["User"] = relationship()  # noqa: F821
