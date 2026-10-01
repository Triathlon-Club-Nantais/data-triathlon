"""Modèle Athlete — une personne, identifiée par la clé normalisée de son nom et
de son prénom, plus un rang d'homonyme (#907, epic #1146)."""
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    event,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.athlete_identity import athlete_identity_keys
from app.core.database import Base
from app.core.time import utcnow


class Athlete(Base):
    __tablename__ = "athletes"
    __table_args__ = (
        UniqueConstraint("last_name_key", "first_name_key", "homonym_rank", name="uq_athlete_identity"),
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
    # Écrites par `_store_identity_keys`, jamais par l'appelant.
    last_name_key: Mapped[str | None] = mapped_column(String, nullable=True)
    first_name_key: Mapped[str | None] = mapped_column(String, nullable=True)
    # 0 : la fiche principale de la clé, la seule que l'import vise ; au-delà, un
    # homonyme distingué (deux dossards sur une même épreuve, #967).
    homonym_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    participations: Mapped[list["Participation"]] = relationship(  # noqa: F821
        back_populates="athlete", cascade="all, delete-orphan"
    )


@event.listens_for(Athlete, "before_insert")
@event.listens_for(Athlete, "before_update")
def _store_identity_keys(_mapper, _connection, athlete: Athlete) -> None:
    athlete.last_name_key, athlete.first_name_key = athlete_identity_keys(athlete.nom, athlete.prenom)


# Repli de l'import (nom et prénom accolés dans un sens ou dans l'autre, #908).
Index("ix_athletes_identity_last_first", Athlete.last_name_key + Athlete.first_name_key)
Index("ix_athletes_identity_first_last", Athlete.first_name_key + Athlete.last_name_key)
