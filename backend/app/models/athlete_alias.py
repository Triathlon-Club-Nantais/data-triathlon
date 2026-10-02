"""AthleteAlias — une graphie absorbée par une fusion, rattachée à la fiche conservée (#908).

L'import la résout comme l'identité de sa fiche : une nouvelle épreuve qui
publie « DUPOMT Jean » rejoint « DUPONT Jean » après leur fusion, au lieu de
recréer la faute. Une variante n'appartient qu'à une fiche ; elle suit sa
fiche dans les fusions suivantes, et disparaît avec elle.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.time import utcnow


class AthleteAlias(Base):
    __tablename__ = "athlete_aliases"
    __table_args__ = (UniqueConstraint("last_name_key", "first_name_key", name="uq_athlete_alias"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    last_name_key: Mapped[str] = mapped_column(String)
    first_name_key: Mapped[str] = mapped_column(String)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
