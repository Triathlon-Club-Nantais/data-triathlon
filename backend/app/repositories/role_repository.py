"""Accès données pour Role et Organisation — seule couche qui touche la Session.

La transaction reste portée par le service appelant (`services/auth/`), comme
partout ailleurs : on `flush()` pour peupler l'id, on ne `commit()` jamais ici.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.organisation import Organisation
from app.models.role import Role
from app.models.user_role import UserRole


def get(db: Session, role_id: int) -> Role | None:
    return db.get(Role, role_id)


def list_all(db: Session, *, organisation_id: int | None = None) -> list[Role]:
    """Les rôles visibles depuis une organisation : les siens **et** les globaux.

    Sans `organisation_id`, tous — c'est la vue d'un exploitant, l'installation
    n'ayant qu'un club. `.permissions` déjà chargé (#625) : `role_view` le lit
    systématiquement, et sans `selectinload` chaque rôle paierait sa propre
    requête pour l'obtenir.
    """
    requete = select(Role).options(selectinload(Role.permissions)).order_by(Role.slug)
    if organisation_id is not None:
        requete = requete.where(
            (Role.organisation_id == organisation_id) | (Role.organisation_id.is_(None))
        )
    return list(db.scalars(requete))


def count_holders_by_role(db: Session, role_ids: list[int]) -> dict[int, int]:
    """Le nombre de porteurs par rôle, en une seule requête agrégée (#625) —
    pour un écran qui rend une liste de rôles, plutôt qu'un `count_holders`
    par rôle. Un `role_id` absent du résultat n'a aucun porteur."""
    if not role_ids:
        return {}
    lignes = db.execute(
        select(UserRole.role_id, func.count())
        .where(UserRole.role_id.in_(role_ids))
        .group_by(UserRole.role_id)
    ).all()
    return dict(lignes)


def list_by_slug(db: Session, slug: str) -> list[Role]:
    """Tous les rôles portant ce slug, toutes portées confondues.

    Rend une **liste** parce que deux portées peuvent le partager : c'est ce qui
    permet à `grant-role` de dire « ce rôle est propre à tel club » plutôt que
    « slug inconnu ».
    """
    return list(db.scalars(select(Role).where(Role.slug == slug).order_by(Role.id)))


def find_in_scope(
    db: Session, *, slug: str, organisation_id: int | None = None
) -> Role | None:
    """Le rôle que ce slug désigne depuis cette organisation.

    Le plus spécifique gagne : sans cela, créer un `validator` propre au club
    serait sans effet, le global l'ayant toujours devancé.
    """
    candidats = list_by_slug(db, slug)
    propres = [role for role in candidats if role.organisation_id == organisation_id]
    if propres:
        return propres[0]
    globaux = [role for role in candidats if role.organisation_id is None]
    return globaux[0] if globaux else None


def create(
    db: Session,
    *,
    slug: str,
    name: str,
    description: str = "",
    organisation_id: int | None = None,
    is_system: bool = False,
    is_superuser: bool = False,
) -> Role:
    role = Role(
        slug=slug,
        name=name,
        description=description,
        organisation_id=organisation_id,
        is_system=is_system,
        is_superuser=is_superuser,
    )
    db.add(role)
    db.flush()
    return role


def delete(db: Session, role: Role) -> None:
    """Supprime le rôle et, par cascade ORM, ses pouvoirs. **Jamais** ses porteurs.

    Aucune cascade sur les attributions : supprimer un rôle qui dépouille
    silencieusement trois personnes est exactement ce qu'on rend explicite par un
    409 (FR-007).
    """
    db.delete(role)


def count_holders(db: Session, role_id: int) -> int:
    """Le nombre que le 409 de suppression doit nommer."""
    return db.scalar(
        select(func.count()).select_from(UserRole).where(UserRole.role_id == role_id)
    )


def find_organisation(db: Session, slug: str) -> Organisation | None:
    return db.scalar(select(Organisation).where(Organisation.slug == slug))


def get_organisation(db: Session, organisation_id: int) -> Organisation | None:
    return db.get(Organisation, organisation_id)


def list_organisations(db: Session) -> list[Organisation]:
    """Toutes les organisations. Un rôle **global** est superutilisateur partout :
    le décocher peut verrouiller n'importe quel club, pas seulement le sien."""
    return list(db.scalars(select(Organisation).order_by(Organisation.id)))


def default_organisation(db: Session) -> Organisation | None:
    """L'organisation par défaut : la première, et il n'y en a qu'une.

    Valeur par défaut de `grant-role --organisation`. Le jour où un second club
    existera, l'option cessera d'être facultative — c'est un choix d'ergonomie,
    pas un modèle qui suppose l'unicité.
    """
    return db.scalar(select(Organisation).order_by(Organisation.id).limit(1))
