"""AthleteKnownClub : un club qu'un admin a confirmé pour une fiche (#1209).

Deux lecteurs : la revue d'identité (motif `multi_club`, un club confirmé n'y
signale plus rien) et l'import, qui rattache à la fiche principale un résultat
publié sous un club confirmé au lieu de créer un homonyme. `club_key` est la clé
canonique (`core.club.broad_club_key` du nom canonique). `ON DELETE CASCADE` :
une fiche disparaît par plusieurs chemins, aucun ne doit penser à cette table.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.time import utcnow


class AthleteKnownClub(Base):
    __tablename__ = "athlete_known_clubs"
    __table_args__ = (UniqueConstraint("athlete_id", "club_key", name="uq_athlete_known_club"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), index=True)
    club_key: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
