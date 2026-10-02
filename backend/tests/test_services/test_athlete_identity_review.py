"""Identity cases for an admin to decide (#908, #967, epic #1146)."""
from datetime import date

import pytest

from app.core.exceptions import DomainError, DuplicateError, NotFoundError
from app.models.admin_action_log import AdminActionLog
from app.models.athlete import Athlete
from app.models.athlete_alias import AthleteAlias
from app.repositories import course_repository, participation_repository, user_repository
from app.services import athlete_identity_review

TCN = "Triathlon Club Nantais"


def _athlete(db, nom, prenom, **fields) -> Athlete:
    athlete = Athlete(nom=nom, prenom=prenom, **fields)
    db.add(athlete)
    db.flush()
    return athlete


def _course(db, name="Tri A", **fields):
    return course_repository.get_or_create(
        db, name=name, event_date=date(2026, 5, 16), event_type="triathlon-m", **fields
    )


def _result(db, athlete, course, bib, **fields):
    return participation_repository.create(
        db, athlete_id=athlete.id, course_id=course.id, bib_number=bib, status="finisher", **fields
    )


def _reasons(db) -> list[tuple[str, list[int]]]:
    return [
        (candidate["reason"], [a["id"] for a in candidate["athletes"]])
        for candidate in athlete_identity_review.find_candidates(db)
    ]


def test_a_club_record_with_two_bibs_on_one_race_is_listed_with_its_conflict(db_session):
    member = _athlete(db_session, "MARTIN", "Thomas", club=TCN)
    course = _course(db_session)
    _result(db_session, member, course, "1", category="M25-29", total_time="02:00:00")
    _result(db_session, member, course, "2", category="M45-49", total_time="02:10:00")

    [candidate] = athlete_identity_review.find_candidates(db_session)

    assert candidate["reason"] == "same_course_bibs" and candidate["reason_label"]
    assert [a["id"] for a in candidate["athletes"]] == [member.id]
    assert candidate["athletes"][0]["categories"] == ["M25-29", "M45-49"]
    [conflict] = candidate["conflicts"]
    assert (conflict["course_id"], sorted(e["bib"] for e in conflict["entries"])) == (course.id, ["1", "2"])


def test_a_record_outside_the_club_with_two_bibs_is_not_listed(db_session):
    outsider = _athlete(db_session, "MARTIN", "Thomas", club="AUTRE CLUB")
    course = _course(db_session)
    _result(db_session, outsider, course, "1")
    _result(db_session, outsider, course, "2")

    assert _reasons(db_session) == []


def test_a_club_result_on_a_record_counts_even_when_the_record_club_differs(db_session):
    """Le club se lit sur la fiche ou sur les résultats en conflit (Q1)."""
    athlete = _athlete(db_session, "MARTIN", "Thomas", club="AUTRE CLUB")
    course = _course(db_session)
    _result(db_session, athlete, course, "1", club=TCN)
    _result(db_session, athlete, course, "2")

    assert _reasons(db_session) == [("same_course_bibs", [athlete.id])]


def test_homonyms_are_listed_only_when_one_belongs_to_the_club(db_session):
    principal = _athlete(db_session, "MARTIN", "Thomas", club=TCN)
    homonym = _athlete(db_session, "MARTIN", "Thomas", homonym_rank=1)
    _athlete(db_session, "DURAND", "Paul")
    _athlete(db_session, "DURAND", "Paul", homonym_rank=1)

    assert _reasons(db_session) == [("club_homonym", [principal.id, homonym.id])]


def test_a_swapped_pair_the_recovery_would_not_merge_is_listed(db_session):
    """Q3 : sans club ni genre communs, la reprise ne fusionne pas ; la paire va en revue."""
    first = _athlete(db_session, "DUPONT", "Jean", club="A", gender="M")
    second = _athlete(db_session, "JEAN", "Dupont", club="B", gender="F")

    assert _reasons(db_session) == [("swapped", [first.id, second.id])]


def test_a_swapped_pair_the_recovery_will_merge_is_not_listed(db_session):
    _athlete(db_session, "DUPONT", "Jean", club="CLUB", gender="M")
    _athlete(db_session, "JEAN", "Dupont", club="club ", gender="")

    assert _reasons(db_session) == []


def test_a_swapped_pair_on_one_race_is_listed_even_with_agreeing_signals(db_session):
    first = _athlete(db_session, "DUPONT", "Jean", club="CLUB")
    second = _athlete(db_session, "JEAN", "Dupont", club="CLUB")
    course = _course(db_session)
    _result(db_session, first, course, "1")
    _result(db_session, second, course, "2")

    [candidate] = athlete_identity_review.find_candidates(db_session)

    assert candidate["reason"] == "swapped"
    assert [c["course_id"] for c in candidate["conflicts"]] == [course.id]


def test_a_concatenated_pair_is_listed(db_session):
    split = _athlete(db_session, "DUPONT", "Jean", club="A")
    whole = _athlete(db_session, "DUPONT JEAN", "", club="B")

    assert _reasons(db_session) == [("concatenated", [split.id, whole.id])]


def test_a_principal_record_on_a_variant_of_another_one_is_listed(db_session):
    """Même club des deux côtés : la règle de la reprise ne s'applique pas à ce motif."""
    kept = _athlete(db_session, "DUPONT", "Jean", club="CLUB", gender="M")
    db_session.add(AthleteAlias(last_name_key="dupomt", first_name_key="jean", athlete_id=kept.id))
    recreated = _athlete(db_session, "DUPOMT", "Jean", club="CLUB", gender="M")

    assert _reasons(db_session) == [("alias_collision", [kept.id, recreated.id])]


def test_candidates_come_in_a_stable_order(db_session):
    first = _athlete(db_session, "DUPONT", "Jean", club="A", gender="M")
    second = _athlete(db_session, "JEAN", "Dupont", club="B", gender="F")
    principal = _athlete(db_session, "MARTIN", "Thomas", club=TCN)
    homonym = _athlete(db_session, "MARTIN", "Thomas", homonym_rank=1)

    assert _reasons(db_session) == [
        ("club_homonym", [principal.id, homonym.id]), ("swapped", [first.id, second.id])
    ]


def test_an_ignored_pair_is_no_longer_listed_and_the_gesture_is_logged(db_session):
    first = _athlete(db_session, "DUPONT", "Jean", club="A", gender="M")
    second = _athlete(db_session, "JEAN", "Dupont", club="B", gender="F")
    admin = user_repository.create(db_session, email="admin@exemple.fr")

    out = athlete_identity_review.ignore_pair(
        db_session, athlete_id_a=second.id, athlete_id_b=first.id, user_id=admin.id
    )

    assert (out["athlete_id_a"], out["athlete_id_b"]) == (first.id, second.id)
    assert _reasons(db_session) == []
    [entry] = db_session.query(AdminActionLog).all()
    assert (entry.action, entry.entity_id) == ("athlete_identity.ignore", first.id)


def test_ignoring_a_pair_refuses_bad_requests(db_session):
    first = _athlete(db_session, "DUPONT", "Jean")
    second = _athlete(db_session, "JEAN", "Dupont")
    admin = user_repository.create(db_session, email="admin@exemple.fr")

    with pytest.raises(DomainError) as same:
        athlete_identity_review.ignore_pair(db_session, athlete_id_a=first.id, athlete_id_b=first.id, user_id=admin.id)
    assert same.value.status_code == 400
    with pytest.raises(NotFoundError):
        athlete_identity_review.ignore_pair(db_session, athlete_id_a=first.id, athlete_id_b=999, user_id=admin.id)
    athlete_identity_review.ignore_pair(db_session, athlete_id_a=first.id, athlete_id_b=second.id, user_id=admin.id)
    with pytest.raises(DuplicateError):
        athlete_identity_review.ignore_pair(db_session, athlete_id_a=second.id, athlete_id_b=first.id, user_id=admin.id)


def test_the_recovery_signal_rule_needs_values_on_both_sides():
    """Q3, A1 : même club ou même genre, renseigné des deux côtés, et jamais une même épreuve."""
    signals = athlete_identity_review.recovery_would_merge

    assert signals(Athlete(club="Club ", gender=""), Athlete(club="club", gender="M"), shared_course=False, blocked=False)
    assert signals(Athlete(club=None, gender="F"), Athlete(club="", gender="F"), shared_course=False, blocked=False)
    assert not signals(Athlete(club=None, gender=""), Athlete(club=None, gender=""), shared_course=False, blocked=False)
    assert not signals(Athlete(club="A", gender="M"), Athlete(club="A", gender="M"), shared_course=True, blocked=False)
    assert not signals(Athlete(club="A", gender="M"), Athlete(club="A", gender="M"), shared_course=False, blocked=True)



def test_two_bibless_results_of_one_club_record_are_not_listed(db_session):
    member = _athlete(db_session, "MARTIN", "Thomas", club=TCN)
    course = _course(db_session)
    _result(db_session, member, course, None)
    _result(db_session, member, course, None)

    assert _reasons(db_session) == []


def test_a_relay_is_never_a_two_bib_case(db_session):
    member = _athlete(db_session, "MARTIN", "Thomas", club=TCN)
    relay = _course(db_session, "Relais", is_relay=True)
    _result(db_session, member, relay, "1")
    _result(db_session, member, relay, "2")

    assert _reasons(db_session) == []


def test_a_club_homonym_is_listed_when_the_club_member_is_the_homonym(db_session):
    principal = _athlete(db_session, "MARTIN", "Thomas")
    homonym = _athlete(db_session, "MARTIN", "Thomas", homonym_rank=1, club=TCN)

    assert _reasons(db_session) == [("club_homonym", [principal.id, homonym.id])]


def test_three_homonyms_give_one_case_per_pair_and_each_can_be_set_aside(db_session):
    member = _athlete(db_session, "MARTIN", "Thomas", club=TCN)
    second = _athlete(db_session, "MARTIN", "Thomas", homonym_rank=1)
    third = _athlete(db_session, "MARTIN", "Thomas", homonym_rank=2)
    admin = user_repository.create(db_session, email="admin@exemple.fr")

    assert _reasons(db_session) == [
        ("club_homonym", [member.id, second.id]), ("club_homonym", [member.id, third.id]),
    ]
    for other in (second, third):
        athlete_identity_review.ignore_pair(db_session, athlete_id_a=member.id, athlete_id_b=other.id, user_id=admin.id)
    assert _reasons(db_session) == []


def test_a_concatenated_pair_the_recovery_will_merge_is_not_listed(db_session):
    _athlete(db_session, "DUPONT", "Jean", club="CLUB")
    _athlete(db_session, "DUPONT JEAN", "", club="club")

    assert _reasons(db_session) == []


def test_a_pair_the_merge_would_refuse_stays_listed_despite_agreeing_signals(db_session):
    """Deux comptes membres : la reprise ne pourra pas fusionner, la paire reste en revue."""
    first = _athlete(db_session, "DUPONT", "Jean", club="CLUB", gender="M")
    second = _athlete(db_session, "JEAN", "Dupont", club="CLUB", gender="M")
    for athlete, email in [(first, "a@x.fr"), (second, "b@x.fr")]:
        user_repository.create(db_session, email=email).athlete_id = athlete.id
    db_session.flush()

    assert _reasons(db_session) == [("swapped", [first.id, second.id])]


def test_a_pair_on_one_relay_counts_as_a_shared_race(db_session):
    first = _athlete(db_session, "DUPONT", "Jean", club="CLUB")
    second = _athlete(db_session, "JEAN", "Dupont", club="CLUB")
    relay = _result(db_session, first, _course(db_session, "Relais", is_relay=True), "9")
    participation_repository.replace_teammates(db_session, relay, [first.id, second.id])

    assert _reasons(db_session) == [("swapped", [first.id, second.id])]


def test_a_pair_is_listed_once_under_its_first_reason(db_session):
    kept = _athlete(db_session, "DUPONT", "Jean", club="A", gender="M")
    db_session.add(AthleteAlias(last_name_key="jean", first_name_key="dupont", athlete_id=kept.id))
    recreated = _athlete(db_session, "JEAN", "Dupont", club="B", gender="F")

    assert _reasons(db_session) == [("swapped", [kept.id, recreated.id])]


def test_numbered_or_placeholder_records_are_left_out_of_swapped_and_concatenated(db_session):
    _athlete(db_session, "CIC", "7", club="A")
    _athlete(db_session, "7", "Cic", club="B")
    _athlete(db_session, "DOSSARD", "12", club="A")
    _athlete(db_session, "DOSSARD 12", "", club="B")

    assert _reasons(db_session) == []


def test_cases_of_one_reason_come_by_smallest_id(db_session):
    late = _athlete(db_session, "ZORRO", "Ana", club="A", gender="M")
    early_twin = _athlete(db_session, "ANA", "Zorro", club="B", gender="F")
    other = _athlete(db_session, "BERT", "Luc", club="A", gender="M")
    other_twin = _athlete(db_session, "LUC", "Bert", club="B", gender="F")

    assert _reasons(db_session) == [("swapped", [late.id, early_twin.id]), ("swapped", [other.id, other_twin.id])]


def test_the_count_matches_the_list(db_session):
    _athlete(db_session, "DUPONT", "Jean", club="A", gender="M")
    _athlete(db_session, "JEAN", "Dupont", club="B", gender="F")

    assert athlete_identity_review.count(db_session) == len(athlete_identity_review.find_candidates(db_session)) == 1
