"""Les trois ressources de `contracts/admin-api.md` (#170).

Parcours nominal et refus. L'ordre **401 avant 403** est vérifié, jamais supposé :
c'est une propriété de composition de `require_permission`, pas un `if` défensif.
"""
from app.core.permissions import P

URL = "/api/v1/admin/allowed-emails"


def test_lister_les_adresses_autorisees(client, ouvrir_session, autoriser):
    ouvrir_session(P.ALLOWED_EMAILS_MANAGE)
    autoriser("zoe@exemple.fr")

    reponse = client.get(URL)

    assert reponse.status_code == 200
    adresses = [ligne["email"] for ligne in reponse.json()]
    assert adresses == sorted(adresses)
    assert "zoe@exemple.fr" in adresses
    premiere = reponse.json()[0]
    assert {"id", "email", "created_at", "created_by_name"} == set(premiere)


def test_une_liste_vide_est_une_reponse_valide(
    client, ouvrir_session, vider_la_liste_autorisation
):
    ouvrir_session(P.ALLOWED_EMAILS_MANAGE)
    vider_la_liste_autorisation()

    reponse = client.get(URL)

    assert reponse.status_code == 200
    assert reponse.json() == []


def test_inscrire_une_adresse(client, ouvrir_session):
    ouvrir_session(P.ALLOWED_EMAILS_MANAGE, nom="Camille Durand")

    reponse = client.post(URL, json={"email": " Nouveau@Exemple.FR "})

    assert reponse.status_code == 201
    ligne = reponse.json()
    assert ligne["email"] == "nouveau@exemple.fr"
    assert ligne["created_by_name"] == "Camille Durand"


def test_inscrire_deux_fois_ne_cree_pas_de_doublon(client, ouvrir_session):
    """FR-005 : réinscrire est un succès, comme réattribuer un rôle en #115."""
    ouvrir_session(P.ALLOWED_EMAILS_MANAGE)

    premiere = client.post(URL, json={"email": "nouveau@exemple.fr"})
    seconde = client.post(URL, json={"email": "NOUVEAU@exemple.fr"})

    assert (premiere.status_code, seconde.status_code) == (201, 201)
    assert seconde.json()["id"] == premiere.json()["id"]
    assert [
        ligne["email"] for ligne in client.get(URL).json()
    ].count("nouveau@exemple.fr") == 1


def test_une_adresse_mal_formee_est_refusee(client, ouvrir_session):
    """FR-010 : rien n'est écrit, et le message est **réellement** en français.

    Les trois assertions comptent, et la deuxième est celle qui manquait : posée
    en `EmailStr` sur le DTO, la contrainte faisait rendre par FastAPI un
    `detail` **liste** portant le message anglais d'`email-validator`, que le
    front affichait en « [object Object] ». Vérifier le seul statut laissait
    passer les deux défauts.
    """
    ouvrir_session(P.ALLOWED_EMAILS_MANAGE)
    avant = client.get(URL).json()

    reponse = client.post(URL, json={"email": "pas-une-adresse"})

    assert reponse.status_code == 422
    detail = reponse.json()["detail"]
    assert isinstance(detail, str), "le front réaffiche `detail` verbatim"
    assert "pas-une-adresse" in detail and "adresse électronique" in detail
    assert client.get(URL).json() == avant


def test_une_adresse_acceptee_par_le_navigateur_mais_pas_par_nous(
    client, ouvrir_session
):
    """`<input type="email">` accepte `a@b` — un domaine sans point.

    C'est le chemin par lequel un 422 atteint réellement l'écran : la validation
    du navigateur ne suffit pas, et le message doit donc être lisible.
    """
    ouvrir_session(P.ALLOWED_EMAILS_MANAGE)

    reponse = client.post(URL, json={"email": "a@b"})

    assert reponse.status_code == 422
    assert isinstance(reponse.json()["detail"], str)


def test_lister_exige_le_pouvoir(client, ouvrir_session):
    ouvrir_session()

    assert client.get(URL).status_code == 403


def test_inscrire_exige_le_pouvoir(client, ouvrir_session, db_session):
    from app.models.allowed_email import AllowedEmail

    ouvrir_session()
    avant = db_session.query(AllowedEmail).count()

    reponse = client.post(URL, json={"email": "nouveau@exemple.fr"})

    assert reponse.status_code == 403
    assert db_session.query(AllowedEmail).count() == avant


def test_un_anonyme_obtient_401_et_jamais_la_liste(client):
    """FR-009 : 401 **avant** 403 — sans session, le contrôle de pouvoir n'est
    même pas atteint. Une liste d'adresses ne fuit pas par une erreur de garde."""
    assert client.get(URL).status_code == 401
    assert client.post(URL, json={"email": "x@exemple.fr"}).status_code == 401


# --- Le retrait (US2) -------------------------------------------------------


def test_retirer_une_adresse(client, ouvrir_session, autoriser):
    ouvrir_session(P.ALLOWED_EMAILS_MANAGE)
    autoriser("cible@exemple.fr")
    cible = next(
        ligne for ligne in client.get(URL).json() if ligne["email"] == "cible@exemple.fr"
    )

    reponse = client.delete(f"{URL}/{cible['id']}")

    assert reponse.status_code == 204
    assert "cible@exemple.fr" not in [ligne["email"] for ligne in client.get(URL).json()]


def test_retirer_un_identifiant_inconnu_est_un_succes(client, ouvrir_session):
    """Idempotent, comme la révocation d'un rôle : un 404 n'apprendrait rien à
    qui vient de supprimer la ligne dans un autre onglet."""
    ouvrir_session(P.ALLOWED_EMAILS_MANAGE)

    assert client.delete(f"{URL}/999999").status_code == 204


def test_le_retrait_ferme_la_session_ouverte_du_titulaire(
    client, ouvrir_session, autoriser, db_session
):
    """FR-016 : effectif au geste, sans déconnexion ni redémarrage.

    La session du compte retiré n'est pas supprimée — c'est la **jointure** de
    `session.resolve` sur `users.is_active` qui la refuse. Le test le vérifie
    des deux côtés : 401 rendu, et `user_sessions` intacte.
    """
    from app.api.v1.auth import session_cookie_name
    from app.core.config import get_settings
    from app.models.user_session import UserSession

    nom_cookie = session_cookie_name(get_settings())

    # La cible ouvre sa session **avant** le retrait, et on garde son cookie.
    ouvrir_session(email="cible@exemple.fr")
    cookie_cible = client.cookies.get(nom_cookie)
    assert client.get("/api/v1/auth/me").status_code == 200

    ouvrir_session(P.ALLOWED_EMAILS_MANAGE, email="admin@exemple.fr")
    autoriser("cible@exemple.fr")
    cible_id = next(
        ligne["id"]
        for ligne in client.get(URL).json()
        if ligne["email"] == "cible@exemple.fr"
    )
    sessions_avant = db_session.query(UserSession).count()

    assert client.delete(f"{URL}/{cible_id}").status_code == 204

    client.cookies.set(nom_cookie, cookie_cible)
    assert client.get("/api/v1/auth/me").status_code == 401
    # Aucune ligne n'a été touchée : c'est la jointure qui refuse, pas une purge.
    assert db_session.query(UserSession).count() == sessions_avant


def test_le_retrait_du_dernier_administrateur_est_refuse(
    client, ouvrir_session, db_session, autoriser
):
    """FR-018 : 409, et non 403 — l'appelant *est* administrateur, sa requête est
    bien formée, c'est le **résultat** qui est interdit.

    Le `rollback` explicite reproduit ce que le harnais court-circuite : en
    production, `get_db` ouvre une session **par requête** et la ferme sans
    `commit` sur erreur, ce qui défait le `flush` de l'invariant. Les tests
    partagent une session unique, donc la désactivation y survivrait en mémoire à
    un refus. Sans cette ligne, le test éprouverait le harnais, pas le contrat.
    """
    admin = ouvrir_session(superutilisateur=True, email="admin@exemple.fr")
    autoriser(admin.email)
    entree_id = next(
        ligne["id"] for ligne in client.get(URL).json() if ligne["email"] == admin.email
    )

    reponse = client.delete(f"{URL}/{entree_id}")
    db_session.rollback()

    assert reponse.status_code == 409
    assert admin.is_active is True
    assert admin.email in [ligne["email"] for ligne in client.get(URL).json()]


def test_avec_deux_administrateurs_le_retrait_passe(
    client, ouvrir_session, db_session, organisation, autoriser
):
    from app.models.role import Role
    from app.repositories import user_role_repository

    admin = ouvrir_session(superutilisateur=True, email="admin@exemple.fr")
    role = db_session.query(Role).filter_by(is_superuser=True).first()
    second = ouvrir_session(email="second@exemple.fr", pose_le_cookie=False)
    user_role_repository.grant(
        db_session, user_id=second.id, role_id=role.id, organisation_id=organisation.id
    )
    db_session.commit()
    autoriser(second.email)
    entree_id = next(
        ligne["id"] for ligne in client.get(URL).json() if ligne["email"] == second.email
    )

    assert client.delete(f"{URL}/{entree_id}").status_code == 204
    assert admin.is_active is True
    assert second.is_active is False


def test_retirer_exige_le_pouvoir(client, ouvrir_session):
    ouvrir_session()

    assert client.delete(f"{URL}/1").status_code == 403


def test_un_anonyme_ne_peut_pas_retirer(client):
    assert client.delete(f"{URL}/1").status_code == 401
