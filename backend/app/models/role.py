"""Modèle Role — une composition de pouvoirs, éditable à chaud (#115)."""
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


class Role(Base):
    """Un rôle : un libellé renommable, un slug immuable, des pouvoirs.

    **`is_superuser` referme la seule objection sérieuse aux rôles en base** —
    « une fonctionnalité livrée mardi n'est administrable que si quelqu'un pense
    à cocher son pouvoir ». Un rôle superutilisateur franchit tout pouvoir,
    présent **et à venir** : une livraison n'exige ni migration, ni recochage, ni
    même que l'exploitant sache qu'elle a eu lieu (FR-014).

    Corollaire non négociable (FR-010) : `is_superuser` n'est posable **ni
    retirable** que par quelqu'un qui le porte déjà. C'est le seul attribut qui
    ne se compose pas.
    """

    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("organisation_id", "slug", name="uq_role_org_slug"),
        # SQLite comme PostgreSQL tiennent deux `NULL` pour **distincts** : la
        # contrainte ci-dessus laisse donc passer deux rôles globaux de même
        # slug. L'index partiel est la seule forme qui couvre le cas, et **les
        # deux dialectes doivent être renseignés** — n'en donner qu'un produit un
        # index *complet* sur l'autre moteur, ce qui interdirait silencieusement
        # un même slug dans deux organisations.
        Index(
            "uq_role_global_slug",
            "slug",
            unique=True,
            sqlite_where=text("organisation_id IS NULL"),
            postgresql_where=text("organisation_id IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    #: `NULL` = rôle partagé par toutes les organisations.
    organisation_id: Mapped[int | None] = mapped_column(
        ForeignKey("organisations.id"), index=True, nullable=True
    )
    #: Le seul nom qui traverse une frontière (`grant-role --role`, le semis).
    #: Immuable : c'est ce qui rend `PATCH {"slug": …}` un 422 et non un renommage.
    slug: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, default="", nullable=False)
    #: Semé par la migration : non supprimable (FR-006). **Reste modifiable** —
    #: livré ne veut pas dire figé.
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    permissions: Mapped[list["RolePermission"]] = relationship(  # noqa: F821
        back_populates="role", cascade="all, delete-orphan"
    )
