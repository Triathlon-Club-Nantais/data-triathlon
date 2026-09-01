"""Modèle VolunteerAction — journal des actions de bénévolat déclarées (#709).

Plusieurs lignes peuvent coexister pour le même `(athlete_id, season)` :
c'est un journal, pas un indicateur unique (research.md D4) — le barème de
validation de saison est satisfait dès qu'il en existe au moins une.

`title`/`description`/`status` (#778) : nullable pour les deux premiers —
le chemin admin qui les créait sans titre ni description a été retiré (#780),
mais des lignes historiques `NULL` en production doivent rester lisibles
sans migration (research.md D2/D3 de la feature #780). `status` est
`NOT NULL` avec un défaut DB : contrairement à `title`/`description`, une
valeur par défaut a un sens pour toute ligne, ancienne ou nouvelle
(research.md D4 de la feature #778).
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
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
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="en_attente")

    declared_by: Mapped["User"] = relationship()  # noqa: F821
