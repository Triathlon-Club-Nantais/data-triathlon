"""Tests for the User SQLAlchemy model (issue #114)."""
import pytest
from sqlalchemy.exc import IntegrityError


def test_user_can_be_created_with_minimal_fields(db_session):
    from app.models import User

    user = User(github_id="1234567", github_login="octocat", email="octo@example.com")
    db_session.add(user)
    db_session.flush()

    assert user.id is not None
    assert user.is_active is True
    assert user.created_at is not None
    assert user.athlete_id is None


def test_user_github_id_is_unique(db_session):
    from app.models import User

    db_session.add(
        User(github_id="42", github_login="alice", email="alice@example.com")
    )
    db_session.flush()

    db_session.add(
        User(github_id="42", github_login="alice2", email="alice2@example.com")
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_user_table_does_not_store_github_token():
    """FR-008 — the GitHub access token is used then forgotten, never persisted."""
    from app.models import User

    columns = set(User.__table__.columns.keys())
    forbidden = {"access_token", "github_token", "oauth_token", "token"}
    assert forbidden.isdisjoint(columns), (
        f"User model must not persist GitHub tokens; found: {forbidden & columns}"
    )
