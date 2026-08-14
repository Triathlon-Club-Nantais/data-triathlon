"""
Modèle Participation — résultat d'un athlète sur une course.

`splits` (JSON segment→temps) remplace les colonnes figées swim/t1/bike/t2/run et
couvre tous les sports (duathlon course1/course2, swimrun…). Les temps restent des
strings normalisées « HH:MM:SS » (cf. scrapers/utils.normalize_time).
"""
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.club import CLUB_NORMALIZED_INDEX_EXPRESSION
from app.core.database import Base
from app.core.time import utcnow


class Participation(Base):
    __tablename__ = "participations"
    __table_args__ = (
        UniqueConstraint("course_id", "bib_number", name="uq_participation_bib"),
        # Index fonctionnel sur la forme normalisée de `club` (#351) : sans lui,
        # `tcn_clause(Participation.club)` — `course_repository._filtered` et
        # quatre `.filter(tcn_clause(...))` de `participation_repository.py`
        # (lignes ~299, 448, 504, 687) — force un balayage complet de la table
        # (aucun index ne peut servir une expression), mesuré à 15-20x plus
        # lent que le même endpoint sans `scope=club`. Deux autres appels
        # (~177, 535) évaluent `tcn_clause` dans un `func.sum(case(...))`,
        # agrégat calculé sur un groupe déjà restreint par d'autres critères :
        # l'index accélère une **sélection** de lignes, pas un booléen évalué
        # ligne à ligne à l'intérieur d'un agrégat déjà borné — ces deux-là ne
        # profitent pas dans les mêmes proportions.
        # `EXPLAIN QUERY PLAN` avant/après : cf. migration `e9cdbf3a4866`.
        Index(
            "ix_participations_club_normalized",
            text(CLUB_NORMALIZED_INDEX_EXPRESSION),
        ),
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
    # Relais d'équipe (TimePulse mélange solos et relais dans une même course) :
    # l'info est portée par la participation, pas par la course.
    is_relay: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    splits: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    athlete: Mapped["Athlete"] = relationship(back_populates="participations")  # noqa: F821
    course: Mapped["Course"] = relationship(back_populates="participations")  # noqa: F821
