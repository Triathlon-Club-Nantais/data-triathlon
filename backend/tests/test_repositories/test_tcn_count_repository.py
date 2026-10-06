"""Stored TCN counting rule (#1206): `Participation.counts_for_tcn`."""
from datetime import date

import pytest
from sqlalchemy import String, literal, select

from app.core import counter_scope
from app.core.club import ClubLabels, counts_by_label, tcn_clause
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


def test_a_bare_ambiguous_result_next_to_a_pending_ambiguous_one_does_not_count(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    bare = _result(db_session, athlete, _course(db_session, "A"), "1", "TCN")
    _result(db_session, athlete, _course(db_session, "B"), "1", "TCN", pending=True)

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
    bare = _result(db_session, athlete, _course(db_session, "A"), "1", "TCN")
    _result(db_session, athlete, _course(db_session, "B"), "1", "Triathlon Club Nantais")

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    assert bare.counts_for_tcn is True
