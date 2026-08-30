"""Le statut de validation de saison d'un athlète (#709, research.md D5).

L'existence de la ligne porte le statut : valider crée, dévalider supprime.
Unique par `(athlete_id, season)`.
"""
from app.repositories import athlete_repository, season_validation_repository, user_repository


def _auteur(db_session, email="admin@exemple.fr"):
    user = user_repository.create(db_session, email=email)
    db_session.flush()
    return user


def _athlete(db_session, nom="DUPONT"):
    athlete = athlete_repository.get_or_create(db_session, nom=nom, prenom="Jean", club="TCN")
    db_session.flush()
    return athlete


def test_create_consigne_les_trois_champs_du_contrat(db_session):
    auteur = _auteur(db_session)
    athlete = _athlete(db_session)

    validation = season_validation_repository.create(
        db_session, athlete_id=athlete.id, season=2025, validated_by_user_id=auteur.id
    )
    db_session.flush()

    assert validation.athlete_id == athlete.id
    assert validation.season == 2025
    assert validation.validated_by_user_id == auteur.id
    assert validation.validated_at is not None


def test_get_for_athlete_season_rend_none_sans_validation(db_session):
    athlete = _athlete(db_session)

    assert season_validation_repository.get_for_athlete_season(
        db_session, athlete_id=athlete.id, season=2025
    ) is None


def test_get_for_athlete_season_rend_la_ligne_apres_validation(db_session):
    auteur = _auteur(db_session)
    athlete = _athlete(db_session)
    season_validation_repository.create(
        db_session, athlete_id=athlete.id, season=2025, validated_by_user_id=auteur.id
    )
    db_session.flush()

    validation = season_validation_repository.get_for_athlete_season(
        db_session, athlete_id=athlete.id, season=2025
    )
    assert validation is not None
    assert validation.season == 2025


def test_get_for_athlete_season_ne_traverse_pas_les_saisons(db_session):
    auteur = _auteur(db_session)
    athlete = _athlete(db_session)
    season_validation_repository.create(
        db_session, athlete_id=athlete.id, season=2024, validated_by_user_id=auteur.id
    )
    db_session.flush()

    assert season_validation_repository.get_for_athlete_season(
        db_session, athlete_id=athlete.id, season=2025
    ) is None


def test_delete_retire_la_ligne(db_session):
    auteur = _auteur(db_session)
    athlete = _athlete(db_session)
    validation = season_validation_repository.create(
        db_session, athlete_id=athlete.id, season=2025, validated_by_user_id=auteur.id
    )
    db_session.flush()

    season_validation_repository.delete(db_session, validation)
    db_session.flush()

    assert season_validation_repository.get_for_athlete_season(
        db_session, athlete_id=athlete.id, season=2025
    ) is None


def test_map_by_athlete_ne_rend_que_les_athletes_demandes(db_session):
    """Lecture en masse pour `list_with_season_participation_count` (#709)."""
    auteur = _auteur(db_session)
    valide = _athlete(db_session, "VALIDE")
    non_valide = _athlete(db_session, "NONVALIDE")
    season_validation_repository.create(
        db_session, athlete_id=valide.id, season=2025, validated_by_user_id=auteur.id
    )
    db_session.flush()

    carte = season_validation_repository.map_by_athlete(
        db_session, athlete_ids=[valide.id, non_valide.id], season=2025
    )

    assert carte == {valide.id: True}
