"""
Modèle Participation — résultat d'un athlète sur une course.

`splits` (JSON segment→temps) remplace les colonnes figées swim/t1/bike/t2/run et
couvre tous les sports (duathlon course1/course2, swimrun…). Les temps restent des
strings normalisées « HH:MM:SS » (cf. scrapers/utils.normalize_time).
"""
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class Participation(Base):
    __tablename__ = "participations"
    __table_args__ = (
        UniqueConstraint("course_id", "bib_number", name="uq_participation_bib"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)

    club: Mapped[str | None] = mapped_column(String, nullable=True)  # club au moment de la course
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    bib_number: Mapped[str | None] = mapped_column(String, nullable=True)

    rank_overall: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rank_category: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rank_gender: Mapped[int | None] = mapped_column(Integer, nullable=True)

    total_time: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="finisher")  # finisher / DNF / DNS

    splits: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    athlete: Mapped["Athlete"] = relationship(back_populates="participations")  # noqa: F821
    course: Mapped["Course"] = relationship(back_populates="participations")  # noqa: F821
