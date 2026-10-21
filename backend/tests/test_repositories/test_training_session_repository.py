from datetime import date, time

import pytest

from app.models.organisation import Organisation
from app.models.personal_profile import PersonalProfile
from app.repositories import training_group_repository, training_session_repository


@pytest.fixture(autouse=True)
def _profils(db_session):
    """Les profils que les tests inscrivent : PostgreSQL vérifie la clé étrangère
    que SQLite laisse passer (#947)."""
    club = Organisation(slug="tcn", name="Triathlon Club Nantais")
    db_session.add(club)
    db_session.flush()
    for profile_id in (1, 2, 42):
        db_session.add(PersonalProfile(
            id=profile_id, organisation_id=club.id, first_name="Jeune", last_name=f"N{profile_id}",
        ))
    db_session.flush()


def _create(db_session, **kwargs):
    return training_session_repository.create(db_session, **kwargs)


def test_list_all_sorts_by_date_then_heure(db_session):
    matin = _create(db_session, date=date(2026, 9, 20), start_time=time(9, 0))
    sans_heure = _create(db_session, date=date(2026, 9, 20), start_time=None)
    soir = _create(db_session, date=date(2026, 9, 20), start_time=time(18, 0))
    plus_tard = _create(db_session, date=date(2026, 9, 27), start_time=time(9, 0))

    resultat = training_session_repository.list_all(db_session)

    # Une séance sans heure sort en fin de sa date, jamais en tête.
    assert [e.id for e in resultat] == [matin.id, soir.id, sans_heure.id, plus_tard.id]


def _requetes(db_session, appel):
    """Compte les requêtes SQL émises par `appel()`."""
    from sqlalchemy import event

    requetes = []

    def _mouchard(conn, cursor, statement, *reste):
        requetes.append(statement)

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", _mouchard)
    try:
        appel()
    finally:
        event.remove(engine, "before_cursor_execute", _mouchard)
    return requetes


def test_count_participants_by_training_session_is_exact(db_session):
    vide = _create(db_session, date=date(2026, 9, 20))
    pleine = _create(db_session, date=date(2026, 9, 21))
    training_session_repository.add_participant(db_session, training_session_id=pleine.id, profile_id=1)
    training_session_repository.add_participant(db_session, training_session_id=pleine.id, profile_id=2)

    comptes = training_session_repository.count_participants_by_training_session(
        db_session, [vide.id, pleine.id]
    )

    # Une séance sans inscrit est absente du résultat.
    assert comptes == {pleine.id: 2}


@pytest.mark.own_database
def test_count_participants_by_training_session_is_a_single_query(db_session):
    seances = [_create(db_session, date=date(2026, 9, 20 + i)) for i in range(3)]
    for seance in seances:
        training_session_repository.add_participant(db_session, training_session_id=seance.id, profile_id=1)
    ids = [seance.id for seance in seances]
    db_session.commit()

    requetes = _requetes(
        db_session,
        lambda: training_session_repository.count_participants_by_training_session(db_session, ids),
    )

    assert len(requetes) == 1, requetes


def test_count_participants_without_id_does_not_query(db_session):
    requetes = _requetes(
        db_session,
        lambda: training_session_repository.count_participants_by_training_session(db_session, []),
    )

    assert requetes == []


def test_list_participants_is_empty_by_default(db_session):
    training_session = _create(db_session, date=date(2026, 9, 20))
    assert training_session_repository.list_participants(db_session, training_session.id) == []


def test_update_only_writes_provided_fields(db_session):
    training_session = _create(
        db_session, date=date(2026, 9, 20), location="Base nautique", session_type="Natation"
    )

    training_session_repository.update(db_session, training_session, date=date(2026, 9, 21))

    assert training_session.date == date(2026, 9, 21)
    # Champs non soumis au PATCH : inchangés.
    assert training_session.location == "Base nautique"
    assert training_session.session_type == "Natation"


def test_update_can_clear_an_optional_field(db_session):
    training_session = _create(db_session, date=date(2026, 9, 20), location="Base nautique")

    training_session_repository.update(db_session, training_session, location=None)

    assert training_session.location is None


def test_add_participant_is_idempotent(db_session):
    training_session = _create(db_session, date=date(2026, 9, 20))

    _, cree_1 = training_session_repository.add_participant(
        db_session, training_session_id=training_session.id, profile_id=42
    )
    _, cree_2 = training_session_repository.add_participant(
        db_session, training_session_id=training_session.id, profile_id=42
    )

    assert cree_1 is True
    assert cree_2 is False
    assert len(training_session_repository.list_participants(db_session, training_session.id)) == 1


def test_add_participant_scopes_to_its_own_entrainement(db_session):
    e1 = _create(db_session, date=date(2026, 9, 20))
    e2 = _create(db_session, date=date(2026, 9, 27))

    training_session_repository.add_participant(db_session, training_session_id=e1.id, profile_id=42)

    assert [p.profile_id for p in training_session_repository.list_participants(db_session, e1.id)] == [42]
    assert training_session_repository.list_participants(db_session, e2.id) == []


def test_remove_participant_returns_false_when_not_registered(db_session):
    training_session = _create(db_session, date=date(2026, 9, 20))
    assert (
        training_session_repository.remove_participant(
            db_session, training_session_id=training_session.id, profile_id=99
        )
        is False
    )


def test_remove_participant_removes_only_this_entrainement(db_session):
    training_session = _create(db_session, date=date(2026, 9, 20))
    training_session_repository.add_participant(db_session, training_session_id=training_session.id, profile_id=42)

    supprime = training_session_repository.remove_participant(
        db_session, training_session_id=training_session.id, profile_id=42
    )

    assert supprime is True
    assert training_session_repository.list_participants(db_session, training_session.id) == []


def test_add_participant_defaults_to_not_yet_pointed(db_session):
    training_session = _create(db_session, date=date(2026, 9, 20))

    participant, _ = training_session_repository.add_participant(
        db_session, training_session_id=training_session.id, profile_id=42
    )

    assert participant.present is None


def test_add_participant_can_be_pointed_present_in_the_same_call(db_session):
    training_session = _create(db_session, date=date(2026, 9, 20))

    participant, cree = training_session_repository.add_participant(
        db_session, training_session_id=training_session.id, profile_id=42, present=True
    )

    assert cree is True
    assert participant.present is True


def test_set_presence_updates_the_existing_registration(db_session):
    training_session = _create(db_session, date=date(2026, 9, 20))
    training_session_repository.add_participant(db_session, training_session_id=training_session.id, profile_id=42)

    resultat = training_session_repository.set_presence(
        db_session, training_session_id=training_session.id, profile_id=42, present=True
    )

    assert resultat.present is True
    # Seul le dernier statut fait foi (FR-005) : pas d'historique.
    resultat_2 = training_session_repository.set_presence(
        db_session, training_session_id=training_session.id, profile_id=42, present=False
    )
    assert resultat_2.present is False


def test_set_presence_returns_none_when_not_registered(db_session):
    training_session = _create(db_session, date=date(2026, 9, 20))

    resultat = training_session_repository.set_presence(
        db_session, training_session_id=training_session.id, profile_id=99, present=True
    )

    assert resultat is None


def test_update_can_change_the_seance_note(db_session):
    training_session = _create(db_session, date=date(2026, 9, 20))
    assert training_session.note == ""

    training_session_repository.update(db_session, training_session, note="Bassin partagé.")

    assert training_session.note == "Bassin partagé."


def test_update_without_note_does_not_erase_it(db_session):
    training_session = _create(db_session, date=date(2026, 9, 20))
    training_session_repository.update(db_session, training_session, note="Bassin partagé.")

    training_session_repository.update(db_session, training_session, location="Base nautique")

    assert training_session.note == "Bassin partagé."


SEASON = {"date_from": date(2025, 11, 1), "date_to": date(2026, 10, 31)}


def _pointed(db_session, day, presences, *, start_time=None, groups=()):
    session = _create(db_session, date=day, start_time=start_time)
    if groups:
        training_session_repository.set_groups(db_session, session, list(groups))
    for profile_id, present in presences.items():
        training_session_repository.add_participant(
            db_session, training_session_id=session.id, profile_id=profile_id, present=present,
        )
    return session


def _group(db_session, name):
    club = db_session.query(Organisation).filter_by(slug="tcn").one()
    return training_group_repository.create(db_session, organisation_id=club.id, name=name)


def test_presence_history_keeps_pointed_sessions_of_the_season_latest_first(db_session):
    _pointed(db_session, date(2025, 10, 31), {1: True})
    _pointed(db_session, date(2025, 11, 1), {1: True})
    _pointed(db_session, date(2026, 3, 4), {1: None})
    _pointed(db_session, date(2026, 3, 11), {1: True}, start_time=time(18, 0))
    _pointed(db_session, date(2026, 3, 11), {1: False})
    _pointed(db_session, date(2026, 11, 1), {1: True})

    assert training_session_repository.presence_history_of_profile(db_session, 1, **SEASON) == [
        False, True, True,
    ]


def test_presence_history_ignores_a_deleted_session(db_session):
    session = _pointed(db_session, date(2026, 3, 4), {1: False})
    training_session_repository.delete_training_session(db_session, session)

    assert training_session_repository.presence_history_of_profile(db_session, 1, **SEASON) == []


def test_attendance_by_group_follows_the_session_group_across_a_group_change(db_session):
    group_a, group_b = _group(db_session, "A"), _group(db_session, "B")
    _group(db_session, "C")
    _pointed(db_session, date(2026, 1, 7), {1: True, 2: None}, groups=[group_a])
    _pointed(db_session, date(2026, 2, 4), {1: False}, groups=[group_b])

    assert training_session_repository.attendance_by_group(db_session, **SEASON) == {
        group_a.id: (1, 1), group_b.id: (0, 1),
    }


def test_attendance_by_group_counts_a_multi_group_session_for_each_group(db_session):
    group_a, group_b = _group(db_session, "A"), _group(db_session, "B")
    _pointed(db_session, date(2026, 1, 7), {1: True, 2: False}, groups=[group_a, group_b])

    assert training_session_repository.attendance_by_group(db_session, **SEASON) == {
        group_a.id: (1, 2), group_b.id: (1, 2),
    }


def test_attendance_by_group_ignores_sessions_outside_the_season(db_session):
    group_a = _group(db_session, "A")
    _pointed(db_session, date(2025, 10, 31), {1: True}, groups=[group_a])

    assert training_session_repository.attendance_by_group(db_session, **SEASON) == {}
