"""API self-service du formulaire public de déclaration de bénévolat (#778) —
contracts/volunteer-action-public-api.md.

`session_de_saisie` (autouse, `tests/test_api/conftest.py`) ouvre déjà une
session sur `client` — le router self-service ne vérifie aucun pouvoir RBAC.
"""
from app.core.season import current_season
from app.repositories import athlete_repository, volunteer_action_repository

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


def test_sans_session_rend_401(client, db_session):
    athlete = _athlete(db_session)
    client.cookies.clear()

    reponse = client.post(
        _URL, json={"athlete_id": athlete.id, "title": "Un titre", "description": "Une description."}
    )

    assert reponse.status_code == 401
