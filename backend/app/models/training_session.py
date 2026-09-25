"""Modèle TrainingSession — une séance d'entraînement (#868, epic #863).

**Aucune mention « jeune » dans ce schéma**, même arbitrage que
`PersonalProfile` (D1 de `specs/20260915-111701-profil-jeune/research.md`) :
la restriction aux jeunes de cette itération vit dans la garde d'accès
(`jeunes:read`/`jeunes:write`), jamais dans la table, pour qu'une extension
aux adultes n'ait ni table à doubler ni colonne à renommer.
"""
from datetime import date as date_
from datetime import datetime, time

from sqlalchemy import Date, DateTime, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class TrainingSession(Base):
    """Une séance d'entraînement — date, et trois champs optionnels.

    Seule `date` est obligatoire (#868). `start_time` est un ajout au-delà de
    la demande littérale de l'issue, justifié dans `research.md` : sans elle,
    deux séances le même jour sont indiscernables dans le calendrier. `location`
    et `session_type` restent du texte libre — aucune nomenclature fermée n'a
    été demandée.

    Porte sa liste de participants inscrits (`TrainingParticipant`), en
    cascade `delete-orphan` : une inscription n'a de sens que rattachée à sa
    séance, même raisonnement que `Course.sources`.
    """

    __tablename__ = "training_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date_] = mapped_column(Date, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    session_type: Mapped[str | None] = mapped_column(String, nullable=True)
    #: Note de séance en texte libre (#869) — rapport/observations de
    #: l'encadrant sur la séance entière, distincte du journal de bord d'un
    #: profil (`ProfileLogEntry`, #867). Cf. research.md D3 de
    #: `specs/20260915-141516-appel-jeunes/`.
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    participants: Mapped[list["TrainingParticipant"]] = relationship(  # noqa: F821
        back_populates="training_session", cascade="all, delete-orphan"
    )
