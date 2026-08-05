"""Modèle UserRole — l'attribution d'un rôle à quelqu'un, dans un club (#115)."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class UserRole(Base):
    """`(user, organisation, role)` — l'association que `users` ne porte pas.

    **`role_id`, pas `role`.** C'est toute la différence avec un scalaire : le
    renommage d'un rôle est gratuit là où une chaîne en aurait fait une migration
    de données (FR-005).

    `UNIQUE(user_id, role_id, organisation_id)` rend l'attribution **idempotente
    sous concurrence** (FR-012) — c'est la contrainte qui le fait, pas une
    lecture préalable, que deux exploitants simultanés passeraient tous deux.

    **Pas d'`ondelete`**, même raison qu'en #114 : `core/database.py` n'émet
    aucun `PRAGMA foreign_keys=ON`, la contrainte serait inerte en SQLite et
    active en PostgreSQL. La cascade ORM depuis `User.roles` fait le travail des
    deux côtés.
    """

    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "role_id", "organisation_id", name="uq_user_role_org"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id"), index=True, nullable=False
    )
    #: **Non nul** — c'est ce que la table `organisations` achète : une colonne
    #: nullable imposerait ici les deux index d'unicité de `roles.slug`.
    organisation_id: Mapped[int] = mapped_column(
        ForeignKey("organisations.id"), index=True, nullable=False
    )
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user: Mapped["User"] = relationship(back_populates="roles")  # noqa: F821
    role: Mapped["Role"] = relationship()  # noqa: F821
