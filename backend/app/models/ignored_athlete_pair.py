"""IgnoredAthletePair — deux fiches qu'un admin a jugées distinctes (#908).

Une paire écartée ne revient plus dans la revue d'identité. La paire est
normalisée, le plus petit id en premier (`ignored_athlete_pair_repository`).
`ON DELETE CASCADE` des deux côtés : contrairement à `IgnoredCourseDuplicate`,
une fiche disparaît par plusieurs chemins (purge des orphelins, fusion), et
aucun ne doit avoir à penser à cette table.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.time import utcnow


class IgnoredAthletePair(Base):
    __tablename__ = "ignored_athlete_pairs"
    __table_args__ = (
        UniqueConstraint("athlete_id_low", "athlete_id_high", name="uq_ignored_athlete_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id_low: Mapped[int] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), index=True)
    athlete_id_high: Mapped[int] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), index=True)
    ignored_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    ignored_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
