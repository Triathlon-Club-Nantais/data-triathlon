"""Accès données pour UserRole — l'attribution d'un rôle, seule couche Session."""
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole


def list_for_user(
    db: Session, user_id: int, *, organisation_id: int | None = None
) -> list[UserRole]:
    """Les attributions de cet utilisateur, `.role` et `.role.permissions`
    déjà chargés — `authorization.py` lit systématiquement les deux pour
    trancher le superutilisateur et les codes portés, et sans `selectinload`
    chaque attribution paierait sa propre requête pour l'un et l'autre (#625).
    """
    requete = select(UserRole).where(UserRole.user_id == user_id).options(
        selectinload(UserRole.role).selectinload(Role.permissions)
    )
    if organisation_id is not None:
        requete = requete.where(UserRole.organisation_id == organisation_id)
    return list(db.scalars(requete.order_by(UserRole.id)))


def find(
    db: Session, *, user_id: int, role_id: int, organisation_id: int
) -> UserRole | None:
    return db.scalar(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
            UserRole.organisation_id == organisation_id,
        )
    )


def grant(
    db: Session, *, user_id: int, role_id: int, organisation_id: int
) -> tuple[UserRole, bool]:
    """Attribue le rôle. Rend `(attribution, créée)` — **idempotent** (FR-012).

    L'insertion est tentée d'abord, sous point de reprise, et c'est délibéré :
    une lecture préalable serait franchie par deux exploitants simultanés, là où
    `UNIQUE(user_id, role_id, organisation_id)` ne l'est jamais. Le `SAVEPOINT`
    est ce qui permet de rattraper la violation sans perdre la transaction en
    cours.
    """
    attribution = UserRole(
        user_id=user_id, role_id=role_id, organisation_id=organisation_id
    )
    try:
        with db.begin_nested():
            db.add(attribution)
            db.flush()
    except IntegrityError:
        existante = find(
            db, user_id=user_id, role_id=role_id, organisation_id=organisation_id
        )
        if existante is None:  # pragma: no cover — une autre contrainte a cédé
            raise
        return existante, False
    return attribution, True


def revoke(db: Session, *, user_id: int, role_id: int, organisation_id: int) -> bool:
    """Retire l'attribution. Rend `False` si elle n'existait pas — jamais d'erreur."""
    attribution = find(
        db, user_id=user_id, role_id=role_id, organisation_id=organisation_id
    )
    if attribution is None:
        return False
    db.delete(attribution)
    db.flush()
    return True


def count_active_superusers(db: Session, organisation_id: int) -> int:
    """Combien de comptes **actifs** franchissent tout dans cette organisation.

    « Actifs » au sens de #114 : un compte désactivé ne compte pas, ses sessions
    étant déjà tombées. Sans cette condition, l'invariant du dernier
    administrateur laisserait une installation verrouillée derrière un compte
    qui ne peut plus se connecter.

    Compte des **utilisateurs distincts** : deux rôles superutilisateur portés
    par la même personne ne font pas deux administrateurs.
    """
    return db.scalar(
        select(func.count(func.distinct(UserRole.user_id)))
        .join(Role, Role.id == UserRole.role_id)
        .join(User, User.id == UserRole.user_id)
        .where(
            UserRole.organisation_id == organisation_id,
            Role.is_superuser.is_(True),
            User.is_active.is_(True),
        )
    )
