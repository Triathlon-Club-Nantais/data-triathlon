"""Modèle SeasonValidation — statut de validation de la saison d'un athlète (#709).

**L'existence de la ligne porte le statut** (research.md D5) : valider crée la
ligne, dévalider la supprime. Pas de colonne booléenne — l'historique complet
(qui, quand, dans quel sens) vit dans `AdminActionLog`, pas ici.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class SeasonValidation(Base):
    __tablename__ = "season_validations"
    __table_args__ = (
        UniqueConstraint("athlete_id", "season", name="uq_season_validation_athlete_season"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    season: Mapped[int] = mapped_column(Integer)
    validated_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    validated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    validated_by: Mapped["User"] = relationship()  # noqa: F821
