"""La révocation d'urgence depuis le back-office (#169).

Une seule ressource, et **globale** : fermer les sessions d'un compte a déjà son
geste — retirer son adresse (#170) —, le trou portait sur « tous les comptes à la
fois ». L'ordre 401 avant 403 est vérifié, jamais supposé.
"""
from app.core.permissions import P
from app.repositories import user_repository
from app.services.auth import session as session_service

URL = "/api/v1/admin/sessions/revoke"


def test_revoquer_ferme_toutes_les_sessions_et_compte_les_deux_unites(
    client, ouvrir_session, db_session
):
    autre = user_repository.create(db_session, email="autre@exemple.fr")
    db_session.flush()
    jeton = session_service.open_for(db_session, autre)
    db_session.commit()
    ouvrir_session(P.SESSIONS_REVOKE)

    reponse = client.post(URL)

    assert reponse.status_code == 200
    # Deux sessions, deux comptes : celui de l'appelant compris.
    assert reponse.json() == {"sessions": 2, "accounts": 2}
    assert session_service.resolve(db_session, jeton) is None


def test_la_revocation_ferme_aussi_la_session_de_l_appelant(client, ouvrir_session):
    """Et ce n'est pas un effet de bord à corriger.

    Sous fuite, le jeton de celui qui clique est suspect comme les autres.
    L'écran le dit avant de lancer le geste ; l'API ne s'épargne pas.
    """
    ouvrir_session(P.SESSIONS_REVOKE)

    assert client.post(URL).status_code == 200

    assert client.get("/api/v1/auth/me").status_code == 401


def test_le_journal_nomme_l_acteur(client, ouvrir_session, caplog):
    """« Qui a coupé tout le monde, et quand » est la première question posée.

    C'est le geste le plus destructeur de l'application, et le seul dont
    l'auteur ne serait pas identifiable après coup — la session qui l'a lancé
    étant elle-même détruite. Tous les gestes d'administration du dépôt
    journalisent leur acteur (`groups.py`, `allowed_emails.py`) ; celui-ci ne
    peut pas faire exception.
    """
    acteur = ouvrir_session(P.SESSIONS_REVOKE)

    with caplog.at_level("INFO"):
        client.post(URL)

    trace = "\n".join(enregistrement.getMessage() for enregistrement in caplog.records)
    assert f"actor={acteur.id}" in trace


def test_sans_session_c_est_401(client):
    assert client.post(URL).status_code == 401


def test_sans_le_pouvoir_c_est_403(client, ouvrir_session):
    ouvrir_session(P.ALLOWED_EMAILS_MANAGE)

    assert client.post(URL).status_code == 403


def test_aucune_session_ouverte_reste_un_succes(client, ouvrir_session, db_session):
    """Idempotent : révoquer deux fois de suite n'est pas une erreur."""
    ouvrir_session(P.SESSIONS_REVOKE)
    client.post(URL)
    ouvrir_session(P.SESSIONS_REVOKE)

    reponse = client.post(URL)

    assert reponse.status_code == 200
    assert reponse.json() == {"sessions": 1, "accounts": 1}
