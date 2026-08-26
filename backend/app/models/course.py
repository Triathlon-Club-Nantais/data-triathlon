"""Modèle Course — une épreuve = nom + date + type + relais (un « heat »), cache par scraped_at."""
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    UniqueConstraint,
    func,
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
    # Précision libre du format quand il n'entre dans aucune taille normalisée
    # (« Autre » du formulaire de saisie manuelle, #270). Le format normalisé,
    # lui, reste encodé dans `event_type` (`triathlon-m`) — la taxonomie y est
    # fermée pour garantir l'idempotence du re-classement (classify.py).
    format_label: Mapped[str | None] = mapped_column(String, nullable=True)
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
    # Nullable depuis #384 : une purge totale des résultats remet ce champ à
    # `NULL` sur toute la base pour forcer un rescrape immédiat — `services/
    # cache.is_fresh` lit déjà `None` comme « jamais scrapée ».
    scraped_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # Géocodage (#579) : persisté par la commande `geocode-courses`, jamais par
    # une route — `GET /stats/events-geo` ne fait plus qu'un `SELECT`. NULL sur
    # les deux = jamais géocodée avec succès (course neuve, ou tentative
    # échouée : voir `geocoded_at`).
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Horodatage de la **dernière tentative**, réussie ou non — posé même sur un
    # échec, pour ne pas re-tenter en boucle une épreuve que Nominatim ne sait
    # pas géocoder. NULL = jamais tentée. `geocode_service.run_geocode_courses`
    # est le seul point d'écriture des trois colonnes.
    geocoded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Dénormalisés (#623) : le nombre de participations validées (#270, jamais
    # en attente) et son sous-ensemble TCN, réécrits par l'import au même
    # endroit que `is_reliable_computed`/`quality_issues` ci-dessus
    # (`_Persister.finalize`) — pour que `GET /courses/events` (page
    # `/resultats`, défilement infini) n'ait plus à joindre puis grouper
    # `participations` sur l'ensemble filtré avant de paginer. Ajustés au
    # geste plutôt que recalculés depuis zéro par
    # `admin_actions.validate_participation`/`.delete_participation`, les deux
    # seuls gestes hors import qui changent l'état compté d'une ligne (cf.
    # `app/repositories/course_repository.py`, `adjust_counts`).
    participation_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    tcn_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

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

        **Aucun `@expression`** (#306) : ses quatre anciens appelants — les trois
        recherches par URL et `iter_all(provider=…)` — joignent `course_sources`
        depuis #281/#282, plus rapide qu'une sous-requête corrélée par ligne.
        #288 et #289 (détection de doublons, rapprochement automatique) sont
        arrivés depuis sans en créer de nouveau : la jointure est la bonne
        écriture, pas une étape de transition. Un futur `filter(Course.provider
        == …)` lève désormais — intentionnel, pas un oubli.
        """
        return _from_active_source(self, "url")

    @hybrid_property
    def provider(self) -> str:
        """Le fournisseur de la **source active**, ou `""` (#279).

        Deux sources d'une même épreuve n'ont pas le même chronométreur : le
        fournisseur suit donc l'active, exactement comme l'URL, et basculer l'une
        bascule l'autre. Les tenir dans deux endroits différents les aurait fait
        diverger au premier arbitrage.

        **Aucun `@expression`**, même décision que `source_url` ci-dessus (#306).
        """
        return _from_active_source(self, "provider")

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
