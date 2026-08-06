"""Modèle Group — un nom d'appartenance dans un club (#197)."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class Group(Base):
    """Un groupe : Codir, arbitres, commission bénévolat. **Il n'accorde rien.**

    C'est toute la différence avec `Role`, et elle est structurelle : un rôle dit
    ce qu'on **peut faire**, un groupe dit à quoi on **appartient**. Un groupe
    existe vide de droits, ce qu'un rôle sans pouvoir ne saurait être, et
    « liste-moi les membres du Codir » n'est rendu proprement par aucune
    agrégation de rôles.

    **Quatre différences avec `Role`**, dont trois sont nommées par #197 et la
    quatrième est ci-dessous :

    - pas d'`is_superuser` — un groupe n'accorde rien ;
    - pas d'invariant du dernier administrateur — le vider ne verrouille
      personne dehors ;
    - pas de non-amplification — il n'y a aucun pouvoir à amplifier ;
    - **`organisation_id` est non nul**. `roles.organisation_id` est nullable
      parce qu'un rôle **global** est une définition réutilisable — « validateur »
      a le même sens dans deux clubs. Un groupe est une composition, celle d'un
      club précis : « Codir » sans club ne désigne rien. C'est ce `NOT NULL` qui
      dispense cette table de l'index partiel `WHERE organisation_id IS NULL`
      qu'exige `roles.slug` — SQLite comme PostgreSQL tiennent deux `NULL` pour
      distincts —, et `user_groups` de toute colonne d'organisation.

    **Aucun groupe n'est semé** : la composition d'un CA n'est pas devinable par
    une migration. D'où l'absence d'`is_system`, qui protégerait de la
    suppression un groupe que personne n'a livré.
    """

    __tablename__ = "groups"
    __table_args__ = (
        UniqueConstraint("organisation_id", "slug", name="uq_group_org_slug"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(
        ForeignKey("organisations.id"), index=True, nullable=False
    )
    #: Immuable : c'est ce qui rend `PATCH {"slug": …}` un 422 et non un renommage.
    slug: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    #: **Sans cascade**, et c'est la moitié de la règle de suppression : le refus
    #: d'effacer un groupe peuplé est prononcé par le service, et une cascade le
    #: ferait tenir par le seul chemin — un appel direct viderait la table sans
    #: le dire. `Role` ne cascade pas non plus vers ses porteurs.
    members: Mapped[list["UserGroup"]] = relationship(  # noqa: F821
        back_populates="group"
    )
