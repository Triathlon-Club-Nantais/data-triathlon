from datetime import date, time

from app.repositories import training_session_repository


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
