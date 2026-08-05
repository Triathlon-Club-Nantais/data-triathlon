"""Modèle Course — une épreuve = nom + date + type + relais (un « heat »), cache par scraped_at."""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, String, UniqueConstraint, func
from sqlalchemy.ext.hybrid import hybrid_property
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
    # Ce que la **machine** constate, réécrit par l'import à chaque passage
    # (cf. services/quality.py). NULL = jamais évaluée (course antérieure à
    # l'indice, ou servie par le cache TTL).
    is_reliable_computed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Ce qu'un **humain** a tranché (#115, pouvoir `quality:override`).
    # NULL = personne. Jamais écrite par l'import : les deux chemins d'écriture
    # ne se croisent pas, et c'est la forme qui l'assure, pas une garde (FR-037).
    reliability_override: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Détail des anomalies relevées : {code: nombre}. `{}` = évaluée, rien à signaler.
    quality_issues: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    participations: Mapped[list["Participation"]] = relationship(  # noqa: F821
        back_populates="course", cascade="all, delete-orphan"
    )

    @hybrid_property
    def is_reliable(self) -> bool | None:
        """Le verdict effectif : l'avis humain s'il existe, sinon le calculé.

        **Le contrat public ne bouge pas** (FR-038) : `CourseBrief` expose
        toujours `is_reliable`, sans qu'une ligne de `schemas/course.py` ne
        change — `from_attributes=True` lit une propriété comme une colonne.

        Ce que cette forme supprime : aucune branche dans l'import (il écrit sa
        colonne, toujours), **aucun recalcul à la levée** — remettre
        `reliability_override` à `NULL` fait réapparaître le *dernier* verdict
        calculé, pas celui qui valait au moment de la décision humaine — et
        aucune perte du verdict machine quand un humain tranche.
        """
        if self.reliability_override is not None:
            return self.reliability_override
        return self.is_reliable_computed

    @is_reliable.expression
    @classmethod
    def is_reliable(cls):
        """Sans ce pendant SQL, la propriété serait **illisible dans un `WHERE`**.

        C'est la moitié qu'on oublie : le Python marcherait, et le premier filtre
        sur `Course.is_reliable` lèverait.
        """
        return func.coalesce(cls.reliability_override, cls.is_reliable_computed)
