"""Licenciés du club par saison (#1202)."""
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.core import sql_observability
from app.models.athlete import Athlete
from app.models.club_member import (
    LINK_AMBIGUOUS,
    LINK_AUTO,
    LINK_MANUAL,
    LINK_UNLINKED,
    SOURCE_FFTRI,
    SOURCE_FILE,
    ClubMember,
)
from app.repositories import (
    athlete_repository,
    club_member_repository,
    course_repository,
    participation_repository,
    tcn_count_repository,
)


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


def test_purge_minimises_licence_less_file_rows_once(db_session):
    athlete = Athlete(nom="MARTIN", prenom="Anne")
    db_session.add(athlete)
    db_session.flush()
    club_member_repository.replace_season(db_session, 2024, [
        _member(season=2024, licence_id=None, athlete_id=athlete.id, link_status=LINK_AUTO,
                nom="MARTIN DUPONT", prenom="Anne Sophie", gender="F", source=SOURCE_FILE),
    ])

    assert club_member_repository.purge_before(db_session, 2025, dry_run=False) == 1

    (kept,) = club_member_repository.list_season(db_session, 2024)
    assert (kept.nom, kept.prenom, kept.gender) == ("MARTIN", "Anne", "")
    assert (kept.last_name_key, kept.first_name_key) == (athlete.last_name_key, athlete.first_name_key)
    assert club_member_repository.purge_before(db_session, 2025, dry_run=False) == 0


# --- Licensees who raced (#1441) ---------------------------------------------

_TCN = "Triathlon Club Nantais"


def _athlete(db, nom):
    return athlete_repository.get_or_create(db, nom=nom, prenom="Anne")


def _licensee(db, athlete, *, season=2026, link_status=LINK_AUTO):
    db.add(_member(
        season=season, nom=athlete.nom, licence_id=f"L{athlete.id}-{season}",
        athlete_id=athlete.id, link_status=link_status,
    ))
    db.flush()


def _raced(db, athlete, *, day=date(2026, 10, 10), club=_TCN, **fields):
    course = course_repository.get_or_create(db, name=f"Tri {day}", event_date=day, event_type="triathlon-m")
    return participation_repository.create(
        db, athlete_id=athlete.id, course_id=course.id, bib_number=str(athlete.id), club=club, **fields
    )


def test_licensee_activity_is_none_without_licensee(db_session):
    _licensee(db_session, _athlete(db_session, "AUTRE"), season=2025)

    assert club_member_repository.licensee_activity(db_session, 2026) is None


def test_licensee_activity_counts_linked_licensees_with_a_season_result(db_session):
    raced = _athlete(db_session, "COUREUSE")
    _licensee(db_session, raced)
    _raced(db_session, raced)
    _raced(db_session, raced, day=date(2027, 3, 1))
    manual = _athlete(db_session, "MANUELLE")
    _licensee(db_session, manual, link_status=LINK_MANUAL)
    _raced(db_session, manual)
    _licensee(db_session, _athlete(db_session, "ABSENTE"))

    assert club_member_repository.licensee_activity(db_session, 2026) == (3, 2)


@pytest.mark.parametrize("link_status", [LINK_UNLINKED, LINK_AMBIGUOUS])
def test_licensee_activity_ignores_an_unlinked_row(db_session, link_status):
    athlete = _athlete(db_session, "NONRATTACHEE")
    _licensee(db_session, athlete, link_status=link_status)
    _raced(db_session, athlete)

    assert club_member_repository.licensee_activity(db_session, 2026) == (1, 0)


def test_licensee_activity_ignores_a_result_of_another_season(db_session):
    athlete = _athlete(db_session, "ANCIENNE")
    _licensee(db_session, athlete)
    # Le 31 août 2026 appartient encore à la saison 2025.
    _raced(db_session, athlete, day=date(2026, 8, 31))

    assert club_member_repository.licensee_activity(db_session, 2026) == (1, 0)


@pytest.mark.parametrize("is_rejected", [False, True])
def test_licensee_activity_ignores_a_pending_or_rejected_result(db_session, is_rejected):
    athlete = _athlete(db_session, "DECLAREE")
    _licensee(db_session, athlete)
    _raced(db_session, athlete, is_pending_validation=True, is_rejected=is_rejected)

    assert club_member_repository.licensee_activity(db_session, 2026) == (1, 0)


def test_licensee_activity_ignores_a_result_that_does_not_count_for_the_club(db_session):
    athlete = _athlete(db_session, "AILLEURS")
    _licensee(db_session, athlete)
    _raced(db_session, athlete, club="ASPTT")

    assert club_member_repository.licensee_activity(db_session, 2026) == (1, 0)


def test_licensee_activity_counts_a_relay_teammate(db_session):
    teammate = _athlete(db_session, "EQUIPIERE")
    _licensee(db_session, teammate)
    team = _athlete(db_session, "EQUIPE")
    course = course_repository.get_or_create(
        db_session, name="Relais", event_date=date(2026, 10, 10), event_type="triathlon-m", is_relay=True
    )
    participation_repository.create_batch(db_session, [{
        "athlete_id": team.id, "course_id": course.id, "bib_number": "7",
        "club": "ASPTT", "teammate_ids": [teammate.id],
    }])
    _licensee(db_session, _athlete(db_session, "ABSENTE"))
    tcn_count_repository.recompute_counts_for_tcn(db_session)

    # Le relais ne compte que pour son équipière, pas pour toute la liste.
    assert club_member_repository.licensee_activity(db_session, 2026) == (2, 1)


def test_licensee_activity_is_one_query(db_session):
    for nom in ("UN", "DEUX", "TROIS"):
        athlete = _athlete(db_session, nom)
        _licensee(db_session, athlete)
        _raced(db_session, athlete)
    sql_observability.install(db_session.bind, slow_query_ms=0, collect_stats=True)
    try:
        with sql_observability.measure_queries("test licensee_activity") as stats:
            assert club_member_repository.licensee_activity(db_session, 2026) == (3, 3)
        assert stats.count == 1
    finally:
        sql_observability.reset_for_tests()


def test_licensee_activity_reads_each_licensee_through_the_athlete_indexes(db_session):
    """#1473: an `OR` between carrier and teammate made PostgreSQL scan every club
    result once per licensee; each branch must be correlated to the licensee."""
    from sqlalchemy import event

    statements = []
    engine = db_session.get_bind()

    def capture(conn, cursor, statement, *args):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        club_member_repository.licensee_activity(db_session, 2026)
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    (sql,) = [s for s in statements if "participation_teammates" in s]
    assert " OR " not in sql, sql
    assert "participations_1.athlete_id = club_members.athlete_id" in sql, sql
    assert "participation_teammates.athlete_id = club_members.athlete_id" in sql, sql
    assert "participation_teammates, club_members" not in sql, sql
    assert "participations_1, club_members" not in sql, sql


def test_licensee_activity_counts_a_relay_carrier_and_teammate(db_session):
    carrier = _athlete(db_session, "PORTEUSE")
    _licensee(db_session, carrier)
    teammate = _athlete(db_session, "EQUIPIERE")
    _licensee(db_session, teammate)
    course = course_repository.get_or_create(
        db_session, name="Relais", event_date=date(2026, 10, 10), event_type="triathlon-m", is_relay=True
    )
    participation_repository.create_batch(db_session, [{
        "athlete_id": carrier.id, "course_id": course.id, "bib_number": "7",
        "club": _TCN, "teammate_ids": [carrier.id, teammate.id],
    }])
    _licensee(db_session, _athlete(db_session, "ABSENTE"))
    tcn_count_repository.recompute_counts_for_tcn(db_session)

    assert club_member_repository.licensee_activity(db_session, 2026) == (3, 2)
