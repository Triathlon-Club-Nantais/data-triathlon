"""Member e-mail list by season (#1334)."""
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.member_email import SOURCE_IMPORT, SOURCE_MANUAL, MemberEmail
from app.repositories import member_email_repository


def _entry(db, email, season=2026, source=SOURCE_IMPORT) -> MemberEmail:
    entry = MemberEmail(email=email, season=season, source=source)
    db.add(entry)
    db.flush()
    return entry


def _emails(db, season=2026) -> dict[str, str]:
    return {e.email: e.source for e in member_email_repository.list_season(db, season)}


def test_an_address_appears_once_per_season(db_session):
    _entry(db_session, "anne@exemple.fr")
    _entry(db_session, "anne@exemple.fr", season=2025)

    with pytest.raises(IntegrityError):
        _entry(db_session, "anne@exemple.fr")


def test_replace_imported_adds_removes_and_keeps_manual_entries(db_session):
    _entry(db_session, "gone@exemple.fr")
    _entry(db_session, "kept@exemple.fr")
    _entry(db_session, "hand@exemple.fr", source=SOURCE_MANUAL)
    _entry(db_session, "both@exemple.fr", source=SOURCE_MANUAL)
    _entry(db_session, "gone@exemple.fr", season=2025)

    report = member_email_repository.replace_imported(
        db_session, 2026, {"kept@exemple.fr", "new@exemple.fr", "both@exemple.fr"}
    )

    assert report == (1, 1, 2)
    assert _emails(db_session) == {
        "both@exemple.fr": SOURCE_MANUAL,
        "hand@exemple.fr": SOURCE_MANUAL,
        "kept@exemple.fr": SOURCE_IMPORT,
        "new@exemple.fr": SOURCE_IMPORT,
    }
    assert _emails(db_session, 2025) == {"gone@exemple.fr": SOURCE_IMPORT}


def test_add_manual_inserts_a_new_address(db_session):
    entry = member_email_repository.add_manual(db_session, "anne@exemple.fr", 2026)

    assert (entry.email, entry.season, entry.source) == ("anne@exemple.fr", 2026, SOURCE_MANUAL)


def test_add_manual_promotes_an_imported_address(db_session):
    imported = _entry(db_session, "anne@exemple.fr")

    entry = member_email_repository.add_manual(db_session, "anne@exemple.fr", 2026)

    assert entry.id == imported.id
    assert entry.source == SOURCE_MANUAL


def test_add_manual_returns_none_when_already_manual(db_session):
    _entry(db_session, "anne@exemple.fr", source=SOURCE_MANUAL)

    assert member_email_repository.add_manual(db_session, "anne@exemple.fr", 2026) is None


def test_remove_deletes_any_entry_and_returns_it(db_session):
    entry = _entry(db_session, "anne@exemple.fr", source=SOURCE_MANUAL)

    removed = member_email_repository.remove(db_session, entry.id)

    assert removed.email == "anne@exemple.fr"
    assert _emails(db_session) == {}
    assert member_email_repository.remove(db_session, entry.id) is None


def test_list_season_is_sorted_by_address(db_session):
    _entry(db_session, "zoe@exemple.fr")
    _entry(db_session, "anne@exemple.fr")

    assert [e.email for e in member_email_repository.list_season(db_session, 2026)] == [
        "anne@exemple.fr", "zoe@exemple.fr",
    ]


def test_seasons_are_distinct_newest_first(db_session):
    _entry(db_session, "a@exemple.fr", season=2024)
    _entry(db_session, "b@exemple.fr", season=2026)
    _entry(db_session, "c@exemple.fr", season=2026)

    assert member_email_repository.seasons(db_session) == [2026, 2024]


def test_the_current_season_counts_once_it_has_an_entry(db_session):
    _entry(db_session, "a@exemple.fr", season=2025)
    _entry(db_session, "b@exemple.fr", season=2026)

    assert member_email_repository.counting_season(db_session, date(2026, 10, 11)) == 2026


def test_the_previous_season_counts_while_the_current_one_is_empty(db_session):
    _entry(db_session, "a@exemple.fr", season=2025)

    assert member_email_repository.counting_season(db_session, date(2026, 10, 11)) == 2025


def test_counts_looks_up_the_normalised_address_in_the_counting_season(db_session):
    _entry(db_session, "old@exemple.fr", season=2025)
    _entry(db_session, "anne@exemple.fr", season=2026)
    today = date(2026, 10, 11)

    assert member_email_repository.counts(db_session, " Anne@Exemple.FR ", today)
    assert not member_email_repository.counts(db_session, "old@exemple.fr", today)
    assert not member_email_repository.counts(db_session, "nobody@exemple.fr", today)


def test_a_manual_entry_alone_does_not_switch_the_counting_season(db_session):
    _entry(db_session, "old@exemple.fr", season=2025)
    _entry(db_session, "hand@exemple.fr", season=2026, source=SOURCE_MANUAL)
    today = date(2026, 10, 11)

    assert member_email_repository.counting_season(db_session, today) == 2025
    assert member_email_repository.counts(db_session, "old@exemple.fr", today)
    assert member_email_repository.counts(db_session, "hand@exemple.fr", today)


def test_add_manual_survives_a_concurrent_insert_of_the_same_address(db_session):
    _entry(db_session, "anne@exemple.fr", source=SOURCE_MANUAL)

    assert member_email_repository.add_manual(db_session, "anne@exemple.fr", 2026) is None
    assert _emails(db_session) == {"anne@exemple.fr": SOURCE_MANUAL}


def test_replace_imported_raises_on_a_concurrent_insert_and_keeps_the_session_usable(db_session, monkeypatch):
    _entry(db_session, "anne@exemple.fr")
    monkeypatch.setattr(member_email_repository, "list_season", lambda db, season: [])

    with pytest.raises(IntegrityError):
        member_email_repository.replace_imported(db_session, 2026, {"anne@exemple.fr", "new@exemple.fr"})

    monkeypatch.undo()
    assert _emails(db_session) == {"anne@exemple.fr": SOURCE_IMPORT}


def test_purge_before_counts_in_dry_run_then_deletes(db_session):
    _entry(db_session, "a@exemple.fr", season=2023)
    _entry(db_session, "b@exemple.fr", season=2024)
    _entry(db_session, "c@exemple.fr", season=2025)

    assert member_email_repository.purge_before(db_session, 2025, dry_run=True) == 2
    assert member_email_repository.seasons(db_session) == [2025, 2024, 2023]

    assert member_email_repository.purge_before(db_session, 2025, dry_run=False) == 2
    assert member_email_repository.seasons(db_session) == [2025]
