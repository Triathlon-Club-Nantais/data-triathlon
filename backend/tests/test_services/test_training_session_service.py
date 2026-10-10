from datetime import date, timedelta

import pytest

from app.core.exceptions import NotFoundError
from app.models.organisation import Organisation
from app.repositories import profile_repository, user_repository
from app.services import training_group_service
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
    # Séances (et leurs groupes visés, #1291, en `selectinload`), puis comptes agrégés.
    assert len(requetes) == 3, requetes


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


# --- Inscription d'office par groupe (#1291, US2) -----------------------------

UPCOMING = date.today() + timedelta(days=7)


def _young(db_session, organisation, last_name, **fields):
    young = profile_repository.create(
        db_session, organisation_id=organisation.id, first_name="Jeune", last_name=last_name
    )
    for field, value in fields.items():
        setattr(young, field, value)
    db_session.flush()
    return young


def _group(db_session, actor, name, *members):
    group = training_group_service.create_group(db_session, actor, name=name)
    for member in members:
        training_group_service.add_member(db_session, actor, group, profile_id=member.id)
    return group


def _enrolled(db_session, training_session):
    detail = service.training_session_detail_view(db_session, training_session)
    return {p["profile_id"]: p["added_manually"] for p in detail["participants"]}


def test_a_session_targeting_a_group_enrols_its_members(db_session, actor, organisation):
    trio = [_young(db_session, organisation, name) for name in ("A", "B", "C")]
    group = _group(db_session, actor, "Benjamins", *trio)

    training_session = service.create_training_session(db_session, actor, date=UPCOMING, group_ids=[group.id])

    assert _enrolled(db_session, training_session) == {young.id: False for young in trio}


def test_a_member_shared_by_two_groups_is_enrolled_once(db_session, actor, organisation):
    shared = _young(db_session, organisation, "Commun")
    alpha = _group(db_session, actor, "Alpha", shared)
    beta = _group(db_session, actor, "Beta", shared)

    training_session = service.create_training_session(
        db_session, actor, date=UPCOMING, group_ids=[alpha.id, beta.id]
    )

    assert _enrolled(db_session, training_session) == {shared.id: False}


def test_an_ended_membership_is_not_enrolled(db_session, actor, organisation):
    gone = _young(db_session, organisation, "Parti", membership_ended_on=UPCOMING - timedelta(days=1))
    group = _group(db_session, actor, "Benjamins", gone)

    training_session = service.create_training_session(db_session, actor, date=UPCOMING, group_ids=[group.id])

    assert _enrolled(db_session, training_session) == {}


def test_an_unknown_group_is_a_404(db_session, actor):
    with pytest.raises(NotFoundError):
        service.create_training_session(db_session, actor, date=UPCOMING, group_ids=[999])


def test_group_changes_follow_upcoming_sessions(db_session, actor, organisation):
    first = _young(db_session, organisation, "Premier")
    late = _young(db_session, organisation, "Tardif")
    group = _group(db_session, actor, "Benjamins", first)
    training_session = service.create_training_session(db_session, actor, date=UPCOMING, group_ids=[group.id])

    training_group_service.add_member(db_session, actor, group, profile_id=late.id)
    assert set(_enrolled(db_session, training_session)) == {first.id, late.id}

    training_group_service.remove_member(db_session, actor, group, profile_id=first.id)
    assert set(_enrolled(db_session, training_session)) == {late.id}


def test_a_manual_or_other_group_enrolment_survives_a_removal(db_session, actor, organisation):
    manual = _young(db_session, organisation, "Manuel")
    shared = _young(db_session, organisation, "Commun")
    alpha = _group(db_session, actor, "Alpha", manual, shared)
    beta = _group(db_session, actor, "Beta", shared)
    training_session = service.create_training_session(
        db_session, actor, date=UPCOMING, group_ids=[alpha.id, beta.id]
    )
    service.add_participant(db_session, actor, training_session, profile_id=manual.id)

    training_group_service.remove_member(db_session, actor, alpha, profile_id=manual.id)
    training_group_service.remove_member(db_session, actor, alpha, profile_id=shared.id)

    assert _enrolled(db_session, training_session) == {manual.id: True, shared.id: False}


def test_past_or_started_sessions_do_not_follow_the_group(db_session, actor, organisation):
    pointed = _young(db_session, organisation, "Pointé")
    late = _young(db_session, organisation, "Tardif")
    group = _group(db_session, actor, "Benjamins", pointed)
    started = service.create_training_session(db_session, actor, date=UPCOMING, group_ids=[group.id])
    service.set_presence(db_session, actor, started, profile_id=pointed.id, present=True)
    past = service.create_training_session(db_session, actor, date=date.today() - timedelta(days=1))
    service.update_training_session(db_session, actor, past, group_ids=[group.id])

    training_group_service.add_member(db_session, actor, group, profile_id=late.id)
    training_group_service.remove_member(db_session, actor, group, profile_id=pointed.id)

    assert set(_enrolled(db_session, started)) == {pointed.id}
    assert _enrolled(db_session, past) == {}


def test_changing_the_groups_of_a_session_resyncs_it(db_session, actor, organisation):
    alix = _young(db_session, organisation, "Alix")
    zoe = _young(db_session, organisation, "Zoé")
    alpha = _group(db_session, actor, "Alpha", alix)
    beta = _group(db_session, actor, "Beta", zoe)
    training_session = service.create_training_session(db_session, actor, date=UPCOMING, group_ids=[alpha.id])

    service.update_training_session(db_session, actor, training_session, group_ids=[beta.id])

    assert _enrolled(db_session, training_session) == {zoe.id: False}
    assert [group.id for group in training_session.groups] == [beta.id]


def test_deleting_a_group_keeps_its_members_enrolled_for_good(db_session, actor, organisation):
    alix = _young(db_session, organisation, "Alix")
    zoe = _young(db_session, organisation, "Zoé")
    alpha = _group(db_session, actor, "Alpha", alix)
    beta = _group(db_session, actor, "Beta", zoe)
    training_session = service.create_training_session(
        db_session, actor, date=UPCOMING, group_ids=[alpha.id, beta.id]
    )

    training_group_service.delete_group(db_session, actor, alpha)
    training_group_service.remove_member(db_session, actor, beta, profile_id=zoe.id)

    assert _enrolled(db_session, training_session) == {alix.id: True}
