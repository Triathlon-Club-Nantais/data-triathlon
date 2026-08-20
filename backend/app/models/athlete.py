"""Modèle Athlete — une personne, dédoublonnée par nom + prénom + date de naissance."""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, String, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class Athlete(Base):
    __tablename__ = "athletes"
    __table_args__ = (
        UniqueConstraint("nom", "prenom", "birth_date", name="uq_athlete_identity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String, index=True)
    prenom: Mapped[str] = mapped_column(String, default="")
    gender: Mapped[str] = mapped_column(String, default="")
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    club: Mapped[str | None] = mapped_column(String, nullable=True)  # club actuel
    # Le club actuel suit l'import — sauf si un humain l'a corrigé : le
    # chronométreur d'une course d'il y a trois ans annonce le club de l'époque,
    # et le laisser gagner ramènerait la correction à chaque réimport (#439).
    # `server_default=false()` et non la chaîne `"false"`, que SQLite relit `True`.
    club_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    participations: Mapped[list["Participation"]] = relationship(  # noqa: F821
        back_populates="athlete", cascade="all, delete-orphan"
    )
