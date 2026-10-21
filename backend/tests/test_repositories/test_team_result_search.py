"""Relay results a claimed member can find by team name (#1739)."""
from datetime import date
from itertools import count

import pytest

from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation, ParticipationTeammate
from app.repositories import participation_repository

_NUMBER = count(1)


def _athlete(db, nom, prenom="") -> Athlete:
    athlete = Athlete(nom=nom, prenom=prenom)
    db.add(athlete)
    db.flush()
    return athlete


def _relay(db, carrier, *, event_date=date(2026, 6, 7), course_relay=True, teammates=(), **extra) -> Participation:
    number = next(_NUMBER)
    course = Course(name=f"Relais {number}", event_date=event_date, event_type="triathlon-s", is_relay=course_relay)
    db.add(course)
    db.flush()
    extra.setdefault("is_relay", True)
    row = Participation(course_id=course.id, athlete_id=carrier.id, bib_number=str(number), status="finisher", **extra)
    db.add(row)
    db.flush()
    for position, teammate in enumerate(teammates):
        db.add(ParticipationTeammate(participation_id=row.id, athlete_id=teammate.id, position=position))
    db.flush()
    return row


@pytest.fixture
def member(db_session):
    return _athlete(db_session, "MARTIN", "Léa")


def _search(db, member, term, **extra):
    return [row.id for row in participation_repository.search_team_results(
        db, term=term, exclude_athlete_id=member.id, **extra
    )]


def test_finds_a_team_record_by_its_name_ignoring_case_and_accents(db_session, member):
    row = _relay(db_session, _athlete(db_session, "Les Mollets d'Écume"))

    assert _search(db_session, member, "mollets d'ecume") == [row.id]


def test_words_match_apart_so_a_missing_apostrophe_still_finds(db_session, member):
    row = _relay(db_session, _athlete(db_session, "LES MOLLETS D'ACIER"))

    assert _search(db_session, member, "mollets d acier") == [row.id]


def test_finds_a_composed_relay_by_team_name(db_session, member):
    jean, paul = _athlete(db_session, "DUPONT", "Jean"), _athlete(db_session, "DURAND", "Paul")
    row = _relay(db_session, jean, team_name="Tri Again", teammates=(jean, paul))

    (hit,) = participation_repository.search_team_results(db_session, term="tri ag", exclude_athlete_id=member.id)

    assert hit.id == row.id
    assert (hit.course.name, hit.athlete.nom) == (row.course.name, "DUPONT")
    assert [link.athlete.nom for link in hit.teammate_links] == ["DUPONT", "DURAND"]


def test_relay_flag_on_the_course_only_is_enough(db_session, member):
    row = _relay(db_session, _athlete(db_session, "Les Requins"), is_relay=False)

    assert _search(db_session, member, "requins") == [row.id]


def test_individual_results_are_not_found(db_session, member):
    _relay(db_session, _athlete(db_session, "Les Requins"), is_relay=False, course_relay=False)

    assert _search(db_session, member, "requins") == []


def test_ignores_relays_split_on_person_records(db_session, member):
    _relay(db_session, _athlete(db_session, "GILLES", "Hugo"), team_name="Tri Again")

    assert _search(db_session, member, "tri again") == []


def test_ignores_pending_and_rejected_results(db_session, member):
    team = _athlete(db_session, "Les Requins")
    _relay(db_session, team, is_pending_validation=True)
    _relay(db_session, team, is_pending_validation=True, is_rejected=True)

    assert _search(db_session, member, "requins") == []


def test_ignores_results_the_member_already_carries_or_belongs_to(db_session, member):
    paul = _athlete(db_session, "DURAND", "Paul")
    _relay(db_session, member, team_name="Les Requins", teammates=(member, paul))
    _relay(db_session, paul, team_name="Les Requins", teammates=(paul, member))
    kept = _relay(db_session, paul, team_name="Les Requins", teammates=(paul,))

    assert _search(db_session, member, "requins") == [kept.id]


@pytest.mark.parametrize("term", ["%", "_", "%%%", "   "])
def test_like_wildcards_are_literal(db_session, member, term):
    _relay(db_session, _athlete(db_session, "Les Requins"))

    assert _search(db_session, member, term) == []


def test_at_most_limit_rows_newest_first(db_session, member):
    team = _athlete(db_session, "Les Requins")
    old = _relay(db_session, team, event_date=date(2025, 6, 1))
    new_first = _relay(db_session, team, event_date=date(2026, 6, 1))
    new_second = _relay(db_session, team, event_date=date(2026, 6, 1))

    assert _search(db_session, member, "requins", limit=2) == [new_second.id, new_first.id]
    assert _search(db_session, member, "requins")[-1] == old.id


def test_anonymised_carriers_are_not_team_records(db_session, member):
    _relay(db_session, _athlete(db_session, "Anonyme 12-34"))

    assert _search(db_session, member, "anonyme") == []


def test_anonymised_carrier_of_a_composed_relay_is_not_returned(db_session, member):
    carrier, paul = _athlete(db_session, "Anonyme 12-34"), _athlete(db_session, "DURAND", "Paul")
    _relay(db_session, carrier, team_name="Tri Again", teammates=(carrier, paul))

    assert _search(db_session, member, "tri again") == []


def test_like_wildcards_match_literally(db_session, member):
    _relay(db_session, _athlete(db_session, "LES MOLLETS"))
    row = _relay(db_session, _athlete(db_session, "100% FUN"))

    assert _search(db_session, member, "100%") == [row.id]
    assert _search(db_session, member, "_") == []
