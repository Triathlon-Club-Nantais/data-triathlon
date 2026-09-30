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
    reponse = client.get(URL)

    assert reponse.status_code == 401
    # La garde SSO ne porte pas le discriminant de la garde du site (#877).
    assert "code" not in reponse.json()


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


def test_put_refuse_un_mot_de_passe_plus_long_que_ce_que_la_connexion_accepte(
    client, ouvrir_session
):
    """Les deux bornes doivent se répondre (relevé en revue de #513).

    `SiteAccessLogin` plafonne à 200 ; sans la même borne ici, un `PUT` de 201
    caractères réussissait — le secret tournait, toutes les sessions ouvertes
    tombaient, et `POST /site-access/session` rendait ensuite 422 sur le seul
    mot de passe qui aurait marché. Tout le monde dehors, personne au courant.
    """
    ouvrir_session(P.SITE_ACCESS_MANAGE)

    reponse = client.put(URL, json={"password": "x" * 201})

    assert reponse.status_code == 422
    assert client.get(URL).json()["configured"] is False  # rien n'a été remplacé


def test_put_refuses_a_typed_password_shorter_than_twelve_characters(client, ouvrir_session):
    """A typed secret is the only bound on distributed brute force (#1020)."""
    ouvrir_session(P.SITE_ACCESS_MANAGE)

    assert client.put(URL, json={"password": "tcn2026!xx1"}).status_code == 422
    assert client.put(URL, json={"password": "tcn2026!xx12"}).status_code == 200


def test_put_accepte_la_longueur_maximale_de_la_connexion(client, ouvrir_session):
    """La borne est la **même** des deux côtés, pas seulement présente."""
    ouvrir_session(P.SITE_ACCESS_MANAGE)

    assert client.put(URL, json={"password": "x" * 200}).status_code == 200


def test_generate_rend_le_mot_de_passe_en_clair_une_seule_fois(client, ouvrir_session):
    ouvrir_session(P.SITE_ACCESS_MANAGE)

    reponse = client.post(URL_GENERATE)

    assert reponse.status_code == 200
    assert len(reponse.json()["password"]) >= 20


def test_get_rend_un_code_pose_hors_ligne_sans_auteur(client, ouvrir_session, db_session):
    """`set-site-code` (#929) pose le code sans utilisateur : l'écran ne doit pas planter."""
    from app.services import site_access

    site_access.replace_password(db_session, password="un-code-hors-ligne", admin_user_id=None)
    db_session.commit()
    ouvrir_session(P.SITE_ACCESS_MANAGE)

    reponse = client.get(URL)

    assert reponse.status_code == 200
    assert reponse.json()["configured"] is True
    assert reponse.json()["updated_by"] is None


def test_put_rouvre_le_site_pour_l_admin_qui_change_le_code(client, ouvrir_session):
    """#877 : la rotation du secret fermait aussi la session de site de l'admin
    appelant, et chaque écran admin lui répondait ensuite 401."""
    from app.services import site_access

    ouvrir_session(P.SITE_ACCESS_MANAGE)

    reponse = client.put(URL, json={"password": "un-secret-assez-long"})

    assert site_access.SITE_SESSION_COOKIE in reponse.cookies
    assert client.get("/api/v1/site-access/session").status_code == 200


def test_generate_rouvre_le_site_pour_l_admin_qui_change_le_code(client, ouvrir_session):
    from app.services import site_access

    ouvrir_session(P.SITE_ACCESS_MANAGE)

    reponse = client.post(URL_GENERATE)

    assert site_access.SITE_SESSION_COOKIE in reponse.cookies
    assert client.get("/api/v1/site-access/session").status_code == 200
