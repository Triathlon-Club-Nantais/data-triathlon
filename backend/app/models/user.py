"""Modèle User — l'identité applicative d'un contributeur (#114)."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class User(Base):
    """Une personne côté application, née d'une connexion réussie et autorisée.

    **`email` n'est délibérément pas unique** : deux identités externes portant
    la même adresse donnent deux utilisateurs distincts (FR-003). Poser un
    UNIQUE ici forcerait un appariement par adresse et rouvrirait la prise de
    contrôle par pré-inscription — un attaquant créant chez un fournisseur
    laxiste un compte à l'adresse d'un contributeur. Ne pas « corriger ».

    **Ne porte aucun rôle** (FR-041) : on est administrateur *d'un club*, pas
    administrateur tout court. Le rôle de #115 vit dans une association
    `(user, organisation, role)`, hors de cette table — le même raisonnement
    qui place le futur mot de passe sur `identities`. C'est `roles` ci-dessous,
    une collection d'attributions, et **aucune colonne** n'a été ajoutée ici.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, index=True)
    # `display_name` ne figure pas dans le tableau de `data-model.md`, mais
    # `contracts/auth-api.md` l'expose sur `GET /auth/me` en le disant « venu du
    # fournisseur ». Rien d'autre en base ne peut le rendre : c'est un attribut
    # mutable du fournisseur, rafraîchi à chaque connexion au même titre que
    # l'adresse (FR-008). L'écart est celui-là, et il est additif.
    display_name: Mapped[str] = mapped_column(String, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # Sans `ondelete` : `database.py` n'émet aucun `PRAGMA foreign_keys=ON`, la
    # contrainte serait inerte en SQLite (dev et tests) et active en PostgreSQL.
    #
    # **Colonne seule, sans `relationship`** : rien ici ne lit l'athlète
    # rattaché, et un attribut dont le seul comportement serait de lever
    # (`lazy="raise"`) est un attribut qui existe pour ne pas servir. #117 la
    # posera quand quelque chose la lira — une `relationship` n'émet aucun DDL,
    # l'ajouter ne coûtera pas de migration. Cardinalité que la colonne fixe :
    # **N utilisateurs → 1 athlète**, sans `UNIQUE`, et c'est FR-003 qui
    # l'impose — une identité externe inconnue créant toujours un nouvel
    # utilisateur, une même personne en aura plusieurs.
    athlete_id: Mapped[int | None] = mapped_column(
        ForeignKey("athletes.id"), index=True, nullable=True
    )

    identities: Mapped[list["Identity"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["UserSession"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    # Patron exact des deux précédentes (#114) : cascade ORM, **pas** d'`ondelete`.
    # Supprimer un utilisateur emporte ses attributions et **jamais** les rôles
    # eux-mêmes (FR-013).
    roles: Mapped[list["UserRole"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    # Même patron, et pour la même raison (#197) : supprimer un utilisateur
    # emporte ses appartenances et **jamais** les groupes eux-mêmes. La
    # dissymétrie avec `Group.members`, qui ne cascade pas, est voulue : une
    # personne supprimée n'a plus d'appartenance possible, là où un groupe
    # supprimé effacerait la composition d'une commission.
    groups: Mapped[list["UserGroup"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
