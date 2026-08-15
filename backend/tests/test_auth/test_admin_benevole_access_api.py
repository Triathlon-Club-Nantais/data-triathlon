"""Gestion admin du mot de passe partagé bénévoles
(`specs/20260815-173645-admin-mdp-benevoles/contracts/api.md`).

Trois ressources, un seul pouvoir dédié (`benevole_access:manage`), gardé
route par route. L'ordre **401 avant 403** est vérifié, jamais supposé.
"""
from app.core.permissions import P
from app.repositories import admin_action_log_repository, benevole_config_repository

URL = "/api/v1/admin/benevoles/access"
URL_GENERATE = f"{URL}/generate"


# --- GET : état courant (FR-005) ---------------------------------------------


def test_etat_non_configure_avant_tout_reglage(client, ouvrir_session):
    ouvrir_session(P.BENEVOLE_ACCESS_MANAGE)

    reponse = client.get(URL)

    assert reponse.status_code == 200
    assert reponse.json() == {"configured": False, "updated_at": None, "updated_by": None}


def test_etat_configure_apres_un_remplacement(client, ouvrir_session):
    ouvrir_session(P.BENEVOLE_ACCESS_MANAGE, nom="Iris Admin")

    client.put(URL, json={"password": "un-secret-assez-long"})
    reponse = client.get(URL)

    assert reponse.status_code == 200
    charge = reponse.json()
    assert charge["configured"] is True
    assert charge["updated_by"] == "Iris Admin"
    assert charge["updated_at"] is not None
    assert "password" not in charge
    assert "password_hash" not in charge


# --- PUT : remplacement par saisie (US1, FR-001) -----------------------------


def test_remplacement_manuel_permet_une_connexion_benevole(client, ouvrir_session):
    ouvrir_session(P.BENEVOLE_ACCESS_MANAGE)

    reponse = client.put(URL, json={"password": "un-secret-assez-long"})
    assert reponse.status_code == 200

    connexion = client.post(
        "/api/v1/benevoles/session", json={"password": "un-secret-assez-long"}
    )
    assert connexion.status_code == 204


def test_remplacement_invalide_les_sessions_deja_ouvertes(client, ouvrir_session):
    """FR-006, SC-002 (quickstart.md scénario 2)."""
    ouvrir_session(P.BENEVOLE_ACCESS_MANAGE)
    client.put(URL, json={"password": "premier-secret-assez-long"})

    session_benevole = client.post(
        "/api/v1/benevoles/session", json={"password": "premier-secret-assez-long"}
    )
    assert session_benevole.status_code == 204

    client.put(URL, json={"password": "second-secret-assez-long"})

    assert client.get("/api/v1/benevoles/queue").status_code == 401
    ancien = client.post(
        "/api/v1/benevoles/session", json={"password": "premier-secret-assez-long"}
    )
    assert ancien.status_code == 401


def test_remplacement_consigne_l_acteur_sans_secret_dans_le_payload(
    client, ouvrir_session, db_session
):
    acteur = ouvrir_session(P.BENEVOLE_ACCESS_MANAGE)

    client.put(URL, json={"password": "un-secret-assez-long"})

    config = benevole_config_repository.get_config(db_session)
    entrees = admin_action_log_repository.list_for_entity(
        db_session, entity_type="benevole_access_config", entity_id=config.id
    )
    assert len(entrees) == 1
    assert entrees[0].user_id == acteur.id
    assert entrees[0].action == "benevole_access.password_replace"
    assert entrees[0].payload is None


# --- POST .../generate : génération sécurisée (US2, FR-002/FR-003) -----------


def test_generation_rend_un_mot_de_passe_qui_fonctionne(client, ouvrir_session):
    ouvrir_session(P.BENEVOLE_ACCESS_MANAGE)

    reponse = client.post(URL_GENERATE)
    assert reponse.status_code == 200
    charge = reponse.json()
    assert len(charge["password"]) >= 20

    connexion = client.post(
        "/api/v1/benevoles/session", json={"password": charge["password"]}
    )
    assert connexion.status_code == 204


def test_le_mot_de_passe_genere_n_est_plus_jamais_retrouvable(client, ouvrir_session):
    """FR-004, SC-003 — même après génération, `GET` ne le rend jamais."""
    ouvrir_session(P.BENEVOLE_ACCESS_MANAGE)

    client.post(URL_GENERATE)
    etat = client.get(URL).json()

    assert "password" not in etat


def test_generation_invalide_aussi_les_sessions_ouvertes(client, ouvrir_session):
    ouvrir_session(P.BENEVOLE_ACCESS_MANAGE)
    client.put(URL, json={"password": "premier-secret-assez-long"})
    session_benevole = client.post(
        "/api/v1/benevoles/session", json={"password": "premier-secret-assez-long"}
    )
    assert session_benevole.status_code == 204

    client.post(URL_GENERATE)

    assert client.get("/api/v1/benevoles/queue").status_code == 401


# --- Garde RBAC : 401 avant 403 ----------------------------------------------


def test_sans_session_c_est_401(client):
    assert client.get(URL).status_code == 401
    assert client.put(URL, json={"password": "un-secret-assez-long"}).status_code == 401
    assert client.post(URL_GENERATE).status_code == 401


def test_sans_le_pouvoir_c_est_403(client, ouvrir_session):
    ouvrir_session()

    assert client.get(URL).status_code == 403
    assert client.put(URL, json={"password": "un-secret-assez-long"}).status_code == 403
    assert client.post(URL_GENERATE).status_code == 403
