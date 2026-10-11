from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.organisation import Organisation
from app.models.personal_profile import PersonalProfile
from app.models.training_group import TrainingGroup, TrainingGroupMember
from app.models.training_participant import TrainingParticipant
from app.models.training_session import TrainingSession
from app.repositories import training_group_repository


@pytest.fixture
def organisation(db_session):
    club = Organisation(slug="tcn", name="Triathlon Club Nantais")
    db_session.add(club)
    db_session.flush()
    return club


def _profile(db_session, organisation, last_name="Martin"):
    profile = PersonalProfile(organisation_id=organisation.id, first_name="Alix", last_name=last_name)
    db_session.add(profile)
    db_session.flush()
    return profile


# --- Modèle (T002) ------------------------------------------------------------


def test_group_name_is_unique_per_organisation(db_session, organisation):
    db_session.add(TrainingGroup(organisation_id=organisation.id, name="Benjamins"))
    db_session.flush()
    db_session.add(TrainingGroup(organisation_id=organisation.id, name="Benjamins"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_a_profile_is_member_of_a_group_once(db_session, organisation):
    group = TrainingGroup(organisation_id=organisation.id, name="Benjamins")
    db_session.add(group)
    profile = _profile(db_session, organisation)
    db_session.add(TrainingGroupMember(training_group_id=group.id, profile_id=profile.id))
    db_session.flush()
    db_session.add(TrainingGroupMember(training_group_id=group.id, profile_id=profile.id))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_new_columns_have_their_defaults(db_session, organisation):
    session = TrainingSession(date=date(2026, 10, 14))
    db_session.add(session)
    db_session.flush()
    participant = TrainingParticipant(
        training_session_id=session.id, profile_id=_profile(db_session, organisation).id
    )
    db_session.add(participant)
    db_session.flush()

    assert session.recurrence_id is None
    assert session.detached is False
    assert session.groups == []
    assert participant.added_manually is True


# --- Dépôt (T009) -------------------------------------------------------------


def test_list_with_member_counts_is_sorted_by_name(db_session, organisation):
    zebres = training_group_repository.create(db_session, organisation_id=organisation.id, name="Zèbres")
    training_group_repository.create(db_session, organisation_id=organisation.id, name="Alpha")
    profile = _profile(db_session, organisation)
    training_group_repository.add_member(db_session, training_group_id=zebres.id, profile_id=profile.id)

    rows = training_group_repository.list_with_member_counts(db_session)

    assert [(group.name, count) for group, count in rows] == [("Alpha", 0), ("Zèbres", 1)]


def test_add_member_is_idempotent(db_session, organisation):
    group = training_group_repository.create(db_session, organisation_id=organisation.id, name="Alpha")
    profile = _profile(db_session, organisation)

    _, first = training_group_repository.add_member(db_session, training_group_id=group.id, profile_id=profile.id)
    _, second = training_group_repository.add_member(db_session, training_group_id=group.id, profile_id=profile.id)

    assert (first, second) == (True, False)
    assert [p.id for p in training_group_repository.list_members(db_session, group.id)] == [profile.id]


def test_remove_member(db_session, organisation):
    group = training_group_repository.create(db_session, organisation_id=organisation.id, name="Alpha")
    profile = _profile(db_session, organisation)
    training_group_repository.add_member(db_session, training_group_id=group.id, profile_id=profile.id)

    assert training_group_repository.remove_member(db_session, training_group_id=group.id, profile_id=profile.id)
    assert not training_group_repository.remove_member(db_session, training_group_id=group.id, profile_id=profile.id)
    assert training_group_repository.list_members(db_session, group.id) == []


def test_groups_of_a_profile(db_session, organisation):
    beta = training_group_repository.create(db_session, organisation_id=organisation.id, name="Beta")
    alpha = training_group_repository.create(db_session, organisation_id=organisation.id, name="Alpha")
    training_group_repository.create(db_session, organisation_id=organisation.id, name="Gamma")
    profile = _profile(db_session, organisation)
    for group in (beta, alpha):
        training_group_repository.add_member(db_session, training_group_id=group.id, profile_id=profile.id)

    groups = training_group_repository.list_groups_of_profile(db_session, profile.id)

    assert [group.name for group in groups] == ["Alpha", "Beta"]


def test_active_member_ids_skips_ended_memberships(db_session, organisation):
    alpha = training_group_repository.create(db_session, organisation_id=organisation.id, name="Alpha")
    beta = training_group_repository.create(db_session, organisation_id=organisation.id, name="Beta")
    shared = _profile(db_session, organisation, "Commun")
    ended = _profile(db_session, organisation, "Parti")
    ended.membership_ended_on = date(2026, 10, 1)
    leaving_later = _profile(db_session, organisation, "Plus tard")
    leaving_later.membership_ended_on = date(2026, 10, 14)
    for group, profile in ((alpha, shared), (beta, shared), (alpha, ended), (beta, leaving_later)):
        training_group_repository.add_member(db_session, training_group_id=group.id, profile_id=profile.id)

    ids = training_group_repository.active_member_ids(db_session, [alpha.id, beta.id], on=date(2026, 10, 14))

    assert ids == {shared.id, leaving_later.id}
