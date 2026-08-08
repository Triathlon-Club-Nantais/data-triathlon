"""Révocation durable des sessions d'**un** compte, depuis le back-office (#169).

Elle comble ce que le retrait d'adresse (#170) ne fait pas : celui-ci ferme par
la jointure sans effacer une ligne, donc une réinscription dans la fenêtre de TTL
ressuscite les jetons. Ici les lignes partent, et le compte reste actif.
"""
from app.core.permissions import P
from app.services.auth import session as session_service


def _url(user_id: int) -> str:
    return f"/api/v1/admin/users/{user_id}/sessions/revoke"


def test_revoquer_un_compte_ferme_ses_sessions_et_epargne_les_autres(
    client, ouvrir_session, db_session
):
    cible = ouvrir_session(email="cible@exemple.fr", pose_le_cookie=False)
    jeton_cible = session_service.open_for(db_session, cible)
    db_session.commit()
    ouvrir_session(P.SESSIONS_REVOKE)

    reponse = client.post(_url(cible.id))

    assert reponse.status_code == 200
    # Deux sessions pour la cible : celle de la fixture, celle ouverte ici.
    assert reponse.json() == {"sessions": 2, "accounts": 1}
    assert session_service.resolve(db_session, jeton_cible) is None
    # L'appelant, lui, agit encore.
    assert client.get("/api/v1/auth/me").status_code == 200


def test_revoquer_un_compte_ne_le_desactive_pas(client, ouvrir_session, db_session):
    """C'est ce qui la distingue du retrait d'adresse : la personne se reconnecte."""
    cible = ouvrir_session(email="cible@exemple.fr", pose_le_cookie=False)
    ouvrir_session(P.SESSIONS_REVOKE)

    client.post(_url(cible.id))

    db_session.refresh(cible)
    assert cible.is_active is True


def test_un_compte_inconnu_est_un_succes_sans_effet(client, ouvrir_session):
    """Même parti pris que le retrait d'une adresse et d'un rôle : un 404
    n'apprendrait rien à qui vient de supprimer la ligne dans un autre onglet."""
    ouvrir_session(P.SESSIONS_REVOKE)

    reponse = client.post(_url(999_999))

    assert reponse.status_code == 200
    assert reponse.json() == {"sessions": 0, "accounts": 0}


def test_revoquer_son_propre_compte_ferme_sa_session(client, ouvrir_session):
    """Permis, et sans garde : c'est le geste de « j'ai perdu mon téléphone »."""
    acteur = ouvrir_session(P.SESSIONS_REVOKE)

    assert client.post(_url(acteur.id)).status_code == 200

    assert client.get("/api/v1/auth/me").status_code == 401


def test_le_journal_nomme_l_acteur_et_la_cible(client, ouvrir_session, caplog):
    victime = ouvrir_session(email="victime@exemple.fr", pose_le_cookie=False)
    acteur = ouvrir_session(P.SESSIONS_REVOKE)

    with caplog.at_level("INFO"):
        client.post(_url(victime.id))

    trace = "\n".join(enregistrement.getMessage() for enregistrement in caplog.records)
    assert f"actor={acteur.id}" in trace
    assert f"target_user={victime.id}" in trace


def test_sans_session_c_est_401(client):
    assert client.post(_url(1)).status_code == 401


def test_sans_le_pouvoir_c_est_403(client, ouvrir_session):
    """`allowed_emails:manage` ne suffit pas : retirer une adresse est réversible
    dans la fenêtre de TTL, effacer les jetons ne l'est pas."""
    ouvrir_session(P.ALLOWED_EMAILS_MANAGE)

    assert client.post(_url(1)).status_code == 403
