"""Modèle Entrainement — une séance d'entraînement jeunes (#868, epic #863)."""
from datetime import date as date_
from datetime import datetime, time

from sqlalchemy import Date, DateTime, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class Entrainement(Base):
    """Une séance d'entraînement jeunes — date, et trois champs optionnels.

    Seule `date` est obligatoire (#868). `heure_debut` est un ajout au-delà de
    la demande littérale de l'issue, justifié dans `research.md` : sans elle,
    deux séances le même jour sont indiscernables dans le calendrier. `lieu`
    et `type_seance` restent du texte libre — aucune nomenclature fermée n'a
    été demandée.

    Porte sa liste de participants inscrits (`EntrainementParticipant`), en
    cascade `delete-orphan` : une inscription n'a de sens que rattachée à sa
    séance, même raisonnement que `Course.sources`.
    """

    __tablename__ = "entrainements_jeunes"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date_] = mapped_column(Date, nullable=False)
    heure_debut: Mapped[time | None] = mapped_column(Time, nullable=True)
    lieu: Mapped[str | None] = mapped_column(String, nullable=True)
    type_seance: Mapped[str | None] = mapped_column(String, nullable=True)
    #: Note de séance en texte libre (#869) — rapport/observations de
    #: l'encadrant sur la séance entière, distincte du journal de bord d'un
    #: jeune (`ProfileLogEntry`, #867). Cf. research.md D3 de
    #: `specs/20260915-141516-appel-jeunes/`.
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    participants: Mapped[list["EntrainementParticipant"]] = relationship(  # noqa: F821
        back_populates="entrainement", cascade="all, delete-orphan"
    )
