"""Licenciés du club par saison (#1202)."""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.athlete import Athlete
from app.models.club_member import LINK_AUTO, LINK_UNLINKED, SOURCE_FFTRI, ClubMember
from app.repositories import club_member_repository


def _member(season=2026, nom="MARTIN", prenom="Anne", licence_id="C1", **fields) -> ClubMember:
    return ClubMember(
        season=season, nom=nom, prenom=prenom, licence_id=licence_id,
        gender=fields.pop("gender", "F"), link_status=fields.pop("link_status", LINK_UNLINKED),
        source=fields.pop("source", SOURCE_FFTRI), **fields,
    )


def test_identity_keys_are_stored_on_insert(db_session):
    club_member_repository.replace_season(db_session, 2026, [_member(nom="LE GOFF", prenom="Loan")])

    (row,) = club_member_repository.list_season(db_session, 2026)
    assert (row.last_name_key, row.first_name_key) == ("legoff", "loan")


def test_replace_season_leaves_other_seasons_alone(db_session):
    club_member_repository.replace_season(db_session, 2025, [_member(season=2025)])
    club_member_repository.replace_season(db_session, 2026, [_member(licence_id="C2")])

    club_member_repository.replace_season(db_session, 2026, [_member(nom="DURAND", licence_id="C3")])

    assert [m.licence_id for m in club_member_repository.list_season(db_session, 2025)] == ["C1"]
    assert [m.licence_id for m in club_member_repository.list_season(db_session, 2026)] == ["C3"]
    assert club_member_repository.seasons(db_session) == [2026, 2025]


def test_a_licence_appears_once_per_season(db_session):
    db_session.add_all([_member(), _member(nom="AUTRE")])
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_without_licence_a_name_appears_once_per_season(db_session):
    db_session.add_all([_member(licence_id=None), _member(licence_id=None)])
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_two_homonyms_with_distinct_licences_coexist(db_session):
    db_session.add_all([_member(licence_id="C1"), _member(licence_id="C2")])
    db_session.flush()


def test_purge_deletes_unlinked_rows_and_strips_linked_ones(db_session):
    athlete = Athlete(nom="MARTIN", prenom="Anne")
    db_session.add(athlete)
    db_session.flush()
    club_member_repository.replace_season(db_session, 2024, [
        _member(season=2024, licence_id="C1", athlete_id=athlete.id, link_status=LINK_AUTO,
                nom="MARTIN", prenom="Anne"),
        _member(season=2024, licence_id="C2", nom="INCONNU", prenom="Paul"),
    ])
    club_member_repository.replace_season(db_session, 2025, [_member(season=2025, licence_id="C9")])

    assert club_member_repository.purge_before(db_session, 2025, dry_run=True) == 2
    assert len(club_member_repository.list_season(db_session, 2024)) == 2

    assert club_member_repository.purge_before(db_session, 2025, dry_run=False) == 2
    (kept,) = club_member_repository.list_season(db_session, 2024)
    assert (kept.athlete_id, kept.licence_id) == (athlete.id, None)
    assert [m.licence_id for m in club_member_repository.list_season(db_session, 2025)] == ["C9"]


def test_repoint_moves_every_link_to_the_target(db_session):
    source = Athlete(nom="MARTIN", prenom="Anne")
    target = Athlete(nom="MARTIN", prenom="Anne", homonym_rank=1)
    db_session.add_all([source, target])
    db_session.flush()
    club_member_repository.replace_season(db_session, 2025, [
        _member(season=2025, licence_id="C1", athlete_id=source.id, link_status=LINK_AUTO),
    ])
    club_member_repository.replace_season(db_session, 2026, [
        _member(licence_id="C2", athlete_id=source.id, link_status=LINK_AUTO),
        _member(nom="AUTRE", licence_id="C3", athlete_id=target.id, link_status=LINK_AUTO),
        _member(nom="DURAND", licence_id="C4"),
    ])

    club_member_repository.repoint(db_session, from_athlete_id=source.id, to_athlete_id=target.id)

    rows = {
        m.licence_id: m.athlete_id
        for season in (2025, 2026)
        for m in club_member_repository.list_season(db_session, season)
    }
    assert rows == {"C1": target.id, "C2": target.id, "C3": target.id, "C4": None}


def test_purge_keeps_two_linked_homonyms_of_an_old_season(db_session):
    first = Athlete(nom="MARTIN", prenom="Anne")
    second = Athlete(nom="MARTIN", prenom="Anne", homonym_rank=1)
    db_session.add_all([first, second])
    db_session.flush()
    club_member_repository.replace_season(db_session, 2024, [
        _member(season=2024, licence_id="C1", athlete_id=first.id, link_status=LINK_AUTO),
        _member(season=2024, licence_id="C2", athlete_id=second.id, link_status=LINK_AUTO),
    ])

    club_member_repository.purge_before(db_session, 2025, dry_run=False)

    rows = club_member_repository.list_season(db_session, 2024)
    assert sorted(m.athlete_id for m in rows) == sorted([first.id, second.id])
    assert {m.licence_id for m in rows} == {None}


def test_purge_keeps_one_row_per_athlete_and_season(db_session):
    athlete = Athlete(nom="MARTIN", prenom="Anne")
    db_session.add(athlete)
    db_session.flush()
    club_member_repository.replace_season(db_session, 2024, [
        _member(season=2024, licence_id="C1", athlete_id=athlete.id, link_status=LINK_AUTO),
        _member(season=2024, licence_id="C2", athlete_id=athlete.id, link_status=LINK_AUTO),
    ])

    assert club_member_repository.purge_before(db_session, 2025, dry_run=True) == 2
    assert club_member_repository.purge_before(db_session, 2025, dry_run=False) == 2

    assert len(club_member_repository.list_season(db_session, 2024)) == 1
    assert club_member_repository.purge_before(db_session, 2025, dry_run=False) == 0


def test_purge_deletes_linked_rows_whose_athlete_is_gone(db_session):
    club_member_repository.replace_season(db_session, 2024, [
        _member(season=2024, licence_id="C1", athlete_id=None, link_status=LINK_AUTO),
    ])

    assert club_member_repository.purge_before(db_session, 2025, dry_run=False) == 1

    assert club_member_repository.list_season(db_session, 2024) == []
    assert club_member_repository.purge_before(db_session, 2025, dry_run=False) == 0


def test_two_unlinked_rows_without_licence_still_collide(db_session):
    db_session.add_all([
        _member(licence_id=None, link_status=LINK_UNLINKED),
        _member(licence_id=None, link_status=LINK_UNLINKED),
    ])
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_purge_keeps_only_the_link_and_the_athlete_identity(db_session):
    athlete = Athlete(nom="MARTIN", prenom="Anne")
    db_session.add(athlete)
    db_session.flush()
    club_member_repository.replace_season(db_session, 2024, [
        _member(season=2024, licence_id="C1", athlete_id=athlete.id, link_status=LINK_AUTO,
                nom="MARTIN DUPONT", prenom="Anne Sophie", gender="F"),
    ])

    club_member_repository.purge_before(db_session, 2025, dry_run=False)

    (kept,) = club_member_repository.list_season(db_session, 2024)
    assert (kept.nom, kept.prenom, kept.gender) == ("MARTIN", "Anne", "")
    assert (kept.last_name_key, kept.first_name_key) == (athlete.last_name_key, athlete.first_name_key)
    assert kept.licence_id is None
