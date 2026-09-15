"""Modèle ProfileLogEntry — journal de bord d'un profil individuel (#867).

Une ligne par entrée datée : un journal est un historique, jamais une valeur
unique écrasée. Patron `app/models/volunteer_action.py`. Rationale complète :
`specs/20260915-111701-profil-jeune/research.md` (D2).

`entry_date` (date **métier** de l'entrée) est distincte de `created_at`
(horodatage **technique** d'écriture) : une saisie a posteriori ne fausse pas
l'ordre d'affichage voulu par l'utilisateur.
"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class ProfileLogEntry(Base):
    __tablename__ = "profile_log_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("personal_profiles.id"), index=True, nullable=False
    )
    entry_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    #: Pas d'`ondelete` — même raison que `PersonalProfile.created_by_user_id`.
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    profile: Mapped["PersonalProfile"] = relationship(  # noqa: F821
        back_populates="log_entries"
    )
    created_by: Mapped["User"] = relationship()  # noqa: F821
