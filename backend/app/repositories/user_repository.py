"""Data access for User — the only layer allowed to touch the Session for this table."""
from sqlalchemy.orm import Session

from app.models.user import User


def get(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_by_github_id(db: Session, github_id: str) -> User | None:
    return db.query(User).filter(User.github_id == github_id).first()


def upsert_from_github(
    db: Session,
    *,
    github_id: str,
    github_login: str,
    email: str,
) -> tuple[User, bool]:
    """Create or refresh a User from a GitHub identity payload.

    Returns (user, created). `created` is True if a new row was inserted.
    Login and email are refreshed in place when the row already exists — the
    row is identified by `github_id` alone (FR-007, FR-010).
    """
    existing = get_by_github_id(db, github_id)
    if existing is not None:
        if existing.github_login != github_login:
            existing.github_login = github_login
        if existing.email != email:
            existing.email = email
        return existing, False

    user = User(github_id=github_id, github_login=github_login, email=email)
    db.add(user)
    db.flush()
    return user, True
