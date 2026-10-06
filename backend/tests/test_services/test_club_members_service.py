"""Licenciés du club : synchro FFTri, import de fichier, rattachement (#1202)."""
from datetime import date

import pytest

from app.core.exceptions import DomainError, NotFoundError
from app.core.identity import identity_hash
from app.models.admin_action_log import AdminActionLog
from app.models.athlete import Athlete
from app.models.club_member import (
    LINK_AMBIGUOUS,
    LINK_AUTO,
    LINK_MANUAL,
    LINK_UNLINKED,
    SOURCE_FFTRI,
    SOURCE_FILE,
)
from app.repositories import (
    athlete_alias_repository,
    club_member_repository,
    course_repository,
    opposition_repository,
    participation_repository,
    user_repository,
)
from app.scrapers.fftri_club_members import ClubRoster, RosterMember, RosterUnreadableError
from app.services import club_members_service


def _athlete(db, nom, prenom, **fields):
    athlete = Athlete(nom=nom, prenom=prenom, **fields)
    db.add(athlete)
    db.flush()
    return athlete


@pytest.fixture
def admin(db_session):
    user = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()
    return user


@pytest.fixture
def roster(monkeypatch):
    members = [
        RosterMember("MARTIN", "Anne", "F", "C1"),
        RosterMember("DURAND", "Paul", "M", "C2"),
        RosterMember("INCONNU", "Zoé", "F", "C3"),
    ]
    monkeypatch.setattr(
        club_members_service.fftri_club_members, "fetch_club_roster",
        lambda url: ClubRoster(licence_year=2027, members=members),
    )
    return members


def test_sync_stores_the_licence_season_and_links_unique_records(db_session, admin, roster):
    martin = _athlete(db_session, "Martin", "Anne")
    _athlete(db_session, "DURAND", "Paul")
    _athlete(db_session, "DURAND", "Paul", homonym_rank=1)

    report = club_members_service.sync_from_fftri(db_session, user_id=admin.id)

    assert report == club_members_service.MembersSyncReport(
        season=2026, total=3, linked=1, unlinked=1, ambiguous=1
    )
    rows = {m.licence_id: m for m in club_member_repository.list_season(db_session, 2026)}
    assert (rows["C1"].athlete_id, rows["C1"].link_status) == (martin.id, LINK_AUTO)
    assert (rows["C2"].athlete_id, rows["C2"].link_status) == (None, LINK_AMBIGUOUS)
    assert (rows["C3"].athlete_id, rows["C3"].link_status) == (None, LINK_UNLINKED)
    assert {m.source for m in rows.values()} == {SOURCE_FFTRI}


def test_sync_links_through_a_spelling_variant(db_session, admin, roster):
    kept = _athlete(db_session, "MARTINE", "Anne")
    athlete_alias_repository.add(db_session, ("martin", "anne"), kept.id)

    club_members_service.sync_from_fftri(db_session, user_id=admin.id)

    rows = {m.licence_id: m for m in club_member_repository.list_season(db_session, 2026)}
    assert rows["C1"].athlete_id == kept.id


def test_a_manual_link_survives_the_next_sync(db_session, admin, roster):
    chosen = _athlete(db_session, "DURAND", "Paul")
    _athlete(db_session, "DURAND", "Paul", homonym_rank=1)
    club_members_service.sync_from_fftri(db_session, user_id=admin.id)
    ambiguous = next(m for m in club_member_repository.list_season(db_session, 2026) if m.licence_id == "C2")

    club_members_service.link_member(db_session, member_id=ambiguous.id, athlete_id=chosen.id, user_id=admin.id)
    club_members_service.sync_from_fftri(db_session, user_id=admin.id)

    again = next(m for m in club_member_repository.list_season(db_session, 2026) if m.licence_id == "C2")
    assert (again.athlete_id, again.link_status) == (chosen.id, LINK_MANUAL)


def test_sync_recomputes_the_tcn_counters(db_session, admin, roster):
    martin = _athlete(db_session, "MARTIN", "Anne")
    course = course_repository.get_or_create(
        db_session, name="Tri", event_date=date(2026, 10, 4), event_type="triathlon-m"
    )
    result = participation_repository.create(
        db_session, athlete_id=martin.id, course_id=course.id, bib_number="1", status="finisher"
    )

    club_members_service.sync_from_fftri(db_session, user_id=admin.id)

    db_session.refresh(result)
    assert result.counts_for_tcn


def test_sync_records_an_audit_entry(db_session, admin, roster):
    club_members_service.sync_from_fftri(db_session, user_id=admin.id)

    log = db_session.query(AdminActionLog).one()
    assert (log.action, log.entity_type, log.entity_id) == ("club_members.sync", "club_members_season", 2026)


def test_an_unreadable_page_is_a_502_domain_error(db_session, admin, monkeypatch):
    def broken(url):
        raise RosterUnreadableError("aucun licencié lu")

    monkeypatch.setattr(club_members_service.fftri_club_members, "fetch_club_roster", broken)

    with pytest.raises(club_members_service.RosterUnavailableError) as raised:
        club_members_service.sync_from_fftri(db_session, user_id=admin.id)
    assert raised.value.status_code == 502


def test_import_file_replaces_a_past_season(db_session, admin):
    martin = _athlete(db_session, "MARTIN", "Anne")
    content = "Nom;Prénom;Sexe\nMARTIN;Anne;F\nDURAND;Paul;H\n".replace(";", ",").encode()

    report = club_members_service.import_file(
        db_session, season=2024, content=content, filename="licencies.csv", user_id=admin.id
    )

    assert (report.season, report.total, report.linked, report.unlinked) == (2024, 2, 1, 1)
    rows = club_member_repository.list_season(db_session, 2024)
    assert {(m.nom, m.gender, m.source) for m in rows} == {("MARTIN", "F", SOURCE_FILE), ("DURAND", "M", SOURCE_FILE)}
    assert next(m for m in rows if m.nom == "MARTIN").athlete_id == martin.id


def test_import_file_reads_an_optional_licence_column_and_drops_duplicates(db_session, admin):
    content = b"NOM,PRENOM,Licence\nMARTIN,Anne,C1\nMARTIN,Anne,C1\n,,\n"

    report = club_members_service.import_file(
        db_session, season=2024, content=content, filename="l.csv", user_id=admin.id
    )

    assert report.total == 1
    assert club_member_repository.list_season(db_session, 2024)[0].licence_id == "C1"


def test_import_file_without_name_columns_is_refused(db_session, admin):
    with pytest.raises(club_members_service.MissingMemberColumnsError):
        club_members_service.import_file(
            db_session, season=2024, content=b"a,b\n1,2\n", filename="l.csv", user_id=admin.id
        )


def test_import_file_refuses_a_season_out_of_range(db_session, admin):
    with pytest.raises(DomainError):
        club_members_service.import_file(
            db_session, season=1990, content=b"Nom,Prenom\nA,B\n", filename="l.csv", user_id=admin.id
        )


def test_link_member_refuses_an_unknown_member_or_athlete(db_session, admin):
    with pytest.raises(NotFoundError):
        club_members_service.link_member(db_session, member_id=999, athlete_id=1, user_id=admin.id)


def test_link_member_recomputes_the_linked_athlete(db_session, admin, roster):
    _athlete(db_session, "MARTIN", "Anne")
    other = _athlete(db_session, "MARTIN", "Anne", homonym_rank=1)
    course = course_repository.get_or_create(
        db_session, name="Tri", event_date=date(2026, 10, 4), event_type="triathlon-m"
    )
    result = participation_repository.create(
        db_session, athlete_id=other.id, course_id=course.id, bib_number="1", status="finisher"
    )
    club_members_service.sync_from_fftri(db_session, user_id=admin.id)
    member = next(m for m in club_member_repository.list_season(db_session, 2026) if m.licence_id == "C1")
    assert member.link_status == LINK_AMBIGUOUS

    club_members_service.link_member(db_session, member_id=member.id, athlete_id=other.id, user_id=admin.id)

    db_session.refresh(result)
    assert result.counts_for_tcn
    assert (member.athlete_id, member.link_status) == (other.id, LINK_MANUAL)


def test_a_manual_link_survives_a_file_import(db_session, admin):
    chosen = _athlete(db_session, "DURAND", "Paul")
    _athlete(db_session, "DURAND", "Paul", homonym_rank=1)
    content = b"Nom,Prenom\nDURAND,Paul\n"
    club_members_service.import_file(db_session, season=2024, content=content, filename="l.csv", user_id=admin.id)
    member = club_member_repository.list_season(db_session, 2024)[0]
    club_members_service.link_member(db_session, member_id=member.id, athlete_id=chosen.id, user_id=admin.id)

    club_members_service.import_file(db_session, season=2024, content=content, filename="l.csv", user_id=admin.id)

    again = club_member_repository.list_season(db_session, 2024)[0]
    assert (again.athlete_id, again.link_status) == (chosen.id, LINK_MANUAL)


def test_sync_tolerates_a_duplicated_licence_in_the_roster(db_session, admin, monkeypatch):
    members = [RosterMember("MARTIN", "Anne", "F", "C1"), RosterMember("MARTIN", "Anne", "F", "C1")]
    monkeypatch.setattr(
        club_members_service.fftri_club_members, "fetch_club_roster",
        lambda url: ClubRoster(licence_year=2027, members=members),
    )

    report = club_members_service.sync_from_fftri(db_session, user_id=admin.id)

    assert report.total == 1


def test_licence_less_rows_of_one_athlete_collapse_to_one(db_session, admin):
    martin = _athlete(db_session, "MARTIN", "Anne")
    athlete_alias_repository.add(db_session, ("martn", "anne"), martin.id)
    content = b"Nom,Prenom\nMARTIN,Anne\nMARTN,Anne\n"

    report = club_members_service.import_file(
        db_session, season=2024, content=content, filename="l.csv", user_id=admin.id
    )

    assert (report.total, report.linked) == (1, 1)


def test_import_file_normalizes_the_gender(db_session, admin):
    content = b"Nom,Prenom,Sexe\nA,B,Homme\nC,D,Femme\nE,F,?\n"

    club_members_service.import_file(db_session, season=2024, content=content, filename="l.csv", user_id=admin.id)

    genders = {m.nom: m.gender for m in club_member_repository.list_season(db_session, 2024)}
    assert genders == {"A": "M", "C": "F", "E": ""}


def _oppose(db, admin, nom, prenom):
    opposition_repository.create(
        db, identity_hash=identity_hash(nom, prenom), requested_on=date(2026, 9, 1), applied_by_user_id=admin.id
    )


def test_sync_skips_an_identity_in_the_opposition_register(db_session, admin, roster):
    _oppose(db_session, admin, "Durand", "PAUL")

    report = club_members_service.sync_from_fftri(db_session, user_id=admin.id)

    assert report.total == 2
    assert "C2" not in {m.licence_id for m in club_member_repository.list_season(db_session, 2026)}


def test_import_file_skips_an_identity_in_the_opposition_register(db_session, admin):
    _oppose(db_session, admin, "MARTIN", "Anne")
    content = b"Nom,Prenom\nMARTIN,Anne\nDURAND,Paul\n"

    club_members_service.import_file(db_session, season=2024, content=content, filename="l.csv", user_id=admin.id)

    assert [m.nom for m in club_member_repository.list_season(db_session, 2024)] == ["DURAND"]
