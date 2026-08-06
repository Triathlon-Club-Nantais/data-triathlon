"""Modèle UserGroup — cette personne est membre de ce groupe (#197)."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class UserGroup(Base):
    """`(user, group)` — et rien d'autre.

    **Pas d'`organisation_id`**, contrairement à `user_roles`. Là-bas, la colonne
    est nécessaire : un rôle global doit dire dans quel club il s'applique. Ici,
    le groupe porte déjà son club ; répéter l'information rendrait représentable
    un état incohérent — `user_groups.organisation_id ≠ groups.organisation_id` —
    qu'aucune contrainte portable ne fermerait.

    `UNIQUE(user_id, group_id)` rend l'appartenance **idempotente sous
    concurrence** : c'est la contrainte qui le fait, pas une lecture préalable,
    que deux exploitants simultanés passeraient tous deux.

    `joined_at` dit depuis quand, jamais jusqu'à quand : une appartenance dure
    jusqu'à son retrait.

    **Pas d'`ondelete`**, mêmes raisons qu'en #114 et #115 : `core/database.py`
    n'émet aucun `PRAGMA foreign_keys=ON`, la contrainte serait inerte en SQLite
    et active en PostgreSQL. La cascade ORM depuis `User.groups` fait le travail
    des deux côtés.
    """

    __tablename__ = "user_groups"
    __table_args__ = (UniqueConstraint("user_id", "group_id", name="uq_user_group"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id"), index=True, nullable=False
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user: Mapped["User"] = relationship(back_populates="groups")  # noqa: F821
    group: Mapped["Group"] = relationship(back_populates="members")  # noqa: F821
