"""SeasonGoal : un objectif privé de l'athlète rattaché pour une saison (#1373).

Possédé par le compte (cascade ORM depuis `User.season_goals`, table de
`user_repository._OWNED_TABLES`) : il part avec lui. Sa progression se calcule
à la lecture, sur la fiche rattachée, jamais stockée.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.time import utcnow

KIND_TIME = "time"
KIND_COUNT = "count"


class SeasonGoal(Base):
    __tablename__ = "season_goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    season: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(8))
    #: Discipline et format (`triathlon-m`) ; requis pour un temps, facultatif pour un nombre.
    event_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Secondes pour un temps, nombre d'épreuves pour un nombre.
    target: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
