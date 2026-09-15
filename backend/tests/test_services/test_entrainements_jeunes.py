from datetime import date

import pytest

from app.core.exceptions import NotFoundError
from app.repositories import user_repository
from app.services.jeunes import entrainements as service


@pytest.fixture
def actor(db_session):
    user = user_repository.create(db_session, email="encadrant@exemple.fr")
    db_session.flush()
    return user


def test_get_entrainement_or_404_raises_on_unknown_id(db_session):
    with pytest.raises(NotFoundError):
        service.get_entrainement_or_404(db_session, 999)


def test_entrainement_view_reports_participant_count(db_session, actor):
    entrainement = service.create_entrainement(db_session, actor, date=date(2026, 9, 20))
    service.add_participant(db_session, actor, entrainement, jeune_id=1)
    service.add_participant(db_session, actor, entrainement, jeune_id=2)

    vue = service.entrainement_view(db_session, entrainement)

    assert vue["participant_count"] == 2
    assert vue["date"] == date(2026, 9, 20)


def test_entrainement_detail_view_lists_participants(db_session, actor):
    entrainement = service.create_entrainement(db_session, actor, date=date(2026, 9, 20))
    service.add_participant(db_session, actor, entrainement, jeune_id=42)

    detail = service.entrainement_detail_view(db_session, entrainement)

    assert [p["jeune_id"] for p in detail["participants"]] == [42]


def test_update_entrainement_only_writes_provided_fields(db_session, actor):
    entrainement = service.create_entrainement(
        db_session, actor, date=date(2026, 9, 20), lieu="Base nautique"
    )

    service.update_entrainement(db_session, actor, entrainement, type_seance="Natation")

    assert entrainement.lieu == "Base nautique"
    assert entrainement.type_seance == "Natation"


def test_add_participant_is_idempotent(db_session, actor):
    entrainement = service.create_entrainement(db_session, actor, date=date(2026, 9, 20))

    service.add_participant(db_session, actor, entrainement, jeune_id=42)
    service.add_participant(db_session, actor, entrainement, jeune_id=42)

    vue = service.entrainement_view(db_session, entrainement)
    assert vue["participant_count"] == 1


def test_remove_participant_is_idempotent(db_session, actor):
    entrainement = service.create_entrainement(db_session, actor, date=date(2026, 9, 20))
    service.add_participant(db_session, actor, entrainement, jeune_id=42)

    service.remove_participant(db_session, actor, entrainement, jeune_id=42)
    service.remove_participant(db_session, actor, entrainement, jeune_id=42)

    vue = service.entrainement_view(db_session, entrainement)
    assert vue["participant_count"] == 0
