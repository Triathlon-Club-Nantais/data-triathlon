"""Le journal des actions de bénévolat déclarées (#709, research.md D4).

Plusieurs déclarations peuvent coexister pour le même `(athlete_id, season)` —
le barème de validation de saison (FR-012) est satisfait dès qu'il en existe
au moins une.
"""
from app.repositories import athlete_repository, user_repository, volunteer_action_repository


def _auteur(db_session, email="benevole@exemple.fr"):
    user = user_repository.create(db_session, email=email)
    db_session.flush()
    return user


def _athlete(db_session, nom="DUPONT"):
    athlete = athlete_repository.get_or_create(db_session, nom=nom, prenom="Jean", club="TCN")
    db_session.flush()
    return athlete


def test_create_consigne_les_quatre_champs_du_contrat(db_session):
    auteur = _auteur(db_session)
    athlete = _athlete(db_session)

    action = volunteer_action_repository.create(
        db_session, athlete_id=athlete.id, season=2025, declared_by_user_id=auteur.id
    )
    db_session.flush()

    assert action.athlete_id == athlete.id
    assert action.season == 2025
    assert action.declared_by_user_id == auteur.id
    assert action.created_at is not None


def test_create_autorise_plusieurs_declarations_pour_le_meme_athlete_et_la_meme_saison(db_session):
    """research.md D4 — journal, pas un indicateur unique."""
    auteur = _auteur(db_session)
    athlete = _athlete(db_session)

    volunteer_action_repository.create(
        db_session, athlete_id=athlete.id, season=2025, declared_by_user_id=auteur.id
    )
    volunteer_action_repository.create(
        db_session, athlete_id=athlete.id, season=2025, declared_by_user_id=auteur.id
    )
    db_session.flush()

    actions = volunteer_action_repository.list_for_athlete_season(
        db_session, athlete_id=athlete.id, season=2025
    )
    assert len(actions) == 2


def test_exists_for_athlete_season_faux_sans_declaration(db_session):
    athlete = _athlete(db_session)

    assert not volunteer_action_repository.exists_for_athlete_season(
        db_session, athlete_id=athlete.id, season=2025
    )


def test_exists_for_athlete_season_vrai_des_une_declaration(db_session):
    auteur = _auteur(db_session)
    athlete = _athlete(db_session)
    volunteer_action_repository.create(
        db_session, athlete_id=athlete.id, season=2025, declared_by_user_id=auteur.id
    )
    db_session.flush()

    assert volunteer_action_repository.exists_for_athlete_season(
        db_session, athlete_id=athlete.id, season=2025
    )


def test_exists_for_athlete_season_ne_traverse_pas_les_saisons(db_session):
    auteur = _auteur(db_session)
    athlete = _athlete(db_session)
    volunteer_action_repository.create(
        db_session, athlete_id=athlete.id, season=2024, declared_by_user_id=auteur.id
    )
    db_session.flush()

    assert not volunteer_action_repository.exists_for_athlete_season(
        db_session, athlete_id=athlete.id, season=2025
    )


def test_create_laisse_title_description_a_none_et_status_au_defaut(db_session):
    """Chemin admin existant (#778 FR-008) : aucune régression sur `create()`."""
    auteur = _auteur(db_session)
    athlete = _athlete(db_session)

    action = volunteer_action_repository.create(
        db_session, athlete_id=athlete.id, season=2025, declared_by_user_id=auteur.id
    )
    db_session.flush()

    assert action.title is None
    assert action.description is None
    assert action.status == "en_attente"


def test_create_pending_consigne_titre_description_et_statut_en_attente(db_session):
    auteur = _auteur(db_session)
    athlete = _athlete(db_session)

    action = volunteer_action_repository.create_pending(
        db_session,
        athlete_id=athlete.id,
        season=2025,
        declared_by_user_id=auteur.id,
        title="Ravitaillement",
        description="Tenue du poste de ravitaillement km 15.",
    )
    db_session.flush()

    assert action.athlete_id == athlete.id
    assert action.season == 2025
    assert action.declared_by_user_id == auteur.id
    assert action.title == "Ravitaillement"
    assert action.description == "Tenue du poste de ravitaillement km 15."
    assert action.status == "en_attente"
