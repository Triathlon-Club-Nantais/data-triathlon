"""Modèle TrainingRecurrence : règle hebdomadaire qui engendre des séances (#1291,
research R4). Pas de moteur RRULE : le club n'a que des créneaux hebdomadaires.

Porte aussi les deux tables d'association vers `training_groups`."""
from datetime import date, datetime, time

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Table, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow

# La clé primaire composite tient lieu de contrainte d'unicité.
training_recurrence_groups = Table(
    "training_recurrence_groups",
    Base.metadata,
    Column("recurrence_id", ForeignKey("training_recurrences.id"), primary_key=True),
    Column("training_group_id", ForeignKey("training_groups.id"), primary_key=True),
)

training_session_groups = Table(
    "training_session_groups",
    Base.metadata,
    Column("training_session_id", ForeignKey("training_sessions.id"), primary_key=True),
    Column("training_group_id", ForeignKey("training_groups.id"), primary_key=True),
)


class TrainingRecurrence(Base):
    __tablename__ = "training_recurrences"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: 0 = lundi, 6 = dimanche (`date.weekday()`).
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Heure locale naïve, comme `TrainingSession.start_time` : l'heure saisie
    #: reste l'heure affichée, heure d'été comprise.
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    session_type: Mapped[str | None] = mapped_column(String, nullable=True)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    groups: Mapped[list["TrainingGroup"]] = relationship(  # noqa: F821
        secondary=training_recurrence_groups, back_populates="recurrences", order_by="TrainingGroup.name"
    )
