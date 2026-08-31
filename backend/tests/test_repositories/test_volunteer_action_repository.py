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


def test_exists_for_athlete_season_faux_pour_une_declaration_en_attente(db_session):
    """#779 FR-008 : une simple existence ne suffit plus — il faut « validée »
    (cf. `test_exists_for_athlete_season_vrai_des_une_ligne_validee`)."""
    auteur = _auteur(db_session)
    athlete = _athlete(db_session)
    volunteer_action_repository.create(
        db_session, athlete_id=athlete.id, season=2025, declared_by_user_id=auteur.id
    )
    db_session.flush()

    assert not volunteer_action_repository.exists_for_athlete_season(
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


def test_list_pending_ne_rend_que_les_lignes_en_attente(db_session):
    auteur = _auteur(db_session)
    athlete = _athlete(db_session)
    en_attente = volunteer_action_repository.create_pending(
        db_session, athlete_id=athlete.id, season=2025, declared_by_user_id=auteur.id,
        title="A", description="B",
    )
    validee = volunteer_action_repository.create_pending(
        db_session, athlete_id=athlete.id, season=2025, declared_by_user_id=auteur.id,
        title="C", description="D",
    )
    volunteer_action_repository.set_status(db_session, validee.id, "validee")
    db_session.flush()

    en_cours = volunteer_action_repository.list_pending(db_session)

    assert [a.id for a in en_cours] == [en_attente.id]


def test_get_rend_none_sur_id_inconnu(db_session):
    assert volunteer_action_repository.get(db_session, 999999) is None


def test_set_status_change_et_relit_le_statut(db_session):
    auteur = _auteur(db_session)
    athlete = _athlete(db_session)
    action = volunteer_action_repository.create_pending(
        db_session, athlete_id=athlete.id, season=2025, declared_by_user_id=auteur.id,
        title="A", description="B",
    )
    db_session.flush()

    mise_a_jour = volunteer_action_repository.set_status(db_session, action.id, "validee")

    assert mise_a_jour.status == "validee"
    assert volunteer_action_repository.get(db_session, action.id).status == "validee"


def test_exists_for_athlete_season_ignore_en_attente_et_refusee(db_session):
    auteur = _auteur(db_session)
    athlete = _athlete(db_session)
    volunteer_action_repository.create_pending(
        db_session, athlete_id=athlete.id, season=2025, declared_by_user_id=auteur.id,
        title="A", description="B",
    )
    refusee = volunteer_action_repository.create_pending(
        db_session, athlete_id=athlete.id, season=2025, declared_by_user_id=auteur.id,
        title="C", description="D",
    )
    volunteer_action_repository.set_status(db_session, refusee.id, "refusee")
    db_session.flush()

    assert not volunteer_action_repository.exists_for_athlete_season(
        db_session, athlete_id=athlete.id, season=2025
    )


def test_exists_for_athlete_season_vrai_des_une_ligne_validee(db_session):
    auteur = _auteur(db_session)
    athlete = _athlete(db_session)
    action = volunteer_action_repository.create_pending(
        db_session, athlete_id=athlete.id, season=2025, declared_by_user_id=auteur.id,
        title="A", description="B",
    )
    volunteer_action_repository.set_status(db_session, action.id, "validee")
    db_session.flush()

    assert volunteer_action_repository.exists_for_athlete_season(
        db_session, athlete_id=athlete.id, season=2025
    )


def test_list_validated_for_athlete_ne_rend_que_les_lignes_validees(db_session):
    auteur = _auteur(db_session)
    athlete = _athlete(db_session)
    autre_athlete = _athlete(db_session, nom="MARTIN")

    en_attente = volunteer_action_repository.create_pending(
        db_session, athlete_id=athlete.id, season=2024, declared_by_user_id=auteur.id,
        title="A", description="B",
    )
    refusee = volunteer_action_repository.create_pending(
        db_session, athlete_id=athlete.id, season=2024, declared_by_user_id=auteur.id,
        title="C", description="D",
    )
    volunteer_action_repository.set_status(db_session, refusee.id, "refusee")
    validee_ancienne = volunteer_action_repository.create_pending(
        db_session, athlete_id=athlete.id, season=2024, declared_by_user_id=auteur.id,
        title="E", description="F",
    )
    volunteer_action_repository.set_status(db_session, validee_ancienne.id, "validee")
    validee_recente = volunteer_action_repository.create_pending(
        db_session, athlete_id=athlete.id, season=2025, declared_by_user_id=auteur.id,
        title="G", description="H",
    )
    volunteer_action_repository.set_status(db_session, validee_recente.id, "validee")
    validee_autre_athlete = volunteer_action_repository.create_pending(
        db_session, athlete_id=autre_athlete.id, season=2025, declared_by_user_id=auteur.id,
        title="I", description="J",
    )
    volunteer_action_repository.set_status(db_session, validee_autre_athlete.id, "validee")
    db_session.flush()

    resultat = volunteer_action_repository.list_validated_for_athlete(db_session, athlete_id=athlete.id)

    assert [a.id for a in resultat] == [validee_recente.id, validee_ancienne.id]
    assert en_attente.id not in [a.id for a in resultat]
