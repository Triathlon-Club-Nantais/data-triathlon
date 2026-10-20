"""SeasonGoal : un objectif privé de l'athlète rattaché pour une saison (#1373).

Possédé par le compte (cascade ORM depuis `User.season_goals`, table de
`user_repository._OWNED_TABLES`) : il part avec lui. Sa progression se calcule
à la lecture, sur la fiche rattachée, jamais stockée.
"""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, false
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.time import utcnow

KIND_TIME = "time"
KIND_COUNT = "count"
KIND_RACE = "race"


class SeasonGoal(Base):
    __tablename__ = "season_goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    season: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(8))
    #: Discipline et format (`triathlon-m`) ; requis pour un temps, facultatif pour un nombre.
    event_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Secondes pour un temps, nombre d'épreuves pour un nombre ; facultatif pour une épreuve cible.
    target: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Épreuve cible connue ; nom et date sont recopiés, donc l'objectif survit à sa suppression.
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    race_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    race_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    #: Un seul objectif majeur par compte et par saison.
    major: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
