"""Accès données pour User — seule couche qui touche la Session pour cette table.

La transaction reste portée par le service appelant (`services/auth/`), comme
dans `import_service` et `scrape_service` : on `flush()` pour peupler l'id, on ne
`commit()` jamais ici.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.role import Role
from app.models.user import User
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
            .where(func.lower(User.email) == email.strip().lower())
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
                func.lower(User.email).in_({email.strip().lower() for email in emails})
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
