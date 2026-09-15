from datetime import date, time

from app.repositories import entrainement_repository


def _create(db_session, **kwargs):
    return entrainement_repository.create(db_session, **kwargs)


def test_list_all_sorts_by_date_then_heure(db_session):
    matin = _create(db_session, date=date(2026, 9, 20), heure_debut=time(9, 0))
    sans_heure = _create(db_session, date=date(2026, 9, 20), heure_debut=None)
    soir = _create(db_session, date=date(2026, 9, 20), heure_debut=time(18, 0))
    plus_tard = _create(db_session, date=date(2026, 9, 27), heure_debut=time(9, 0))

    resultat = entrainement_repository.list_all(db_session)

    # Une séance sans heure sort en fin de sa date, jamais en tête.
    assert [e.id for e in resultat] == [matin.id, soir.id, sans_heure.id, plus_tard.id]


def test_participant_count_is_exact(db_session):
    entrainement = _create(db_session, date=date(2026, 9, 20))
    assert entrainement_repository.participant_count(db_session, entrainement.id) == 0

    entrainement_repository.add_participant(db_session, entrainement_id=entrainement.id, jeune_id=1)
    entrainement_repository.add_participant(db_session, entrainement_id=entrainement.id, jeune_id=2)

    assert entrainement_repository.participant_count(db_session, entrainement.id) == 2


def test_list_participants_is_empty_by_default(db_session):
    entrainement = _create(db_session, date=date(2026, 9, 20))
    assert entrainement_repository.list_participants(db_session, entrainement.id) == []


def test_update_only_writes_provided_fields(db_session):
    entrainement = _create(
        db_session, date=date(2026, 9, 20), lieu="Base nautique", type_seance="Natation"
    )

    entrainement_repository.update(db_session, entrainement, date=date(2026, 9, 21))

    assert entrainement.date == date(2026, 9, 21)
    # Champs non soumis au PATCH : inchangés.
    assert entrainement.lieu == "Base nautique"
    assert entrainement.type_seance == "Natation"


def test_update_can_clear_an_optional_field(db_session):
    entrainement = _create(db_session, date=date(2026, 9, 20), lieu="Base nautique")

    entrainement_repository.update(db_session, entrainement, lieu=None)

    assert entrainement.lieu is None


def test_add_participant_is_idempotent(db_session):
    entrainement = _create(db_session, date=date(2026, 9, 20))

    _, cree_1 = entrainement_repository.add_participant(
        db_session, entrainement_id=entrainement.id, jeune_id=42
    )
    _, cree_2 = entrainement_repository.add_participant(
        db_session, entrainement_id=entrainement.id, jeune_id=42
    )

    assert cree_1 is True
    assert cree_2 is False
    assert entrainement_repository.participant_count(db_session, entrainement.id) == 1


def test_add_participant_scopes_to_its_own_entrainement(db_session):
    e1 = _create(db_session, date=date(2026, 9, 20))
    e2 = _create(db_session, date=date(2026, 9, 27))

    entrainement_repository.add_participant(db_session, entrainement_id=e1.id, jeune_id=42)

    assert [p.jeune_id for p in entrainement_repository.list_participants(db_session, e1.id)] == [42]
    assert entrainement_repository.list_participants(db_session, e2.id) == []


def test_remove_participant_returns_false_when_not_registered(db_session):
    entrainement = _create(db_session, date=date(2026, 9, 20))
    assert (
        entrainement_repository.remove_participant(
            db_session, entrainement_id=entrainement.id, jeune_id=99
        )
        is False
    )


def test_remove_participant_removes_only_this_entrainement(db_session):
    entrainement = _create(db_session, date=date(2026, 9, 20))
    entrainement_repository.add_participant(db_session, entrainement_id=entrainement.id, jeune_id=42)

    supprime = entrainement_repository.remove_participant(
        db_session, entrainement_id=entrainement.id, jeune_id=42
    )

    assert supprime is True
    assert entrainement_repository.list_participants(db_session, entrainement.id) == []


def test_add_participant_defaults_to_not_yet_pointed(db_session):
    entrainement = _create(db_session, date=date(2026, 9, 20))

    participant, _ = entrainement_repository.add_participant(
        db_session, entrainement_id=entrainement.id, jeune_id=42
    )

    assert participant.present is None


def test_add_participant_can_be_pointed_present_in_the_same_call(db_session):
    entrainement = _create(db_session, date=date(2026, 9, 20))

    participant, cree = entrainement_repository.add_participant(
        db_session, entrainement_id=entrainement.id, jeune_id=42, present=True
    )

    assert cree is True
    assert participant.present is True


def test_set_presence_updates_the_existing_registration(db_session):
    entrainement = _create(db_session, date=date(2026, 9, 20))
    entrainement_repository.add_participant(db_session, entrainement_id=entrainement.id, jeune_id=42)

    resultat = entrainement_repository.set_presence(
        db_session, entrainement_id=entrainement.id, jeune_id=42, present=True
    )

    assert resultat.present is True
    # Seul le dernier statut fait foi (FR-005) : pas d'historique.
    resultat_2 = entrainement_repository.set_presence(
        db_session, entrainement_id=entrainement.id, jeune_id=42, present=False
    )
    assert resultat_2.present is False


def test_set_presence_returns_none_when_not_registered(db_session):
    entrainement = _create(db_session, date=date(2026, 9, 20))

    resultat = entrainement_repository.set_presence(
        db_session, entrainement_id=entrainement.id, jeune_id=99, present=True
    )

    assert resultat is None


def test_update_can_change_the_seance_note(db_session):
    entrainement = _create(db_session, date=date(2026, 9, 20))
    assert entrainement.note == ""

    entrainement_repository.update(db_session, entrainement, note="Bassin partagé.")

    assert entrainement.note == "Bassin partagé."


def test_update_without_note_does_not_erase_it(db_session):
    entrainement = _create(db_session, date=date(2026, 9, 20))
    entrainement_repository.update(db_session, entrainement, note="Bassin partagé.")

    entrainement_repository.update(db_session, entrainement, lieu="Base nautique")

    assert entrainement.note == "Bassin partagé."
