"""`GET /auth/me` et `POST /auth/logout` — identité affichée et déconnexion."""
from app.api.v1.auth import session_cookie_name
from app.core.config import get_settings
from app.models.user_session import UserSession
from app.repositories import user_repository
from app.services.auth import session


def _connecte(client, db_session, email="contributeur@exemple.fr") -> str:
    user = user_repository.create(db_session, email=email, display_name="contributeur")
    db_session.flush()
    jeton = session.open_for(db_session, user)
    db_session.commit()
    client.cookies.set(session_cookie_name(get_settings()), jeton)
    return jeton


def test_me_rend_l_identite_avec_une_session(client, db_session):
    _connecte(client, db_session)

    reponse = client.get("/api/v1/auth/me")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["email"] == "contributeur@exemple.fr"
    assert corps["display_name"] == "contributeur"
    assert corps["created_at"].endswith("Z")


def test_me_rend_401_sans_session(client):
    """Point de contrat **figé** : 401, et jamais « 200 avec un corps nul ».

    En changer plus tard inverserait une sémantique, ce que le Principe IV
    proscrit.
    """
    reponse = client.get("/api/v1/auth/me")

    assert reponse.status_code == 401
    assert "detail" in reponse.json()


def test_me_rend_401_sur_un_jeton_invalide(client):
    client.cookies.set(session_cookie_name(get_settings()), "j" * 43)

    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_rend_401_quand_le_compte_est_desactive(client, db_session):
    _connecte(client, db_session)
    from app.models.user import User

    db_session.query(User).one().is_active = False
    db_session.commit()

    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_n_expose_ni_jeton_ni_identifiant_de_session(client, db_session):
    jeton = _connecte(client, db_session)

    corps = client.get("/api/v1/auth/me").text

    assert jeton not in corps
    assert "token" not in corps
    assert "session" not in corps


def test_logout_ferme_la_session_et_rend_204(client, db_session):
    jeton = _connecte(client, db_session)

    reponse = client.post("/api/v1/auth/logout")

    assert reponse.status_code == 204
    assert reponse.content == b""
    assert session.resolve(db_session, jeton) is None
    assert db_session.query(UserSession).count() == 0


def test_logout_efface_le_cookie(client, db_session):
    """L'effacement se lit dans l'en-tête `Set-Cookie` de la réponse.

    Pas dans le bocal du client : le cookie y a été posé à la main par le test,
    sans domaine, là où celui de la réponse en porte un — httpx y voit deux
    entrées distinctes, et ce serait l'artefact qu'on mesurerait.
    """
    _connecte(client, db_session)
    nom = session_cookie_name(get_settings())

    reponse = client.post("/api/v1/auth/logout")

    effacement = [e for e in reponse.headers.get_list("set-cookie") if e.startswith(f"{nom}=")]
    assert effacement, "aucun Set-Cookie d'effacement"
    assert 'Max-Age=0' in effacement[0] or "1970" in effacement[0]


def test_logout_est_idempotent_sans_cookie(client):
    """Se déconnecter d'une session absente est un **succès**, jamais un 401."""
    assert client.post("/api/v1/auth/logout").status_code == 204


def test_logout_est_idempotent_sur_un_jeton_invalide(client):
    client.cookies.set(session_cookie_name(get_settings()), "j" * 43)

    assert client.post("/api/v1/auth/logout").status_code == 204


def test_logout_ne_ferme_pas_les_autres_appareils(client, db_session):
    """FR-014 — la différence de comportement assumée avec la PR #159."""
    user = user_repository.create(db_session, email="a@exemple.fr", display_name="a")
    db_session.flush()
    autre_appareil = session.open_for(db_session, user)
    cet_appareil = session.open_for(db_session, user)
    db_session.commit()
    client.cookies.set(session_cookie_name(get_settings()), cet_appareil)

    client.post("/api/v1/auth/logout")

    assert session.resolve(db_session, cet_appareil) is None
    assert session.resolve(db_session, autre_appareil) is not None
