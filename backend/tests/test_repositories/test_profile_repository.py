"""L'accès données des profils individuels (#867) — tri, journal, isolation.

Patron `tests/test_auth/test_group_repository.py`.
"""
import pytest

from app.models.organisation import Organisation
from app.repositories import profile_repository


@pytest.fixture
def organisation(db_session):
    ligne = Organisation(slug="tcn", name="Triathlon Club Nantais")
    db_session.add(ligne)
    db_session.flush()
    return ligne


@pytest.fixture
def profile(db_session, organisation):
    return profile_repository.create(
        db_session,
        organisation_id=organisation.id,
        first_name="Alix",
        last_name="Martin",
    )


def test_creating_a_profile_populates_its_id(db_session, profile):
    assert profile.id is not None
    assert profile.first_name == "Alix"
    assert profile.last_name == "Martin"


def test_profiles_come_out_sorted_by_last_name_then_first_name(db_session, organisation):
    profile_repository.create(
        db_session, organisation_id=organisation.id, first_name="Zoé", last_name="Martin"
    )
    profile_repository.create(
        db_session, organisation_id=organisation.id, first_name="Alix", last_name="Dupont"
    )

    profiles = profile_repository.list_all(db_session)

    assert [(p.last_name, p.first_name) for p in profiles] == [
        ("Dupont", "Alix"),
        ("Martin", "Zoé"),
    ]


def test_get_returns_none_for_an_unknown_id(db_session):
    assert profile_repository.get(db_session, 9999) is None


def test_update_changes_only_the_given_fields(db_session, profile):
    profile_repository.update(db_session, profile, notes="Allergie aux fruits à coque.")

    assert profile.notes == "Allergie aux fruits à coque."
    assert profile.first_name == "Alix"


def test_adding_a_log_entry_populates_its_id(db_session, profile):
    entry = profile_repository.add_log_entry(
        db_session, profile_id=profile.id, text="Première séance, bon niveau natation."
    )

    assert entry.id is not None
    assert entry.text == "Première séance, bon niveau natation."
    assert entry.entry_date is not None


def test_log_entries_come_out_most_recent_first(db_session, profile):
    import datetime

    old = profile_repository.add_log_entry(
        db_session,
        profile_id=profile.id,
        text="Ancienne entrée",
        entry_date=datetime.date(2026, 1, 1),
    )
    recent = profile_repository.add_log_entry(
        db_session,
        profile_id=profile.id,
        text="Entrée récente",
        entry_date=datetime.date(2026, 6, 1),
    )

    entries = profile_repository.list_log_entries(db_session, profile.id)

    assert [entry.id for entry in entries] == [recent.id, old.id]


def test_log_entries_of_another_profile_do_not_leak(db_session, organisation, profile):
    other = profile_repository.create(
        db_session, organisation_id=organisation.id, first_name="Zoé", last_name="Roux"
    )
    profile_repository.add_log_entry(db_session, profile_id=profile.id, text="Pour Alix")
    profile_repository.add_log_entry(db_session, profile_id=other.id, text="Pour Zoé")

    entries = profile_repository.list_log_entries(db_session, profile.id)

    assert [entry.text for entry in entries] == ["Pour Alix"]
