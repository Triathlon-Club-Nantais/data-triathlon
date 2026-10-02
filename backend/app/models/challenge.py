"""Classement Challenge (#1008) : le cumul d'un athlète sur plusieurs épreuves du même jour.

Ses lignes ne sont pas des `Participation` : elles n'entrent dans aucun compteur,
aucun `federal_only`, aucune validation de saison ni aucune statistique, par
construction et non par une clause à ne pas oublier.
"""
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class Challenge(Base):
    __tablename__ = "challenges"
    __table_args__ = (UniqueConstraint("name", "event_date", name="uq_challenge_identity"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    event_date: Mapped[date] = mapped_column(Date)
    source_url: Mapped[str] = mapped_column(String, default="")
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    links: Mapped[list["ChallengeCourse"]] = relationship(
        back_populates="challenge", cascade="all, delete-orphan"
    )
    results: Mapped[list["ChallengeResult"]] = relationship(
        back_populates="challenge", cascade="all, delete-orphan"
    )


class ChallengeCourse(Base):
    __tablename__ = "challenge_courses"

    challenge_id: Mapped[int] = mapped_column(
        ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True, index=True
    )

    challenge: Mapped[Challenge] = relationship(back_populates="links")
    course: Mapped["Course"] = relationship()  # noqa: F821


class ChallengeResult(Base):
    __tablename__ = "challenge_results"
    __table_args__ = (UniqueConstraint("challenge_id", "bib_number", name="uq_challenge_result_bib"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[int] = mapped_column(
        ForeignKey("challenges.id", ondelete="CASCADE"), index=True
    )
    # RESTRICT : une fiche porteuse de lignes Challenge ne disparaît pas en silence.
    athlete_id: Mapped[int] = mapped_column(
        ForeignKey("athletes.id", ondelete="RESTRICT"), index=True
    )
    bib_number: Mapped[str | None] = mapped_column(String, nullable=True)
    rank_overall: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rank_gender: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rank_category: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_time: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="finisher")
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    challenge: Mapped[Challenge] = relationship(back_populates="results")
    athlete: Mapped["Athlete"] = relationship()  # noqa: F821
