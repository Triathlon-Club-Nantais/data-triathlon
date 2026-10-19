"""Member e-mail list: AssoConnect import, manual add and removal (#1334)."""
from datetime import date

import pytest

from app.core.exceptions import NotFoundError
from app.core.season import SeasonOutOfRangeError
from app.models.admin_action_log import AdminActionLog
from app.models.member_email import SOURCE_IMPORT, SOURCE_MANUAL
from app.repositories import member_email_repository, user_repository
from app.services import member_emails_service
from app.services.auth.allowed_emails import InvalidEmailError
from app.services.member_emails_service import (
    AlreadyListedError,
    ConcurrentImportError,
    MissingEmailColumnError,
    NoValidEmailError,
)


@pytest.fixture
def admin(db_session):
    user = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()
    return user


def _import(db, content: bytes, season=2026, filename="export.csv", user_id=None):
    return member_emails_service.import_file(
        db, season=season, content=content, filename=filename, user_id=user_id
    )


def _emails(db, season=2026) -> dict[str, str]:
    return {e.email: e.source for e in member_email_repository.list_season(db, season)}


def _last_log(db) -> AdminActionLog:
    return db.query(AdminActionLog).order_by(AdminActionLog.id.desc()).first()


@pytest.mark.parametrize("header", ["Email", "E-mail", "Adresse e-mail", "Courriel", "Adresse électronique"])
def test_recognised_email_headers(db_session, header):
    report = _import(db_session, f"Nom,{header}\nMARTIN,anne@exemple.fr\n".encode())

    assert report.added == 1
    assert _emails(db_session) == {"anne@exemple.fr": SOURCE_IMPORT}


def test_import_normalises_merges_duplicates_and_counts_invalid_rows(db_session):
    content = b"email\njeanne@exemple.fr\nPAUL@Exemple.fr \nfaux\n\njeanne@EXEMPLE.fr\n,\n"

    report = _import(db_session, content)

    assert (report.season, report.added, report.removed, report.unchanged, report.ignored) == (2026, 2, 0, 0, 1)
    assert _emails(db_session) == {"jeanne@exemple.fr": SOURCE_IMPORT, "paul@exemple.fr": SOURCE_IMPORT}


def test_the_first_recognised_column_is_read(db_session):
    _import(db_session, b"Courriel,Email\nfirst@exemple.fr,second@exemple.fr\n")

    assert _emails(db_session) == {"first@exemple.fr": SOURCE_IMPORT}


def test_no_other_column_is_stored(db_session):
    _import(db_session, "Nom,Prénom,Téléphone,Email\nMARTIN,Anne,0600000000,anne@exemple.fr\n".encode())

    (entry,) = member_email_repository.list_season(db_session, 2026)
    stored = {column.key: getattr(entry, column.key) for column in entry.__table__.columns}
    assert not {"MARTIN", "Anne", "0600000000"} & {str(v) for v in stored.values()}


def test_reimport_removes_absent_imported_addresses_and_keeps_manual_ones(db_session, admin):
    _import(db_session, b"email\njeanne@exemple.fr\npaul@exemple.fr\n")
    member_emails_service.add(db_session, email="hand@exemple.fr", season=2026, user_id=admin.id)

    report = _import(db_session, b"email\npaul@exemple.fr\n")

    assert (report.added, report.removed, report.unchanged) == (0, 1, 1)
    assert _emails(db_session) == {"hand@exemple.fr": SOURCE_MANUAL, "paul@exemple.fr": SOURCE_IMPORT}


def test_a_file_without_email_column_is_refused_without_writing(db_session):
    _import(db_session, b"email\njeanne@exemple.fr\n")

    with pytest.raises(MissingEmailColumnError) as refused:
        _import(db_session, b"Nom,Prenom\nMARTIN,Anne\n")

    assert refused.value.status_code == 422
    assert _emails(db_session) == {"jeanne@exemple.fr": SOURCE_IMPORT}


@pytest.mark.parametrize("content", [b"email\n", b"email\nfaux\n\n"])
def test_a_file_without_valid_address_is_refused_without_writing(db_session, content):
    _import(db_session, b"email\njeanne@exemple.fr\n")

    with pytest.raises(NoValidEmailError) as refused:
        _import(db_session, content)

    assert refused.value.status_code == 422
    assert _emails(db_session) == {"jeanne@exemple.fr": SOURCE_IMPORT}


def test_a_season_out_of_range_is_refused(db_session):
    with pytest.raises(SeasonOutOfRangeError):
        _import(db_session, b"email\na@exemple.fr\n", season=1999)
    with pytest.raises(SeasonOutOfRangeError):
        member_emails_service.add(db_session, email="a@exemple.fr", season=2101, user_id=None)


def test_import_is_audited(db_session, admin):
    _import(db_session, b"email\na@exemple.fr\n", user_id=admin.id)

    log = _last_log(db_session)
    assert (log.action, log.entity_type, log.entity_id) == ("member_emails.import", "member_emails_season", 2026)
    assert log.payload == {"added": 1, "removed": 0, "unchanged": 0, "ignored": 0}


def test_add_normalises_and_promotes_an_imported_address(db_session, admin):
    _import(db_session, b"email\nanne@exemple.fr\n")

    entry = member_emails_service.add(db_session, email=" Anne@Exemple.fr ", season=2026, user_id=admin.id)

    assert (entry.email, entry.source) == ("anne@exemple.fr", SOURCE_MANUAL)
    log = _last_log(db_session)
    assert (log.action, log.entity_type, log.entity_id) == ("member_emails.add", "member_email", entry.id)


def test_add_refuses_an_invalid_address(db_session):
    with pytest.raises(InvalidEmailError):
        member_emails_service.add(db_session, email="faux", season=2026, user_id=None)


def test_add_refuses_an_address_already_added_by_hand(db_session):
    member_emails_service.add(db_session, email="anne@exemple.fr", season=2026, user_id=None)

    with pytest.raises(AlreadyListedError) as refused:
        member_emails_service.add(db_session, email="ANNE@exemple.fr", season=2026, user_id=None)

    assert refused.value.status_code == 409


def test_remove_deletes_the_entry_and_is_audited(db_session, admin):
    entry = member_emails_service.add(db_session, email="anne@exemple.fr", season=2026, user_id=None)

    member_emails_service.remove(db_session, entry_id=entry.id, user_id=admin.id)

    assert _emails(db_session) == {}
    log = _last_log(db_session)
    assert (log.action, log.entity_type, log.entity_id) == ("member_emails.remove", "member_email", entry.id)
    with pytest.raises(NotFoundError):
        member_emails_service.remove(db_session, entry_id=entry.id, user_id=admin.id)


def test_list_season_reports_the_counting_season(db_session):
    _import(db_session, b"email\nold@exemple.fr\n", season=2025)

    listed = member_emails_service.list_season(db_session, 2026, date(2026, 10, 11))

    assert (listed.season, listed.counting_season, listed.seasons, listed.entries) == (2026, 2025, [2025], [])


def test_the_season_error_is_shared_with_the_club_members_import():
    from app.services import club_members_service

    assert club_members_service.SeasonOutOfRangeError is SeasonOutOfRangeError


@pytest.mark.parametrize("cell", ["Jeanne <jeanne@exemple.fr>", "jeanne@exemple.fr jeanne", "<jeanne@exemple.fr>"])
def test_only_a_bare_address_is_imported(db_session, cell):
    report = _import(db_session, f'email\n"{cell}"\npaul@exemple.fr\n'.encode())

    assert report.ignored == 1
    assert _emails(db_session) == {"paul@exemple.fr": SOURCE_IMPORT}


def test_add_refuses_a_named_address(db_session):
    with pytest.raises(InvalidEmailError) as refused:
        member_emails_service.add(db_session, email="Jeanne <jeanne@exemple.fr>", season=2026, user_id=None)

    assert refused.value.status_code == 422
    assert "prenom.nom@exemple.fr" in refused.value.message


def test_a_concurrent_change_during_import_is_a_french_409(db_session, monkeypatch):
    member_emails_service.add(db_session, email="anne@exemple.fr", season=2026, user_id=None)
    monkeypatch.setattr(member_email_repository, "list_season", lambda db, season: [])

    with pytest.raises(ConcurrentImportError) as refused:
        _import(db_session, b"email\nanne@exemple.fr\n")

    assert refused.value.status_code == 409
    assert refused.value.message == "La liste a été modifiée pendant l'import, réessayez."
