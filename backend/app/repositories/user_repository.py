"""Accès données pour User — seule couche qui touche la Session pour cette table.

La transaction reste portée par le service appelant (`services/auth/`), comme
dans `import_service` et `scrape_service` : on `flush()` pour peupler l'id, on ne
`commit()` jamais ici.
"""
from sqlalchemy.orm import Session

from app.models.user import User


def get(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


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
