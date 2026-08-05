"""Modèle RolePermission — un pouvoir porté par un rôle (#115)."""
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RolePermission(Base):
    """Le lien rôle → pouvoir. **Une chaîne, sans clé étrangère.**

    À lire dans le bon sens, la formulation « chaîne nue » ayant été comprise de
    travers (clarification du 2026-08-05) :

    - `permission_code` **est** une donnée en base, écrite et relue, modifiable à
      chaud par `PATCH /admin/roles/{id}` ;
    - « nue » qualifie l'**absence de clé étrangère**, pas l'absence de stockage.
      Le précédent explicite du dépôt est `Course.event_type` (`triathlon-m` en
      `String`, nomenclature tenue dans `core/discipline.py`) ;
    - ce qui n'existe pas, c'est une table `permissions` listant les codes
      possibles — un second inventaire doublant `core/permissions.py`.

    **Les lignes orphelines sont inertes par construction** : la garde ne demande
    jamais « quels codes ce rôle porte-t-il ? » mais « porte-t-il *ce* code ? »,
    et ce code est une constante de l'application. Un pouvoir retiré par une
    livraison n'est plus jamais interrogé ; l'API l'expose dans
    `stale_permissions` — hygiène, jamais correction (FR-042).

    Ce qu'une clé étrangère protégerait : rien. Le seul écrivain valide déjà les
    codes **soumis** contre le catalogue et rend 422.
    """

    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_code", name="uq_role_permission"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id"), index=True, nullable=False
    )
    permission_code: Mapped[str] = mapped_column(String, index=True, nullable=False)

    role: Mapped["Role"] = relationship(back_populates="permissions")  # noqa: F821
