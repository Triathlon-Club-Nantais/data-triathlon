"""Modèle VolunteerDeclaration — déclaration de bénévolat (#751).

Indépendant de `VolunteerAction` (#709) : ce dernier est un journal
immuable, déclaré uniquement par un admin, au service du quota de saison.
Cette table est suppressible et porte titre/description — voir
research.md D1/D2 de `specs/20260830-160242-declaration-benevolat/`.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow

#: Statuts acceptés — patron `UserFeedback.status` (chaîne nue, pas de table à part).
VOLUNTEER_DECLARATION_STATUSES = ("en_attente", "validee")


class VolunteerDeclaration(Base):
    __tablename__ = "volunteer_declarations"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    beneficiary_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="en_attente")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    beneficiary: Mapped["User"] = relationship(foreign_keys=[beneficiary_user_id])  # noqa: F821
    author: Mapped["User"] = relationship(foreign_keys=[author_user_id])  # noqa: F821
