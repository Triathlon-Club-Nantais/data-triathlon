"""Modèle CourseSource — les N sources d'une épreuve, dont une seule active (#278)."""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class CourseSource(Base):
    """Une URL de chronométrage rattachée à une épreuve.

    Une même épreuve publiée par deux chronométreurs produisait deux lignes
    `Course` sans lien (#210) : la seconde URL était perdue par
    `course_repository.get_or_create`, qui rend l'existante sans jamais toucher
    `source_url`. Les sources vivent donc ici, N par épreuve — mais **les
    participations restent portées par la `Course`**, pas par la source : le
    classement affiché ne mélange jamais deux chronométreurs (D1, D2).

    **`UNIQUE(course_id, url)` et non `UNIQUE(url)`.** Une URL porte
    légitimement N épreuves — heats Klikego, multi-catégories Wiclax,
    multi-listes RaceResult, multi-épreuves Chronoplace, cf.
    `course_repository.list_by_source_url`. Un unique global sur `url` casserait
    ces quatre fournisseurs.

    **L'unicité de la source active est tenue par la base**, par un index
    partiel, et non par une lecture préalable : deux exploitants simultanés
    franchiraient tous deux la lecture, pas la contrainte.

    Cette table est, depuis #279, la **seule** vérité : `Course.source_url` et
    `Course.provider` ne sont plus des colonnes mais deux `hybrid_property` qui
    lisent la source active — écrire l'un ou l'autre lève.
    """

    __tablename__ = "course_sources"
    __table_args__ = (
        UniqueConstraint("course_id", "url", name="uq_course_source_url"),
        # Une seule source **active** par épreuve. L'index partiel est la seule
        # forme qui l'exprime sans interdire les passives, et **les deux
        # dialectes doivent être renseignés** — n'en donner qu'un produit un
        # index *complet* sur l'autre moteur, ce qui rendrait la deuxième source
        # d'une épreuve irreprésentable (même piège qu'`uq_role_global_slug`).
        Index(
            "uq_course_source_active",
            "course_id",
            unique=True,
            sqlite_where=text("is_active"),
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id"), index=True, nullable=False
    )
    url: Mapped[str] = mapped_column(String, nullable=False)
    #: Le fournisseur reconnu pour cette URL, tel que le résout `scrapers/registry`.
    provider: Mapped[str] = mapped_column(String, default="", nullable=False)
    #: Naît **passive** : une URL soumise pour une épreuve déjà connue ne prend
    #: pas la main, la première scrapée la garde (D3).
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    #: Nullable, et le restera : l'import — collage public, Sheet, re-scrape en
    #: batch — n'a pas d'utilisateur à nommer.
    #:
    #: **Sans `ondelete`**, comme partout dans le dépôt : `core/database.py`
    #: n'émet aucun `PRAGMA foreign_keys=ON`, la contrainte serait inerte en
    #: SQLite (dev et tests) et active en PostgreSQL.
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    #: Dernier scrape **de cette source**, distinct de `Course.scraped_at` : une
    #: source passive n'est pas scrapée, et le jour où elle devient active son
    #: horodatage propre dit s'il y a quelque chose à rafraîchir.
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    course: Mapped["Course"] = relationship(back_populates="sources")  # noqa: F821
    # Sens unique : aucune collection n'est ajoutée sur `User` — même critère que
    # `AllowedEmail.created_by`, personne ne lit « les sources que j'ai posées ».
    created_by: Mapped["User | None"] = relationship()  # noqa: F821
