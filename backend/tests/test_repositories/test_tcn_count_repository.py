"""Stored TCN counting rule (#1206): `Participation.counts_for_tcn`."""
from datetime import date

import pytest
from sqlalchemy import String, literal, or_, select
from sqlalchemy.orm import aliased

from app.core import counter_scope
from app.core.club import ClubLabels, counts_by_label, tcn_clause
from app.models.club_member import (
    LINK_AMBIGUOUS,
    LINK_AUTO,
    LINK_MANUAL,
    LINK_UNLINKED,
    SOURCE_FFTRI,
    ClubMember,
)
from app.models.course import Course
from app.models.participation import Participation, ParticipationTeammate
from app.repositories import (
    athlete_repository,
    course_repository,
    participation_repository,
    tcn_count_repository,
)


def _course(db, name="Tri de test", day=18):
    return course_repository.get_or_create(
        db, name=name, event_date=date(2026, 5, day), event_type="triathlon-m"
    )


def _result(db, athlete, course, bib, club, *, pending=False):
    return participation_repository.create(
        db,
        athlete_id=athlete.id,
        course_id=course.id,
        bib_number=bib,
        club=club,
        is_pending_validation=pending,
    )


def _ambiguous_tcn():
    counter_scope.load(
        disciplines=counter_scope.non_federal_disciplines(),
        club_labels=counter_scope.tcn_club_labels(),
        ambiguous_club_labels={"tcn"},
    )


def test_a_new_row_takes_its_label_verdict(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    course = _course(db_session)

    nantes = _result(db_session, athlete, course, "1", "Triathlon Club Nantais")
    autre = _result(db_session, athlete, _course(db_session, "Autre"), "2", "ASPTT")

    assert nantes.counts_for_tcn is True
    assert autre.counts_for_tcn is False


def test_a_new_row_with_an_ambiguous_label_does_not_count_yet(db_session):
    _ambiguous_tcn()
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")

    row = _result(db_session, athlete, _course(db_session), "1", "TCN")

    assert row.counts_for_tcn is False


def test_changing_the_club_recomputes_the_label_verdict(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    row = _result(db_session, athlete, _course(db_session), "1", "ASPTT")

    participation_repository.update(db_session, row, club="Tri Club Nantais")

    assert row.counts_for_tcn is True


@pytest.mark.parametrize(
    "label",
    [
        "Triathlon Club Nantais",
        "  TRIATHLON   club nantais ",
        "Tri\tClub\xa0Nantais",
        "TCN",
        " tcn ",
        "ASPTT",
        "",
        None,
    ],
)
def test_listener_verdict_matches_the_sql_label_condition(db_session, label):
    """Le verdict provisoire de l'écouteur est la condition 1 de la règle.

    Le constructeur SQL de la règle n'arrive qu'avec le recalcul : on compare
    donc à `tcn_clause` sur les libellés non ambigus de la portée.
    """
    _ambiguous_tcn()
    clear = counter_scope.tcn_club_labels() - counter_scope.ambiguous_club_labels()
    sql_verdict = db_session.execute(select(tcn_clause(literal(label, String), clear))).scalar()

    assert counts_by_label(label) is bool(sql_verdict)


_LABELS = ClubLabels(clear=frozenset({"triathlon club nantais"}), ambiguous=frozenset({"tcn"}))


def _flags(db, *rows):
    db.expire_all()
    return [row.counts_for_tcn for row in rows]


def test_an_ambiguous_label_alone_does_not_count(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    row = _result(db_session, athlete, _course(db_session), "1", "TCN")

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    assert _flags(db_session, row) == [False]


def test_an_ambiguous_label_counts_when_the_athlete_has_a_clear_result(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    bare = _result(db_session, athlete, _course(db_session, "A"), "1", "TCN")
    clear = _result(db_session, athlete, _course(db_session, "B"), "1", "Triathlon Club Nantais")

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    assert _flags(db_session, bare, clear) == [True, True]


def test_a_pending_clear_result_does_not_confirm_the_club(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    bare = _result(db_session, athlete, _course(db_session, "A"), "1", "TCN")
    _result(db_session, athlete, _course(db_session, "B"), "1", "Triathlon Club Nantais", pending=True)

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    assert _flags(db_session, bare) == [False]


def test_two_ambiguous_results_do_not_confirm_each_other(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    first = _result(db_session, athlete, _course(db_session, "A"), "1", "TCN")
    second = _result(db_session, athlete, _course(db_session, "B"), "1", "TCN")

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    assert _flags(db_session, first, second) == [False, False]


def test_a_label_outside_the_scope_never_counts(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    _result(db_session, athlete, _course(db_session, "A"), "1", "Triathlon Club Nantais")
    other = _result(db_session, athlete, _course(db_session, "B"), "1", "ASPTT")

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    assert _flags(db_session, other) == [False]


def test_the_course_counter_counts_validated_flagged_rows(db_session):
    course = _course(db_session)
    for bib, (nom, club, pending) in enumerate(
        [("A", "Triathlon Club Nantais", False), ("B", "TCN", False), ("C", "Triathlon Club Nantais", True)]
    ):
        athlete = athlete_repository.get_or_create(db_session, nom=nom, prenom="X")
        _result(db_session, athlete, course, str(bib), club, pending=pending)

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    db_session.expire_all()
    assert course.tcn_count == 1


def test_a_course_scope_reaches_the_other_results_of_its_athletes(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    old_course = _course(db_session, "Ancienne", day=1)
    bare = _result(db_session, athlete, old_course, "1", "TCN")
    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)
    new_course = _course(db_session, "Nouvelle", day=20)
    _result(db_session, athlete, new_course, "1", "Triathlon Club Nantais")

    tcn_count_repository.recompute_counts_for_tcn(
        db_session, course_ids=[new_course.id], labels=_LABELS
    )

    assert _flags(db_session, bare) == [True]
    assert old_course.tcn_count == 1


def test_an_athlete_scope_leaves_other_athletes_alone(db_session):
    anne = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    paul = athlete_repository.get_or_create(db_session, nom="DURAND", prenom="Paul")
    course = _course(db_session)
    _result(db_session, anne, course, "1", "Triathlon Club Nantais")
    stale = _result(db_session, paul, course, "2", "ASPTT")
    db_session.query(type(stale)).filter_by(id=stale.id).update({"counts_for_tcn": True})

    tcn_count_repository.recompute_counts_for_tcn(db_session, athlete_ids=[anne.id], labels=_LABELS)

    assert _flags(db_session, stale) == [True]


def test_a_course_whose_rows_were_deleted_is_recounted(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    course = _course(db_session)
    row = _result(db_session, athlete, course, "1", "Triathlon Club Nantais")
    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)
    participation_repository.delete(db_session, row)
    db_session.flush()

    tcn_count_repository.recompute_counts_for_tcn(
        db_session, course_ids=[course.id], athlete_ids=[athlete.id], labels=_LABELS
    )

    db_session.expire_all()
    assert course.tcn_count == 0


def test_without_labels_the_registry_decides(db_session):
    _ambiguous_tcn()
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    bare = _result(db_session, athlete, _course(db_session, "A"), "1", "TCN")
    _result(db_session, athlete, _course(db_session, "B"), "1", "Tri Club Nantais")

    tcn_count_repository.recompute_counts_for_tcn(db_session)

    assert _flags(db_session, bare) == [True]


def test_loaded_instances_see_the_new_verdict_without_a_refresh(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    course = _course(db_session)
    bare = _result(db_session, athlete, course, "1", "TCN")
    tcn_count_repository.recompute_counts_for_tcn(db_session)
    assert (bare.counts_for_tcn, course.tcn_count) == (True, 1)

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    assert bare.counts_for_tcn is False
    assert course.tcn_count == 0


def _dated_course(db, event_date=date(2026, 10, 10), name="Tri saison", is_relay=False):
    return course_repository.get_or_create(
        db, name=name, event_date=event_date, event_type="triathlon-m", is_relay=is_relay
    )


def _licence(db, athlete, season, link_status=LINK_AUTO):
    db.add(ClubMember(
        season=season, nom=athlete.nom, prenom=athlete.prenom,
        licence_id=f"C{athlete.id}-{season}", athlete_id=athlete.id,
        link_status=link_status, source=SOURCE_FFTRI,
    ))
    db.flush()


def _relay(db, team, teammate, bib="7"):
    course = _dated_course(db, is_relay=True)
    return participation_repository.create_batch(db, [{
        "athlete_id": team.id, "course_id": course.id, "bib_number": bib,
        "club": "ASPTT", "teammate_ids": [teammate.id],
    }])[0]


def test_a_member_of_the_course_season_counts_without_club_label(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    row = _result(db_session, athlete, _dated_course(db_session), "1", "ASPTT")
    _licence(db_session, athlete, season=2026)

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    assert _flags(db_session, row) == [True]


def test_a_licence_of_another_season_does_not_count(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    # Le 31 août 2026 appartient à la saison 2025 : la licence 2026 ne la couvre pas.
    row = _result(db_session, athlete, _dated_course(db_session, date(2026, 8, 31)), "1", None)
    _licence(db_session, athlete, season=2026)

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    assert _flags(db_session, row) == [False]


def test_a_course_without_date_is_covered_by_no_licence(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    row = _result(db_session, athlete, _dated_course(db_session, None), "1", None)
    _licence(db_session, athlete, season=2026)

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    assert _flags(db_session, row) == [False]


@pytest.mark.parametrize("link_status", [LINK_UNLINKED, LINK_AMBIGUOUS])
def test_an_unlinked_member_row_does_not_count(db_session, link_status):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    row = _result(db_session, athlete, _dated_course(db_session), "1", None)
    _licence(db_session, athlete, season=2026, link_status=link_status)

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    assert _flags(db_session, row) == [False]


def test_a_manual_link_counts(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    row = _result(db_session, athlete, _dated_course(db_session), "1", None)
    _licence(db_session, athlete, season=2026, link_status=LINK_MANUAL)

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    assert _flags(db_session, row) == [True]


def test_a_relay_counts_when_a_teammate_is_a_member(db_session):
    team = athlete_repository.get_or_create(db_session, nom="EQUIPE", prenom="Bleue")
    teammate = athlete_repository.get_or_create(db_session, nom="DURAND", prenom="Paul")
    row = _relay(db_session, team, teammate)
    _licence(db_session, teammate, season=2026)

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    assert _flags(db_session, row) == [True]


def test_a_relay_teammate_licensed_another_season_does_not_count(db_session):
    team = athlete_repository.get_or_create(db_session, nom="EQUIPE", prenom="Bleue")
    teammate = athlete_repository.get_or_create(db_session, nom="DURAND", prenom="Paul")
    row = _relay(db_session, team, teammate)
    _licence(db_session, teammate, season=2025)

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    assert _flags(db_session, row) == [False]


def test_a_member_on_another_relay_does_not_count_for_this_one(db_session):
    member = athlete_repository.get_or_create(db_session, nom="DURAND", prenom="Paul")
    stranger = athlete_repository.get_or_create(db_session, nom="PETIT", prenom="Luc")
    _relay(db_session, athlete_repository.get_or_create(db_session, nom="EQUIPE", prenom="Bleue"), member)
    other = _relay(db_session, athlete_repository.get_or_create(db_session, nom="EQUIPE", prenom="Rouge"), stranger, bib="8")
    _licence(db_session, member, season=2026)

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    assert _flags(db_session, other) == [False]


def test_an_athlete_scope_reaches_the_relays_of_a_teammate(db_session):
    team = athlete_repository.get_or_create(db_session, nom="EQUIPE", prenom="Bleue")
    teammate = athlete_repository.get_or_create(db_session, nom="DURAND", prenom="Paul")
    row = _relay(db_session, team, teammate)
    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)
    _licence(db_session, teammate, season=2026)

    tcn_count_repository.recompute_counts_for_tcn(
        db_session, athlete_ids=[teammate.id], labels=_LABELS
    )

    assert _flags(db_session, row) == [True]


def test_an_ambiguous_label_counts_for_a_licensed_athlete_of_any_season(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    row = _result(db_session, athlete, _dated_course(db_session), "1", "TCN")
    _licence(db_session, athlete, season=2019)

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    assert _flags(db_session, row) == [True]


def test_an_unlinked_licence_does_not_confirm_an_ambiguous_label(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    row = _result(db_session, athlete, _dated_course(db_session), "1", "TCN")
    _licence(db_session, athlete, season=2019, link_status=LINK_UNLINKED)

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    assert _flags(db_session, row) == [False]


def test_the_course_counter_follows_membership(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    course = _dated_course(db_session)
    _result(db_session, athlete, course, "1", None)
    _licence(db_session, athlete, season=2026)

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    db_session.expire_all()
    assert course.tcn_count == 1


def _scope_before_1580(course_ids, athlete_ids):
    """The `OR` scope #1580 replaced, kept as the oracle of the rows it reaches."""
    conditions = []
    if course_ids:
        on_courses = aliased(Participation)
        conditions += [
            Participation.course_id.in_(course_ids),
            Participation.athlete_id.in_(
                select(on_courses.athlete_id).where(on_courses.course_id.in_(course_ids))
            ),
        ]
    if athlete_ids:
        conditions += [
            Participation.athlete_id.in_(athlete_ids),
            Participation.id.in_(
                select(ParticipationTeammate.participation_id).where(
                    ParticipationTeammate.athlete_id.in_(athlete_ids)
                )
            ),
        ]
    return or_(*conditions)


@pytest.mark.parametrize(
    ("courses", "athletes"),
    [
        (["home"], None),
        (["relay"], None),
        (["home", "elsewhere"], None),
        (["empty"], None),
        (None, ["anne"]),
        (None, ["teammate"]),
        (None, ["anne", "teammate", "loner"]),
        (["home"], ["teammate"]),
        (["relay"], ["loner"]),
    ],
)
def test_the_scope_reaches_the_same_rows_as_before_1580(db_session, courses, athletes):
    people = {
        name: athlete_repository.get_or_create(db_session, nom=name.upper(), prenom="Test")
        for name in ("anne", "bob", "teammate", "loner", "carrier")
    }
    races = {
        "home": _dated_course(db_session, name="Home"),
        "elsewhere": _dated_course(db_session, name="Elsewhere", event_date=date(2026, 6, 1)),
        "far": _dated_course(db_session, name="Far", event_date=date(2025, 6, 1)),
        "empty": _dated_course(db_session, name="Empty", event_date=date(2026, 7, 1)),
    }
    for bib, (who, where) in enumerate([
        ("anne", "home"), ("bob", "home"), ("anne", "far"), ("bob", "elsewhere"),
        ("loner", "far"), ("teammate", "elsewhere"), ("carrier", "far"),
    ]):
        _result(db_session, people[who], races[where], str(bib), "ASPTT")
    relay = _relay(db_session, people["carrier"], people["teammate"])
    races["relay"] = db_session.get(Course, relay.course_id)

    course_ids = [races[name].id for name in courses] if courses else None
    athlete_ids = [people[name].id for name in athletes] if athletes else None

    def reached(scope):
        return set(db_session.scalars(select(Participation.id).where(scope)))

    expected = reached(_scope_before_1580(course_ids, athlete_ids))
    assert reached(tcn_count_repository._scope(course_ids, athlete_ids)) == expected
    assert expected or courses == ["empty"]


def test_the_scope_is_one_indexable_in_clause_on_postgresql():
    """#1580: `course_id IN (...) OR athlete_id IN (SELECT ...)` full-scans
    participations on PostgreSQL, as `carried_by` did before #1391."""
    from sqlalchemy.dialects import postgresql

    scope = tcn_count_repository._scope([1], [2])
    sql = str(scope.compile(dialect=postgresql.dialect())).upper()

    assert " OR " not in sql, sql
    assert sql.count("UNION ALL") == 3, sql
