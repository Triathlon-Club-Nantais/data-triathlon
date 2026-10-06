"""Stored TCN counting rule (#1206): `Participation.counts_for_tcn`."""
from datetime import date

import pytest
from sqlalchemy import String, literal, select

from app.core import counter_scope
from app.core.club import counts_by_label, tcn_clause
from app.repositories import athlete_repository, course_repository, participation_repository


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
