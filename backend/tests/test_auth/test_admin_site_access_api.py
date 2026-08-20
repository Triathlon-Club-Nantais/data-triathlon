"""Gestion admin du mot de passe partagé du site (#509) — patron exact de
`test_admin_benevole_access_api.py`, RBAC (`site_access:manage`).

`GET`/`PUT /admin/site-access` sont gardées par `require_permission` : 401
sans session, 403 sans le pouvoir, 200 avec — jamais un 404, le routeur étant
monté depuis la tâche 8.
"""
from app.core.permissions import P

URL = "/api/v1/admin/site-access"
URL_GENERATE = f"{URL}/generate"


def test_get_sans_session_est_refuse(client):
    assert client.get(URL).status_code == 401


def test_get_sans_le_pouvoir_est_refuse(client, ouvrir_session):
    ouvrir_session()  # aucun pouvoir

    assert client.get(URL).status_code == 403


def test_get_rend_non_configure_avant_tout_reglage(client, ouvrir_session):
    ouvrir_session(P.SITE_ACCESS_MANAGE)

    reponse = client.get(URL)

    assert reponse.status_code == 200
    assert reponse.json() == {"configured": False, "updated_at": None, "updated_by": None}


def test_put_remplace_le_mot_de_passe(client, ouvrir_session):
    ouvrir_session(P.SITE_ACCESS_MANAGE, nom="Iris Admin")

    reponse = client.put(URL, json={"password": "un-secret-assez-long"})

    assert reponse.status_code == 200
    charge = reponse.json()
    assert charge["configured"] is True
    assert charge["updated_by"] == "Iris Admin"


def test_generate_rend_le_mot_de_passe_en_clair_une_seule_fois(client, ouvrir_session):
    ouvrir_session(P.SITE_ACCESS_MANAGE)

    reponse = client.post(URL_GENERATE)

    assert reponse.status_code == 200
    assert len(reponse.json()["password"]) >= 20
