"""Modèle AbsorbedCourse — l'identité d'une épreuve absorbée par une fusion (#983)."""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class AbsorbedCourse(Base):
    """Ce que publiait une épreuve supprimée par une fusion, et qui l'a absorbée.

    Repointer l'URL de l'absorbée en passive ne suffit pas quand cette URL reste
    **active** sur d'autres épreuves (manches Breizh Chrono, variantes relais
    wiclax/timepulse) : le rescrape de ces sœurs republie la ligne de l'absorbée,
    qui n'apparie plus aucune épreuve par identité et la recréait. La ligne
    scrapée qui porte cette URL **et** cette identité est **ignorée**
    (`mapping.is_absorbed`, `_Persister.add`) : ni recréée, ni versée dans
    `target`, dont l'upsert écraserait temps et rangs et ajouterait des doublons
    d'athlètes (précision du 29/09 sur #983).

    Suit la cible : une seconde fusion qui absorbe la cible repointe ses lignes
    (`absorbed_course_repository.repoint`), la suppression de la cible les
    emporte (cascade ORM, même raison que `Course.sources`).
    """

    __tablename__ = "absorbed_courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id"), index=True, nullable=False
    )
    url: Mapped[str] = mapped_column(String, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    is_relay: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    target: Mapped["Course"] = relationship(back_populates="absorbed")  # noqa: F821
