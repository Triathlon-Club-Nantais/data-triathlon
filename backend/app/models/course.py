"""Modèle Course — une épreuve = nom + date + type (un « heat »), clé de cache par scraped_at."""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint(
            "name", "event_date", "event_type", "is_relay", name="uq_course_identity"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_url: Mapped[str] = mapped_column(String, default="")
    provider: Mapped[str] = mapped_column(String, default="")
    name: Mapped[str] = mapped_column(String, index=True)
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    event_type: Mapped[str] = mapped_column(String, index=True, default="")
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_relay: Mapped[bool] = mapped_column(Boolean, default=False)
    # Indice de fiabilité des données, calculé à l'import (cf. services/quality.py).
    # NULL = jamais évaluée (course antérieure à l'indice, ou servie par le cache TTL).
    is_reliable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Détail des anomalies relevées : {code: nombre}. `{}` = évaluée, rien à signaler.
    quality_issues: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    participations: Mapped[list["Participation"]] = relationship(  # noqa: F821
        back_populates="course", cascade="all, delete-orphan"
    )
