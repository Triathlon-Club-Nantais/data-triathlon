from datetime import date

import pytest

from app.core.exceptions import NotFoundError
from app.models.organisation import Organisation
from app.repositories import profile_repository, user_repository
from app.services import training_session_service as service


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
def profile(db_session, organisation):
    """Un profil jeune réel (#867) — `profile_id` référence `personal_profiles.id`."""
    return profile_repository.create(
        db_session, organisation_id=organisation.id, first_name="Alix", last_name="Martin"
    )


def test_get_training_session_or_404_raises_on_unknown_id(db_session):
    with pytest.raises(NotFoundError):
        service.get_training_session_or_404(db_session, 999)


def test_list_training_session_views_reports_participant_count(db_session, actor, organisation):
    training_session = service.create_training_session(db_session, actor, date=date(2026, 9, 20))
    zoe = profile_repository.create(
        db_session, organisation_id=organisation.id, first_name="Zoé", last_name="Roux"
    )
    alix = profile_repository.create(
        db_session, organisation_id=organisation.id, first_name="Alix", last_name="Martin"
    )
    service.add_participant(db_session, actor, training_session, profile_id=zoe.id)
    service.add_participant(db_session, actor, training_session, profile_id=alix.id)

    (vue,) = service.list_training_session_views(db_session)

    assert vue["participant_count"] == 2
    assert vue["date"] == date(2026, 9, 20)


def test_list_training_session_views_query_count_does_not_grow_with_sessions(
    db_session, actor, profile
):
    """Un `COUNT` par séance coûtait une requête par ligne du calendrier."""
    from sqlalchemy import event

    for jour in range(20, 25):
        training_session = service.create_training_session(db_session, actor, date=date(2026, 9, jour))
        service.add_participant(db_session, actor, training_session, profile_id=profile.id)
    db_session.commit()

    requetes = []

    def _mouchard(conn, cursor, statement, *reste):
        requetes.append(statement)

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", _mouchard)
    try:
        vues = service.list_training_session_views(db_session)
    finally:
        event.remove(engine, "before_cursor_execute", _mouchard)

    assert [vue["participant_count"] for vue in vues] == [1] * 5
    assert len(requetes) == 2, requetes


def test_training_session_detail_view_lists_participants(db_session, actor, profile):
    training_session = service.create_training_session(db_session, actor, date=date(2026, 9, 20))
    service.add_participant(db_session, actor, training_session, profile_id=profile.id)

    detail = service.training_session_detail_view(db_session, training_session)

    assert [p["profile_id"] for p in detail["participants"]] == [profile.id]


def test_update_entrainement_only_writes_provided_fields(db_session, actor):
    training_session = service.create_training_session(
        db_session, actor, date=date(2026, 9, 20), location="Base nautique"
    )

    service.update_training_session(db_session, actor, training_session, session_type="Natation")

    assert training_session.location == "Base nautique"
    assert training_session.session_type == "Natation"


def test_add_participant_is_idempotent(db_session, actor, profile):
    training_session = service.create_training_session(db_session, actor, date=date(2026, 9, 20))

    service.add_participant(db_session, actor, training_session, profile_id=profile.id)
    service.add_participant(db_session, actor, training_session, profile_id=profile.id)

    detail = service.training_session_detail_view(db_session, training_session)
    assert detail["participant_count"] == 1


def test_add_participant_raises_on_unknown_jeune(db_session, actor):
    """`profile_id` référence `personal_profiles.id` (#867) : un profil inexistant
    est refusé en Python, avant l'écriture — jamais laissé à la seule
    contrainte SQL, muette en SQLite."""
    training_session = service.create_training_session(db_session, actor, date=date(2026, 9, 20))

    with pytest.raises(NotFoundError):
        service.add_participant(db_session, actor, training_session, profile_id=999)


def test_remove_participant_is_idempotent(db_session, actor, profile):
    training_session = service.create_training_session(db_session, actor, date=date(2026, 9, 20))
    service.add_participant(db_session, actor, training_session, profile_id=profile.id)

    service.remove_participant(db_session, actor, training_session, profile_id=profile.id)
    service.remove_participant(db_session, actor, training_session, profile_id=profile.id)

    detail = service.training_session_detail_view(db_session, training_session)
    assert detail["participant_count"] == 0


def test_add_participant_can_mark_present_in_the_same_call(db_session, actor, profile):
    training_session = service.create_training_session(db_session, actor, date=date(2026, 9, 20))

    service.add_participant(db_session, actor, training_session, profile_id=profile.id, present=True)

    detail = service.training_session_detail_view(db_session, training_session)
    assert detail["participants"][0]["present"] is True


def test_training_session_detail_view_reports_presence(db_session, actor, profile):
    """Un jeune non encore pointé reste `None` — pas `False` (FR-002)."""
    training_session = service.create_training_session(db_session, actor, date=date(2026, 9, 20))
    service.add_participant(db_session, actor, training_session, profile_id=profile.id)

    detail = service.training_session_detail_view(db_session, training_session)

    assert detail["participants"][0]["present"] is None


def test_set_presence_updates_status(db_session, actor, profile):
    training_session = service.create_training_session(db_session, actor, date=date(2026, 9, 20))
    service.add_participant(db_session, actor, training_session, profile_id=profile.id)

    service.set_presence(db_session, actor, training_session, profile_id=profile.id, present=True)

    detail = service.training_session_detail_view(db_session, training_session)
    assert detail["participants"][0]["present"] is True


def test_set_presence_raises_when_profile_not_registered(db_session, actor, profile):
    training_session = service.create_training_session(db_session, actor, date=date(2026, 9, 20))

    with pytest.raises(NotFoundError):
        service.set_presence(db_session, actor, training_session, profile_id=profile.id, present=True)


def test_update_entrainement_can_change_note(db_session, actor):
    training_session = service.create_training_session(db_session, actor, date=date(2026, 9, 20))

    service.update_training_session(db_session, actor, training_session, note="Bassin partagé.")

    assert training_session.note == "Bassin partagé."
