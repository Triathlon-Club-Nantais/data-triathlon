"""API self-service du formulaire public de déclaration de bénévolat (#778) —
contracts/volunteer-action-public-api.md.

`session_de_saisie` (autouse, `tests/test_api/conftest.py`) ouvre déjà une
session sur `client` — le router self-service ne vérifie aucun pouvoir RBAC.
"""
from app.core.season import current_season
from app.repositories import athlete_repository, user_repository, volunteer_action_repository

_URL = "/api/v1/volunteer-actions"


def _athlete(db_session, nom="DUPONT"):
    athlete = athlete_repository.get_or_create(db_session, nom=nom, prenom="Jean", club="TCN")
    db_session.flush()
    db_session.commit()
    return athlete


def test_creer_une_declaration_pour_lathlete_choisi(client, db_session):
    athlete = _athlete(db_session)

    reponse = client.post(
        _URL,
        json={"athlete_id": athlete.id, "title": "Ravitaillement", "description": "Poste eau km 15."},
    )

    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["athlete_id"] == athlete.id
    assert corps["status"] == "en_attente"
    assert corps["title"] == "Ravitaillement"
    # #809 FR-005 — un appelant connecté via SSO reste tracé.
    auteur = user_repository.find_by_email(db_session, "saisie@exemple.fr")[0]
    assert corps["declared_by_user_id"] == auteur.id


def test_titre_vide_rend_422_et_ne_persiste_rien(client, db_session):
    athlete = _athlete(db_session)

    reponse = client.post(
        _URL, json={"athlete_id": athlete.id, "title": "", "description": "Poste eau km 15."}
    )

    assert reponse.status_code == 422
    assert volunteer_action_repository.list_for_athlete_season(
        db_session, athlete_id=athlete.id, season=current_season()
    ) == []


def test_description_vide_rend_422(client, db_session):
    athlete = _athlete(db_session)

    reponse = client.post(_URL, json={"athlete_id": athlete.id, "title": "Un titre", "description": ""})

    assert reponse.status_code == 422


def test_titre_trop_long_rend_422(client, db_session):
    athlete = _athlete(db_session)

    reponse = client.post(
        _URL, json={"athlete_id": athlete.id, "title": "x" * 201, "description": "Poste eau km 15."}
    )

    assert reponse.status_code == 422


def test_description_trop_longue_rend_422(client, db_session):
    athlete = _athlete(db_session)

    reponse = client.post(
        _URL, json={"athlete_id": athlete.id, "title": "Un titre", "description": "x" * 10_001}
    )

    assert reponse.status_code == 422


def test_athlete_inconnu_rend_404(client):
    reponse = client.post(
        _URL, json={"athlete_id": 999999, "title": "Un titre", "description": "Une description."}
    )

    assert reponse.status_code == 404


def test_sans_session_rend_201_et_sans_auteur(client, db_session):
    """#809 — le mot de passe partagé du site (neutralisé pour ce client par
    `require_site_access`, cf. `tests/conftest.py`) suffit désormais ; la
    session SSO individuelle n'est plus exigée."""
    athlete = _athlete(db_session)
    client.cookies.clear()

    reponse = client.post(
        _URL, json={"athlete_id": athlete.id, "title": "Un titre", "description": "Une description."}
    )

    assert reponse.status_code == 201
    assert reponse.json()["declared_by_user_id"] is None
