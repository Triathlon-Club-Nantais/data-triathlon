"""Modèle Course — une épreuve = nom + date + type + relais (un « heat »), cache par scraped_at."""
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    String,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow
from app.models.course_source import CourseSource

#: La chaîne vide qu'une épreuve **sans source** rend des deux côtés du hybride —
#: en Python comme en SQL. Une saisie manuelle n'a pas d'URL, et c'est un état
#: légitime : sans ce repli, le SQL rendrait `NULL` là où le contrat public
#: (`CourseBrief.source_url: str`) promet une chaîne, et un `WHERE
#: source_url = ''` ne ramènerait plus ces épreuves.
_SANS_SOURCE = ""


def _from_active_source(course: "Course", champ: str) -> str:
    """Lit un champ de la source active **dans la collection déjà en mémoire**.

    Pas de requête : la relation `sources` est la même que celle que traverse la
    cascade, donc une source ajoutée ou basculée dans la transaction courante est
    visible immédiatement — sans quoi la valeur dérivée resterait celle d'avant
    la bascule jusqu'au prochain `expire`.
    """
    for source in course.sources:
        if source.is_active:
            return getattr(source, champ)
    return _SANS_SOURCE


def _active_source_subquery(course_cls: type["Course"], colonne):
    """Sous-requête scalaire corrélée sur la source active, repliée sur `""`.

    `correlate_except` plutôt que `correlate` : c'est la forme qui survit à un
    alias — le jour où une requête joint `courses` deux fois (fusion de #287), la
    corrélation explicite sur la classe se serait figée sur la mauvaise moitié.
    """
    return func.coalesce(
        select(colonne)
        .where(
            CourseSource.course_id == course_cls.id,
            CourseSource.is_active,
        )
        .correlate_except(CourseSource)
        .scalar_subquery(),
        _SANS_SOURCE,
    )


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint(
            "name", "event_date", "event_type", "is_relay", name="uq_course_identity"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
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
    #: Les N sources d'import de l'épreuve, dont une seule active (#278). Même
    #: cascade que les participations, et portée par l'**ORM** pour la même
    #: raison : `database.py` n'émet aucun `PRAGMA foreign_keys=ON`, un
    #: `ondelete` serait inerte en SQLite et actif en PostgreSQL.
    sources: Mapped[list["CourseSource"]] = relationship(  # noqa: F821
        back_populates="course", cascade="all, delete-orphan"
    )

    @hybrid_property
    def source_url(self) -> str:
        """L'URL de la **source active**, ou `""` — plus une colonne (#279).

        Une épreuve sans aucune source rend la chaîne vide : c'est l'état d'une
        saisie manuelle, pas une erreur. Aucun `@setter` n'accompagne la
        propriété, et c'est délibéré — la table est la seule vérité, et c'est la
        **forme** qui l'assure plutôt qu'un grep à refaire à chaque relecture.
        """
        return _from_active_source(self, "url")

    @source_url.expression
    @classmethod
    def source_url(cls):
        """Sans ce pendant SQL, la propriété serait **illisible dans un `WHERE`**.

        Et ici la moitié SQL porte du travail réel :
        `course_repository.get_latest_by_source_url`, `list_by_source_url` et
        `list_by_source_urls` filtrent tous les trois sur ce champ — le cache TTL
        et le sélecteur de heats du front en dépendent.
        """
        return _active_source_subquery(cls, CourseSource.url)

    @hybrid_property
    def provider(self) -> str:
        """Le fournisseur de la **source active**, ou `""` (#279).

        Deux sources d'une même épreuve n'ont pas le même chronométreur : le
        fournisseur suit donc l'active, exactement comme l'URL, et basculer l'une
        bascule l'autre. Les tenir dans deux endroits différents les aurait fait
        diverger au premier arbitrage.
        """
        return _from_active_source(self, "provider")

    @provider.expression
    @classmethod
    def provider(cls):
        """Le pendant SQL qu'exige `course_repository.iter_all(provider=…)`."""
        return _active_source_subquery(cls, CourseSource.provider)

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
