from datetime import date, time, timedelta

import pytest

from app.core.exceptions import DomainError
from app.models.organisation import Organisation
from app.models.training_session import TrainingSession
from app.repositories import profile_repository, user_repository
from app.services import training_group_service, training_session_service
from app.services import training_recurrence_service as service

WEDNESDAY = 2


@pytest.fixture
def actor(db_session):
    user = user_repository.create(db_session, email="encadrant@exemple.fr")
    db_session.flush()
    return user


@pytest.fixture
def organisation(db_session):
    club = Organisation(slug="tcn", name="Triathlon Club Nantais")
    db_session.add(club)
    db_session.flush()
    return club


# --- Dates (T032) ---------------------------------------------------------------


def test_dates_fall_on_the_weekday_with_both_bounds_included():
    dates = service.occurrence_dates(WEDNESDAY, date(2026, 10, 1), date(2026, 11, 25))

    assert dates[0] == date(2026, 10, 7)
    assert dates[-1] == date(2026, 11, 25)
    assert len(dates) == 8
    assert {day.weekday() for day in dates} == {WEDNESDAY}


def test_an_end_before_the_start_is_refused():
    with pytest.raises(DomainError) as refusal:
        service.occurrence_dates(WEDNESDAY, date(2026, 11, 1), date(2026, 10, 1))

    assert refusal.value.status_code == 422
    assert refusal.value.message == "La date de fin précède la date de début."


def test_a_period_without_occurrence_is_refused():
    with pytest.raises(DomainError) as refusal:
        service.occurrence_dates(WEDNESDAY, date(2026, 10, 1), date(2026, 10, 6))

    assert refusal.value.message == "Aucune séance dans cette période."


def test_more_than_53_occurrences_are_refused_with_the_bound():
    start = date(2026, 9, 2)
    assert len(service.occurrence_dates(WEDNESDAY, start, start + timedelta(weeks=52))) == 53

    with pytest.raises(DomainError) as refusal:
        service.occurrence_dates(WEDNESDAY, start, start + timedelta(weeks=53))

    assert "53" in refusal.value.message


# --- Création, modification, suppression (T033, T034) --------------------------


def _next(weekday: int, weeks: int = 0) -> date:
    today = date.today()
    return today + timedelta(days=(weekday - today.weekday()) % 7 or 7, weeks=weeks)


def _sessions(db_session, recurrence_id):
    return (
        db_session.query(TrainingSession)
        .filter_by(recurrence_id=recurrence_id)
        .order_by(TrainingSession.date)
        .all()
    )


def _create(db_session, actor, weeks=3, **fields):
    start = _next(WEDNESDAY)
    return service.create_recurrence(
        db_session,
        actor,
        weekday=WEDNESDAY,
        start_time=fields.pop("start_time", time(14, 0)),
        location=fields.pop("location", "Piscine"),
        session_type=None,
        starts_on=start,
        ends_on=start + timedelta(weeks=weeks - 1),
        group_ids=fields.pop("group_ids", []),
    )


def test_creation_generates_one_session_per_date_with_group_members(db_session, actor, organisation):
    young = profile_repository.create(db_session, organisation_id=organisation.id, first_name="A", last_name="B")
    group = training_group_service.create_group(db_session, actor, name="Benjamins")
    training_group_service.add_member(db_session, actor, group, profile_id=young.id)

    recurrence, created = _create(db_session, actor, group_ids=[group.id])

    sessions = _sessions(db_session, recurrence.id)
    assert created == 3 == len(sessions)
    assert all(s.start_time == time(14, 0) and s.location == "Piscine" for s in sessions)
    assert all([p.profile_id for p in s.participants] == [young.id] for s in sessions)


def test_a_session_changed_alone_is_detached(db_session, actor):
    recurrence, _ = _create(db_session, actor)
    first, second, _third = _sessions(db_session, recurrence.id)

    training_session_service.update_training_session(db_session, actor, first, location="Lac")
    training_session_service.update_training_session(db_session, actor, second, note="Bassin partagé.")

    assert first.detached is True
    assert second.detached is False


def test_an_update_reaches_only_syncable_attached_sessions(db_session, actor, organisation):
    young = profile_repository.create(db_session, organisation_id=organisation.id, first_name="A", last_name="B")
    recurrence, _ = _create(db_session, actor)
    detached, started, plain = _sessions(db_session, recurrence.id)
    training_session_service.update_training_session(db_session, actor, detached, location="Lac")
    training_session_service.add_participant(db_session, actor, started, profile_id=young.id, present=True)

    service.update_recurrence(db_session, actor, recurrence, start_time=time(15, 0), location="Gymnase")

    assert (detached.start_time, detached.location) == (time(14, 0), "Lac")
    assert (started.start_time, started.location) == (time(14, 0), "Piscine")
    assert (plain.start_time, plain.location) == (time(15, 0), "Gymnase")


def test_an_update_of_the_period_deletes_and_creates_dates(db_session, actor):
    recurrence, _ = _create(db_session, actor)
    first, second, _third = _sessions(db_session, recurrence.id)

    service.update_recurrence(
        db_session, actor, recurrence, starts_on=second.date, ends_on=second.date + timedelta(weeks=2)
    )

    dates = [s.date for s in _sessions(db_session, recurrence.id)]
    assert dates == [second.date, second.date + timedelta(weeks=1), second.date + timedelta(weeks=2)]
    assert db_session.get(TrainingSession, first.id) is None


def test_a_session_deleted_alone_is_not_recreated_by_an_update(db_session, actor):
    recurrence, _ = _create(db_session, actor)
    first, _second, _third = _sessions(db_session, recurrence.id)
    training_session_service.delete_training_session(db_session, actor, first)

    service.update_recurrence(db_session, actor, recurrence, location="Gymnase")

    assert len(_sessions(db_session, recurrence.id)) == 2


def test_deletion_keeps_started_or_detached_sessions(db_session, actor, organisation):
    young = profile_repository.create(db_session, organisation_id=organisation.id, first_name="A", last_name="B")
    recurrence, _ = _create(db_session, actor, weeks=4)
    detached, started, plain, _other = _sessions(db_session, recurrence.id)
    training_session_service.update_training_session(db_session, actor, detached, location="Lac")
    training_session_service.add_participant(db_session, actor, started, profile_id=young.id, present=False)
    assert service.recurrence_view(db_session, recurrence)["upcoming_session_count"] == 2

    outcome = service.delete_recurrence(db_session, actor, recurrence)

    assert outcome == {"deleted_session_count": 2, "kept_session_count": 2}
    assert db_session.get(TrainingSession, plain.id) is None
    assert detached.recurrence_id is None and started.recurrence_id is None


def test_saving_unchanged_values_does_not_detach(db_session, actor):
    recurrence, _ = _create(db_session, actor)
    first = _sessions(db_session, recurrence.id)[0]

    training_session_service.update_training_session(
        db_session, actor, first, date=first.date, start_time=time(14, 0), location="Piscine", group_ids=[]
    )

    assert first.detached is False


def test_a_manual_removal_survives_a_recurrence_update(db_session, actor, organisation):
    young = profile_repository.create(db_session, organisation_id=organisation.id, first_name="A", last_name="B")
    group = training_group_service.create_group(db_session, actor, name="Benjamins")
    training_group_service.add_member(db_session, actor, group, profile_id=young.id)
    recurrence, _ = _create(db_session, actor, group_ids=[group.id])
    first = _sessions(db_session, recurrence.id)[0]
    training_session_service.remove_participant(db_session, actor, first, profile_id=young.id)

    service.update_recurrence(db_session, actor, recurrence, location="Gymnase", group_ids=[group.id])

    assert first.location == "Gymnase"
    assert first.participants == []


def test_a_date_added_to_the_period_is_not_doubled(db_session, actor):
    recurrence, _ = _create(db_session, actor)
    last = _sessions(db_session, recurrence.id)[-1]
    training_session_service.update_training_session(
        db_session, actor, last, date=last.date + timedelta(weeks=1)
    )

    service.update_recurrence(db_session, actor, recurrence, ends_on=recurrence.ends_on + timedelta(weeks=1))

    dates = [s.date for s in _sessions(db_session, recurrence.id)]
    assert len(dates) == len(set(dates))


def test_deleting_a_group_then_its_recurrence_holds_with_enforced_foreign_keys(db_session_fk):
    db = db_session_fk
    club = Organisation(slug="tcn", name="Triathlon Club Nantais")
    db.add(club)
    db.flush()
    actor = user_repository.create(db, email="encadrant@exemple.fr")
    young = profile_repository.create(db, organisation_id=club.id, first_name="A", last_name="B")
    group = training_group_service.create_group(db, actor, name="Benjamins")
    training_group_service.add_member(db, actor, group, profile_id=young.id)
    recurrence, _ = _create(db, actor, group_ids=[group.id])

    training_group_service.delete_group(db, actor, group)
    service.delete_recurrence(db, actor, recurrence)
    db.flush()

    assert db.query(TrainingSession).count() == 0


def test_the_recurrence_list_query_count_does_not_grow_with_sessions(db_session, actor):
    from sqlalchemy import event

    def count_queries():
        db_session.expire_all()
        statements = []
        engine = db_session.get_bind()
        listener = lambda *args: statements.append(args[2])  # noqa: E731
        event.listen(engine, "before_cursor_execute", listener)
        try:
            service.list_recurrence_views(db_session)
        finally:
            event.remove(engine, "before_cursor_execute", listener)
        return len(statements)

    recurrence, _ = _create(db_session, actor, weeks=2)
    few = count_queries()
    service.update_recurrence(db_session, actor, recurrence, ends_on=recurrence.ends_on + timedelta(weeks=10))

    assert count_queries() == few
