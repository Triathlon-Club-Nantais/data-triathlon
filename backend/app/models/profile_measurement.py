"""Modèle ProfileMeasurement : un test chronométré d'un profil individuel (#1365).

Une ligne par test daté (épreuve libre, durée en dixièmes de seconde) : une
progression est un historique, jamais une valeur écrasée. Patron
`profile_log_entry.py`. Rationale complète : la spec de #1365.

`measured_on` (date **métier** du test) est distincte de `created_at`
(horodatage **technique** d'écriture). La séance rattachée est facultative et
n'est qu'un repère : supprimer la séance remet `training_session_id` à NULL.
"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class ProfileMeasurement(Base):
    __tablename__ = "profile_measurements"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("personal_profiles.id"), index=True, nullable=False
    )
    measured_on: Mapped[date] = mapped_column(Date, nullable=False)
    event: Mapped[str] = mapped_column(String(100), nullable=False)
    duration_tenths: Mapped[int] = mapped_column(nullable=False)
    #: Pas d'`ondelete` : `training_session_repository.delete_training_session`
    #: remet la colonne à NULL (SQLite n'applique aucune clé étrangère).
    training_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_sessions.id"), nullable=True
    )
    #: Pas d'`ondelete`, même raison que `PersonalProfile.created_by_user_id`.
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    profile: Mapped["PersonalProfile"] = relationship(  # noqa: F821
        back_populates="measurements"
    )
