from datetime import date

import pytest

from app.core.exceptions import DomainError, NotFoundError
from app.models.organisation import Organisation
from app.models.training_participant import TrainingParticipant
from app.repositories import profile_repository, training_session_repository, user_repository
from app.services import training_group_service as service


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


def _profile(db_session, organisation, last_name="Martin", **fields):
    profile = profile_repository.create(
        db_session, organisation_id=organisation.id, first_name="Alix", last_name=last_name
    )
    for field, value in fields.items():
        setattr(profile, field, value)
    db_session.flush()
    return profile


def test_create_trims_the_name(db_session, actor, organisation):
    group = service.create_group(db_session, actor, name="  Benjamins mercredi ")

    assert group.name == "Benjamins mercredi"
    assert group.organisation_id == organisation.id


@pytest.mark.parametrize("name", ["", "   "])
def test_an_empty_name_is_refused_in_french(db_session, actor, organisation, name):
    with pytest.raises(DomainError) as refusal:
        service.create_group(db_session, actor, name=name)

    assert refusal.value.status_code == 422
    assert refusal.value.message == "Le nom du groupe est obligatoire."


def test_a_too_long_name_is_refused(db_session, actor, organisation):
    with pytest.raises(DomainError) as refusal:
        service.create_group(db_session, actor, name="x" * 81)

    assert refusal.value.message == "Le nom du groupe compte au plus 80 caractères."


def test_a_taken_name_is_refused_on_create_and_rename(db_session, actor, organisation):
    service.create_group(db_session, actor, name="Benjamins")
    other = service.create_group(db_session, actor, name="Minimes")

    with pytest.raises(DomainError) as on_create:
        service.create_group(db_session, actor, name="Benjamins")
    with pytest.raises(DomainError) as on_rename:
        service.rename_group(db_session, actor, other, name="Benjamins")

    assert on_create.value.message == on_rename.value.message == "Un groupe porte déjà ce nom."
    assert other.name == "Minimes"


def test_renaming_a_group_to_its_own_name_is_accepted(db_session, actor, organisation):
    group = service.create_group(db_session, actor, name="Benjamins")

    service.rename_group(db_session, actor, group, name="Benjamins")

    assert group.name == "Benjamins"


def test_unknown_group_is_a_404(db_session):
    with pytest.raises(NotFoundError):
        service.get_group_or_404(db_session, 999)


def test_adding_an_unknown_profile_is_a_404(db_session, actor, organisation):
    group = service.create_group(db_session, actor, name="Benjamins")

    with pytest.raises(NotFoundError):
        service.add_member(db_session, actor, group, profile_id=999)


def test_detail_lists_members_and_list_counts_them(db_session, actor, organisation):
    group = service.create_group(db_session, actor, name="Benjamins")
    zoe = _profile(db_session, organisation, "Roux")
    alix = _profile(db_session, organisation, "Martin")
    service.add_member(db_session, actor, group, profile_id=zoe.id)
    service.add_member(db_session, actor, group, profile_id=alix.id)
    service.add_member(db_session, actor, group, profile_id=alix.id)
    service.remove_member(db_session, actor, group, profile_id=zoe.id)

    detail = service.group_detail_view(db_session, group)
    (row,) = service.list_group_views(db_session)

    assert [member["id"] for member in detail["members"]] == [alix.id]
    assert row == {"id": group.id, "name": "Benjamins", "member_count": 1}


def test_deleting_a_group_keeps_the_enrolments_it_produced(db_session, actor, organisation):
    group = service.create_group(db_session, actor, name="Benjamins")
    profile = _profile(db_session, organisation)
    service.add_member(db_session, actor, group, profile_id=profile.id)
    session = training_session_repository.create(db_session, date=date(2026, 9, 20))
    session.groups.append(group)
    training_session_repository.add_participant(db_session, training_session_id=session.id, profile_id=profile.id)

    service.delete_group(db_session, actor, group)

    assert db_session.query(TrainingParticipant).filter_by(training_session_id=session.id).count() == 1
    db_session.expire(session)
    assert session.groups == []
