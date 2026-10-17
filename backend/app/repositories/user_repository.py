"""Accès données pour User — seule couche qui touche la Session pour cette table.

La transaction reste portée par le service appelant (`services/auth/`), comme
dans `import_service` et `scrape_service` : on `flush()` pour peupler l'id, on ne
`commit()` jamais ici.
"""
from datetime import datetime

from sqlalchemy import Column, func, select, update
from sqlalchemy.orm import Session, selectinload

import app.models  # noqa: F401  registers every table on Base.metadata for the reference inventory
from app.core.database import Base
from app.core.email import normalize_email
from app.models.role import Role
from app.models.user import SYSTEM_USER_EMAIL, User
from app.models.user_group import UserGroup
from app.models.user_role import UserRole


def get(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_with_roles_and_groups(db: Session, user_id: int) -> User | None:
    """L'utilisateur, rôles et groupes déjà chargés — pour `GET /auth/me`.

    Six requêtes fixes (l'utilisateur, ses `UserRole`, leurs `Role`, les
    pouvoirs de ces rôles, ses `UserGroup`, leurs `Group`) au lieu d'une par
    rôle et par groupe portés : sans ces `selectinload`, chaque accès à
    `.role`, `.role.permissions` ou `.group` déclenche sa propre requête
    (#625).
    """
    return db.scalar(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.roles)
            .selectinload(UserRole.role)
            .selectinload(Role.permissions),
            selectinload(User.groups).selectinload(UserGroup.group),
        )
    )


def list_all(db: Session) -> list[User]:
    """Tous les utilisateurs, par adresse. **Sans pagination**, et c'est borné.

    Le peuplement d'`users` l'est par la liste d'autorisation (`allowed_emails`,
    #170) : une personne y naît d'une connexion réussie *et autorisée*.
    """
    return list(db.scalars(select(User).order_by(User.email, User.id)))


def find_by_email(db: Session, email: str) -> list[User]:
    """Les utilisateurs portant cette adresse — une **liste**, jamais un scalaire.

    `users.email` n'est pas unique, délibérément (#114, FR-003) : deux identités
    externes portant la même adresse donnent deux utilisateurs distincts. Rendre
    un scalaire rouvrirait le choix au hasard que `grant-role` doit refuser
    (FR-030).

    La casse est ignorée — une adresse ne la distingue pas côté domaine, et
    `Prenom.Nom@` saisi à la main ne doit pas rester introuvable.
    """
    return list(
        db.scalars(
            select(User)
            .where(func.lower(User.email) == normalize_email(email))
            .order_by(User.id)
        )
    )


def emails_with_account(db: Session, emails: list[str]) -> set[str]:
    """Parmi ces adresses, celles que porte au moins un compte — **en minuscules**.

    Une seule requête pour toute la liste : l'écran des accès (#170) l'appelle
    pour un tableau entier, et `find_by_email` par ligne y serait un N+1.

    La casse est ignorée, comme dans `find_by_email` et pour la même raison :
    `users.email` garde celle du fournisseur, `allowed_emails` la normalise.
    Comparer à l'égalité stricte rendrait « jamais connecté » sur un compte bien
    vivant.
    """
    if not emails:
        return set()
    return set(
        db.scalars(
            select(func.lower(User.email)).where(
                func.lower(User.email).in_({normalize_email(email) for email in emails})
            )
        )
    )


def create(db: Session, *, email: str, display_name: str = "") -> User:
    """Crée un utilisateur. **Aucune recherche par adresse** au préalable (FR-003).

    L'appelant ne doit pas non plus en faire une : l'adresse n'apparie jamais
    deux identités. Une identité externe inconnue crée toujours un nouvel
    utilisateur, même si l'adresse est déjà en base.
    """
    user = User(email=email, display_name=display_name)
    db.add(user)
    db.flush()
    return user


def refresh_profile(db: Session, user: User, *, email: str, display_name: str) -> User:
    """Aligne les attributs mutables sur ce que le fournisseur vient de dire (FR-008).

    Une valeur vide n'écrase rien : le fournisseur qui se tait ne doit pas effacer
    ce qu'un autre a renseigné.
    """
    if email:
        user.email = email
    if display_name:
        user.display_name = display_name
    db.flush()
    return user


def set_active(db: Session, users: list[User], *, active: bool) -> int:
    """Ouvre ou ferme des comptes. Rend le nombre de comptes **réellement changés**.

    Fermer un compte fait tomber ses sessions **immédiatement** : l'invariant de
    `session.resolve` est une jointure, jamais un cache (#114). C'est ce qui rend
    le retrait d'une adresse effectif au geste (#170, FR-016), sans avoir à
    parcourir `user_sessions`.

    Le compte rendu n'est pas décoratif : la CLI en fait un « 2 compte(s)
    réactivé(s) », et « rien à faire » se distingue ainsi d'un geste sans effet.
    """
    changes = [user for user in users if user.is_active != active]
    for user in changes:
        user.is_active = active
    db.flush()
    return len(changes)


#: Tables that belong to the account and leave with it through the ORM cascade of `User`.
_OWNED_TABLES = frozenset({"identities", "user_sessions", "user_roles", "user_groups", "athlete_claims"})


def _references_to_users() -> list[Column]:
    """Every column outside the account's own tables that points to `users.id` (#1326).

    Read from the schema rather than listed by hand: FKs carry no `ondelete` and are
    only enforced by PostgreSQL, so a forgotten column would surface in production
    only, as an `IntegrityError`.
    """
    return [
        foreign_key.parent
        for table in Base.metadata.sorted_tables
        if table.name not in _OWNED_TABLES
        for foreign_key in table.foreign_keys
        if foreign_key.column.table.name == User.__tablename__
    ]


def required_references() -> list[Column]:
    return [column for column in _references_to_users() if not column.nullable]


def optional_references() -> list[Column]:
    return [column for column in _references_to_users() if column.nullable]


def has_required_reference(db: Session, user_id: int) -> bool:
    return any(
        db.scalar(select(column).where(column == user_id).limit(1)) is not None
        for column in required_references()
    )


def detach_optional_references(db: Session, user_id: int) -> None:
    for column in optional_references():
        db.execute(update(column.table).where(column == user_id).values({column.name: None}))


def touch_last_seen(db: Session, user_id: int, now: datetime) -> None:
    """Sets `last_seen_at` to `now` unless it is already today: one write per day at most."""
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    db.execute(
        update(User)
        .where(User.id == user_id, User.last_seen_at < start_of_day)
        .values(last_seen_at=now)
    )


def list_inactive_without_role(db: Session, cutoff: datetime) -> list[User]:
    """Accounts with no role, last seen before `cutoff`, never the system account (#1326)."""
    return list(db.scalars(
        select(User)
        .where(
            User.last_seen_at < cutoff,
            User.email != SYSTEM_USER_EMAIL,
            ~select(UserRole.id).where(UserRole.user_id == User.id).exists(),
        )
        .order_by(User.id)
    ))


def delete(db: Session, user: User) -> None:
    """Deletes the account; identities, sessions, roles and groups follow by ORM cascade."""
    db.delete(user)
    db.flush()


def count_linked_by_athlete(db: Session, athlete_ids: list[int]) -> dict[int, int]:
    """Comptes rattachés à chacune de ces fiches (#1325) ; une fiche sans compte est absente."""
    rows = db.execute(
        select(User.athlete_id, func.count(User.id))
        .where(User.athlete_id.in_(athlete_ids))
        .group_by(User.athlete_id)
    )
    return {athlete_id: count for athlete_id, count in rows}


def set_athlete(db: Session, user: User, athlete_id: int | None) -> None:
    """Pose ou retire le rattachement validé du compte (#1325)."""
    user.athlete_id = athlete_id
    db.flush()


def ids_linked_to_athlete(db: Session, athlete_id: int) -> set[int]:
    return set(db.scalars(select(User.id).where(User.athlete_id == athlete_id)))


def repoint_athlete(db: Session, *, from_athlete_id: int, to_athlete_id: int) -> int:
    """Rattache à la fiche conservée les comptes liés à une fiche absorbée (#908)."""
    return db.execute(
        update(User).where(User.athlete_id == from_athlete_id).values(athlete_id=to_athlete_id)
    ).rowcount


def detach_athlete(db: Session, athlete_id: int) -> None:
    db.query(User).filter(User.athlete_id == athlete_id).update({User.athlete_id: None})
