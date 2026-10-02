"""Recovery of the existing duplicates, simulated before applied (#906, #907, #908, #900)."""
from datetime import date

import pytest

from app.models.admin_action_log import AdminActionLog
from app.models.athlete import Athlete
from app.models.participation import Participation
from app.repositories import course_repository, participation_repository, user_repository
from app.services import athlete_reconciliation


def _athlete(db, nom, prenom, **fields) -> Athlete:
    athlete = Athlete(nom=nom, prenom=prenom, **fields)
    db.add(athlete)
    db.flush()
    return athlete


def _course(db, name="Tri A", day=16):
    return course_repository.get_or_create(
        db, name=name, event_date=date(2026, 5, day), event_type="triathlon-m"
    )


def _result(db, athlete, course, bib, **fields) -> Participation:
    return participation_repository.create(
        db, athlete_id=athlete.id, course_id=course.id, bib_number=bib, status="finisher",
        source_identity_key=f"{athlete.last_name_key}|{athlete.first_name_key}", **fields,
    )


@pytest.fixture
def admin(db_session):
    user = user_repository.create(db_session, email="admin@exemple.fr")
    db_session.commit()
    return user


def _actions(plan) -> list[tuple]:
    return [
        (op["family"], op["action"], op.get("kept_id"), op.get("absorbed_id"), op.get("athlete_id"))
        for op in plan["operations"]
    ]


def test_comma_names_are_split_then_joined_to_their_twin(db_session, admin):
    twin = _athlete(db_session, "JUMEAUX", "Adrien")
    whole = _athlete(db_session, "JUMEAUX, ADRIEN", "")
    trailing = _athlete(db_session, "HOFMANN,", "Patrick")
    reversed_ = _athlete(db_session, "Rose", "Courjon,")
    _result(db_session, whole, _course(db_session), "1")
    db_session.commit()

    plan = athlete_reconciliation.plan(db_session)
    athlete_reconciliation.apply(db_session, plan, user_id=admin.id)

    assert _actions(plan)[:3] == [
        ("comma_names", "merge", twin.id, whole.id, None),
        ("comma_names", "rename", None, None, trailing.id),
        ("comma_names", "rename", None, None, reversed_.id),
    ]
    db_session.expire_all()
    assert db_session.get(Athlete, whole.id) is None
    assert db_session.query(Participation).one().athlete_id == twin.id
    assert db_session.query(Participation).one().source_identity_key == "jumeaux|adrien"
    assert (db_session.get(Athlete, trailing.id).nom, db_session.get(Athlete, trailing.id).prenom) == ("HOFMANN", "Patrick")
    assert (db_session.get(Athlete, reversed_.id).nom, db_session.get(Athlete, reversed_.id).prenom) == ("Courjon", "Rose")


def test_same_key_groups_merge_into_their_principal(db_session, admin):
    principal = _athlete(db_session, "LETORT", "Léo")
    duplicate = _athlete(db_session, "LETORT", "Leo", homonym_rank=1)
    _result(db_session, duplicate, _course(db_session), "1")
    db_session.commit()

    plan = athlete_reconciliation.plan(db_session)
    athlete_reconciliation.apply(db_session, plan, user_id=admin.id)

    assert ("same_key", "merge", principal.id, duplicate.id, None) in _actions(plan)
    db_session.expire_all()
    assert db_session.get(Athlete, duplicate.id) is None


def test_a_same_key_group_with_two_bibs_on_one_race_goes_to_review(db_session, admin):
    principal = _athlete(db_session, "ANDRE", "Arthur")
    homonym = _athlete(db_session, "ANDRÉ", "Arthur", homonym_rank=1)
    course = _course(db_session)
    _result(db_session, principal, course, "1")
    _result(db_session, homonym, course, "2")
    db_session.commit()

    plan = athlete_reconciliation.plan(db_session)

    assert _actions(plan) == []
    assert plan["review"] == [
        {"family": "same_key", "athlete_ids": [principal.id, homonym.id], "reason": "same_course_bibs"}
    ]


def test_a_dated_record_and_its_undated_twin_are_merged(db_session, admin):
    """#900 : la scission déjà survenue est réparée par la famille des mêmes clés."""
    dated = _athlete(db_session, "DUPONT", "Jean", birth_date=date(1990, 1, 1))
    undated = _athlete(db_session, "DUPONT", "Jean", homonym_rank=1)
    db_session.commit()

    plan = athlete_reconciliation.plan(db_session)

    assert ("same_key", "merge", dated.id, undated.id, None) in _actions(plan)


def test_swapped_and_concatenated_pairs_merge_only_with_agreeing_signals(db_session, admin):
    """Q3 : même club ou même genre, renseigné des deux côtés, jamais une même épreuve."""
    kept = _athlete(db_session, "DUPONT", "Jean", club="CLUB")
    swapped = _athlete(db_session, "JEAN", "Dupont", club="club ")
    _result(db_session, kept, _course(db_session, "Tri A", 16), "1")
    _result(db_session, kept, _course(db_session, "Tri B", 17), "1")
    _result(db_session, swapped, _course(db_session, "Tri C", 18), "1")
    doubtful = _athlete(db_session, "MARTIN", "Luc")
    doubtful_twin = _athlete(db_session, "LUC", "Martin")
    split = _athlete(db_session, "DURAND", "Paul", gender="M")
    whole = _athlete(db_session, "DURAND PAUL", "", gender="M")
    db_session.commit()

    plan = athlete_reconciliation.plan(db_session)

    assert ("swapped", "merge", kept.id, swapped.id, None) in _actions(plan)
    assert ("concatenated", "merge", split.id, whole.id, None) in _actions(plan)
    assert {"family": "swapped", "athlete_ids": [doubtful.id, doubtful_twin.id], "reason": "no_signal"} in plan["review"]


def test_placeholder_records_are_left_alone(db_session, admin):
    _athlete(db_session, "?DOSSARD #12", "")
    _athlete(db_session, "Anonyme 3-12", "")
    _athlete(db_session, "Un turbo, un diesel & co", "")
    _athlete(db_session, "CIC", "7", club="A")
    _athlete(db_session, "7", "Cic", club="A")
    db_session.commit()

    plan = athlete_reconciliation.plan(db_session)

    assert _actions(plan) == []


def test_the_simulation_writes_nothing_and_the_application_does_exactly_its_plan(db_session, admin):
    _athlete(db_session, "LETORT", "Léo")
    _athlete(db_session, "LETORT", "Leo", homonym_rank=1)
    _athlete(db_session, "HOFMANN,", "Patrick")
    db_session.commit()
    before = sorted((a.id, a.nom, a.prenom) for a in db_session.query(Athlete))

    simulated = athlete_reconciliation.plan(db_session)
    assert sorted((a.id, a.nom, a.prenom) for a in db_session.query(Athlete)) == before

    report = athlete_reconciliation.apply(db_session, athlete_reconciliation.plan(db_session), user_id=admin.id)

    assert report["operations"] == simulated["operations"]
    assert report["errors"] == []
    assert report["applied"] is True


def test_a_second_run_finds_nothing_to_do(db_session, admin):
    _athlete(db_session, "LETORT", "Léo")
    _athlete(db_session, "LETORT", "Leo", homonym_rank=1)
    _athlete(db_session, "JUMEAUX", "Adrien")
    _athlete(db_session, "JUMEAUX, ADRIEN", "")
    _athlete(db_session, "DUPONT", "Jean", club="CLUB")
    _athlete(db_session, "JEAN", "Dupont", club="CLUB")
    db_session.commit()

    athlete_reconciliation.apply(db_session, athlete_reconciliation.plan(db_session), user_id=admin.id)

    assert athlete_reconciliation.plan(db_session)["operations"] == []


def test_an_interrupted_run_resumes_without_doing_anything_twice(db_session, admin):
    for index in range(4):
        _athlete(db_session, f"NOM{chr(65 + index)}", "Léo")
        _athlete(db_session, f"NOM{chr(65 + index)}", "Leo", homonym_rank=1)
    db_session.commit()
    full = athlete_reconciliation.plan(db_session)

    athlete_reconciliation.apply(db_session, {**full, "operations": full["operations"][:2]}, user_id=admin.id)
    rest = athlete_reconciliation.plan(db_session)
    athlete_reconciliation.apply(db_session, rest, user_id=admin.id)

    assert len(rest["operations"]) == 2
    assert db_session.query(Athlete).count() == 4


def test_each_operation_is_logged_under_the_operator(db_session, admin):
    _athlete(db_session, "LETORT", "Léo")
    _athlete(db_session, "LETORT", "Leo", homonym_rank=1)
    _athlete(db_session, "HOFMANN,", "Patrick")
    db_session.commit()

    athlete_reconciliation.apply(db_session, athlete_reconciliation.plan(db_session), user_id=admin.id)

    actions = sorted(entry.action for entry in db_session.query(AdminActionLog))
    assert actions == ["athlete.merge", "athlete.update"]
    assert {entry.user_id for entry in db_session.query(AdminActionLog)} == {admin.id}


def test_an_operation_that_became_impossible_is_reported_and_the_others_still_run(db_session, admin):
    principal = _athlete(db_session, "LETORT", "Léo")
    duplicate = _athlete(db_session, "LETORT", "Leo", homonym_rank=1)
    _athlete(db_session, "HOFMANN,", "Patrick")
    db_session.commit()
    plan = athlete_reconciliation.plan(db_session)
    db_session.delete(db_session.get(Athlete, duplicate.id))
    db_session.commit()

    report = athlete_reconciliation.apply(db_session, plan, user_id=admin.id)

    assert len(report["errors"]) == 1
    assert report["errors"][0]["operation"]["absorbed_id"] == duplicate.id
    assert db_session.query(Athlete).filter_by(nom="HOFMANN").count() == 1
    assert db_session.get(Athlete, principal.id) is not None
