from datetime import date

import pytest

from app.core.exceptions import NotFoundError
from app.models.organisation import Organisation
from app.repositories import profile_repository, user_repository
from app.services.jeunes import entrainements as service


@pytest.fixture
def actor(db_session):
    user = user_repository.create(db_session, email="encadrant@exemple.fr")
    db_session.flush()
    return user


@pytest.fixture
def organisation(db_session):
    ligne = Organisation(slug="tcn", name="Triathlon Club Nantais")
    db_session.add(ligne)
    db_session.flush()
    return ligne


@pytest.fixture
def jeune(db_session, organisation):
    """Un profil jeune réel (#867) — `jeune_id` référence `personal_profiles.id`."""
    return profile_repository.create(
        db_session, organisation_id=organisation.id, first_name="Alix", last_name="Martin"
    )


def test_get_entrainement_or_404_raises_on_unknown_id(db_session):
    with pytest.raises(NotFoundError):
        service.get_entrainement_or_404(db_session, 999)


def test_entrainement_view_reports_participant_count(db_session, actor, organisation):
    entrainement = service.create_entrainement(db_session, actor, date=date(2026, 9, 20))
    zoe = profile_repository.create(
        db_session, organisation_id=organisation.id, first_name="Zoé", last_name="Roux"
    )
    alix = profile_repository.create(
        db_session, organisation_id=organisation.id, first_name="Alix", last_name="Martin"
    )
    service.add_participant(db_session, actor, entrainement, jeune_id=zoe.id)
    service.add_participant(db_session, actor, entrainement, jeune_id=alix.id)

    vue = service.entrainement_view(db_session, entrainement)

    assert vue["participant_count"] == 2
    assert vue["date"] == date(2026, 9, 20)


def test_entrainement_detail_view_lists_participants(db_session, actor, jeune):
    entrainement = service.create_entrainement(db_session, actor, date=date(2026, 9, 20))
    service.add_participant(db_session, actor, entrainement, jeune_id=jeune.id)

    detail = service.entrainement_detail_view(db_session, entrainement)

    assert [p["jeune_id"] for p in detail["participants"]] == [jeune.id]


def test_update_entrainement_only_writes_provided_fields(db_session, actor):
    entrainement = service.create_entrainement(
        db_session, actor, date=date(2026, 9, 20), lieu="Base nautique"
    )

    service.update_entrainement(db_session, actor, entrainement, type_seance="Natation")

    assert entrainement.lieu == "Base nautique"
    assert entrainement.type_seance == "Natation"


def test_add_participant_is_idempotent(db_session, actor, jeune):
    entrainement = service.create_entrainement(db_session, actor, date=date(2026, 9, 20))

    service.add_participant(db_session, actor, entrainement, jeune_id=jeune.id)
    service.add_participant(db_session, actor, entrainement, jeune_id=jeune.id)

    vue = service.entrainement_view(db_session, entrainement)
    assert vue["participant_count"] == 1


def test_add_participant_raises_on_unknown_jeune(db_session, actor):
    """`jeune_id` référence `personal_profiles.id` (#867) : un profil inexistant
    est refusé en Python, avant l'écriture — jamais laissé à la seule
    contrainte SQL, muette en SQLite."""
    entrainement = service.create_entrainement(db_session, actor, date=date(2026, 9, 20))

    with pytest.raises(NotFoundError):
        service.add_participant(db_session, actor, entrainement, jeune_id=999)


def test_remove_participant_is_idempotent(db_session, actor, jeune):
    entrainement = service.create_entrainement(db_session, actor, date=date(2026, 9, 20))
    service.add_participant(db_session, actor, entrainement, jeune_id=jeune.id)

    service.remove_participant(db_session, actor, entrainement, jeune_id=jeune.id)
    service.remove_participant(db_session, actor, entrainement, jeune_id=jeune.id)

    vue = service.entrainement_view(db_session, entrainement)
    assert vue["participant_count"] == 0


def test_add_participant_can_mark_present_in_the_same_call(db_session, actor, jeune):
    entrainement = service.create_entrainement(db_session, actor, date=date(2026, 9, 20))

    service.add_participant(db_session, actor, entrainement, jeune_id=jeune.id, present=True)

    detail = service.entrainement_detail_view(db_session, entrainement)
    assert detail["participants"][0]["present"] is True


def test_entrainement_detail_view_reports_presence(db_session, actor, jeune):
    """Un jeune non encore pointé reste `None` — pas `False` (FR-002)."""
    entrainement = service.create_entrainement(db_session, actor, date=date(2026, 9, 20))
    service.add_participant(db_session, actor, entrainement, jeune_id=jeune.id)

    detail = service.entrainement_detail_view(db_session, entrainement)

    assert detail["participants"][0]["present"] is None


def test_set_presence_updates_status(db_session, actor, jeune):
    entrainement = service.create_entrainement(db_session, actor, date=date(2026, 9, 20))
    service.add_participant(db_session, actor, entrainement, jeune_id=jeune.id)

    service.set_presence(db_session, actor, entrainement, jeune_id=jeune.id, present=True)

    detail = service.entrainement_detail_view(db_session, entrainement)
    assert detail["participants"][0]["present"] is True


def test_set_presence_raises_when_jeune_not_registered(db_session, actor, jeune):
    entrainement = service.create_entrainement(db_session, actor, date=date(2026, 9, 20))

    with pytest.raises(NotFoundError):
        service.set_presence(db_session, actor, entrainement, jeune_id=jeune.id, present=True)


def test_update_entrainement_can_change_note(db_session, actor):
    entrainement = service.create_entrainement(db_session, actor, date=date(2026, 9, 20))

    service.update_entrainement(db_session, actor, entrainement, note="Bassin partagé.")

    assert entrainement.note == "Bassin partagé."
