"""Tests for user_repository (issue #114)."""


def test_get_by_github_id_returns_none_when_missing(db_session):
    from app.repositories import user_repository

    assert user_repository.get_by_github_id(db_session, "unknown") is None


def test_upsert_from_github_creates_new_user(db_session):
    from app.repositories import user_repository

    user, created = user_repository.upsert_from_github(
        db_session,
        github_id="1234567",
        github_login="octocat",
        email="octo@example.com",
    )

    assert created is True
    assert user.id is not None
    assert user.github_id == "1234567"
    assert user.github_login == "octocat"
    assert user.email == "octo@example.com"


def test_upsert_from_github_updates_existing_user(db_session):
    from app.repositories import user_repository

    original, _ = user_repository.upsert_from_github(
        db_session,
        github_id="1234567",
        github_login="octocat",
        email="octo@example.com",
    )
    updated, created = user_repository.upsert_from_github(
        db_session,
        github_id="1234567",
        github_login="octocat-renamed",
        email="new@example.com",
    )

    assert created is False
    assert updated.id == original.id
    assert updated.github_login == "octocat-renamed"
    assert updated.email == "new@example.com"


def test_upsert_from_github_distinguishes_users_sharing_email(db_session):
    """FR-010 — two distinct github_id sharing an email create two records."""
    from app.models import User
    from app.repositories import user_repository

    alice, _ = user_repository.upsert_from_github(
        db_session, github_id="A", github_login="alice", email="shared@example.com"
    )
    bob, created_bob = user_repository.upsert_from_github(
        db_session, github_id="B", github_login="bob", email="shared@example.com"
    )

    assert created_bob is True
    assert alice.id != bob.id
    assert db_session.query(User).count() == 2
