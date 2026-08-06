"""Accès données pour Group et UserGroup — seule couche qui touche la Session.

La transaction reste portée par le service appelant (`services/auth/groups.py`),
comme partout ailleurs : on `flush()` pour peupler l'id, on ne `commit()` jamais
ici.
"""
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.group import Group
from app.models.user import User
from app.models.user_group import UserGroup


def get(db: Session, group_id: int) -> Group | None:
    return db.get(Group, group_id)


def list_all(db: Session, *, organisation_id: int | None = None) -> list[Group]:
    """Les groupes, triés par slug. Sans `organisation_id`, tous.

    Pas de forme « les siens **et** les globaux » comme pour les rôles : un
    groupe global n'existe pas, sa colonne d'organisation étant non nulle.
    """
    query = select(Group).order_by(Group.slug)
    if organisation_id is not None:
        query = query.where(Group.organisation_id == organisation_id)
    return list(db.scalars(query))


def find_in_scope(db: Session, *, slug: str, organisation_id: int) -> Group | None:
    """Le groupe que ce slug désigne dans ce club, ou `None`.

    L'unicité porte sur le couple : deux clubs ont chacun leur Codir, et aucun
    ne voit celui de l'autre.
    """
    return db.scalar(
        select(Group).where(
            Group.slug == slug, Group.organisation_id == organisation_id
        )
    )


def create(
    db: Session,
    *,
    organisation_id: int,
    slug: str,
    name: str,
    description: str = "",
) -> Group:
    group = Group(
        organisation_id=organisation_id,
        slug=slug,
        name=name,
        description=description,
    )
    db.add(group)
    db.flush()
    return group


def delete(db: Session, group: Group) -> None:
    """Supprime le groupe. **Jamais ses membres** : la suppression d'un groupe
    encore peuplé est refusée en amont, par le service."""
    db.delete(group)


def count_members(db: Session, group_id: int) -> int:
    """Le nombre que le 409 de suppression doit nommer."""
    return db.scalar(
        select(func.count()).select_from(UserGroup).where(UserGroup.group_id == group_id)
    )


def list_members(db: Session, group_id: int) -> list[UserGroup]:
    """Les membres, dans l'**ordre d'affichage** — nom puis adresse.

    Sans tri explicite, la liste sortirait dans l'ordre des identifiants, donc
    dans l'ordre où les gens se sont connectés pour la première fois : stable,
    mais illisible pour qui cherche un nom.
    """
    return list(
        db.scalars(
            select(UserGroup)
            .join(User, User.id == UserGroup.user_id)
            .options(joinedload(UserGroup.user))
            .where(UserGroup.group_id == group_id)
            .order_by(User.display_name, User.email)
        )
    )


def find_member(db: Session, *, group_id: int, user_id: int) -> UserGroup | None:
    return db.scalar(
        select(UserGroup).where(
            UserGroup.group_id == group_id, UserGroup.user_id == user_id
        )
    )


def add_member(db: Session, *, group_id: int, user_id: int) -> tuple[UserGroup, bool]:
    """Ajoute le membre. Rend `(membership, créée)` — **idempotent**.

    L'insertion est tentée d'abord, sous point de reprise, et c'est délibéré :
    une lecture préalable serait franchie par deux exploitants simultanés, là où
    `UNIQUE(user_id, group_id)` ne l'est jamais. Le `SAVEPOINT` est ce qui permet
    de rattraper la violation sans perdre la transaction en cours. Reprise exacte
    de `user_role_repository.grant`.
    """
    membership = UserGroup(group_id=group_id, user_id=user_id)
    try:
        with db.begin_nested():
            db.add(membership)
            db.flush()
    except IntegrityError:
        existing = find_member(db, group_id=group_id, user_id=user_id)
        if existing is None:  # pragma: no cover — une autre contrainte a cédé
            raise
        return existing, False
    return membership, True


def remove_member(db: Session, *, group_id: int, user_id: int) -> bool:
    """Retire le membre. Rend `False` s'il ne l'était pas — jamais d'erreur."""
    membership = find_member(db, group_id=group_id, user_id=user_id)
    if membership is None:
        return False
    db.delete(membership)
    db.flush()
    return True
