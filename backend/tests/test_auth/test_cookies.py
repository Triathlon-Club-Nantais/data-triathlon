"""Attributs des cookies — `__Host-`, `HttpOnly`, `SameSite`, absence de `Domain`.

`SameSite` protège la **lecture** d'un cookie, jamais son **écriture**. Sans
`__Host-`, tout contenu exécuté sur un domaine apparenté peut poser un cookie de
session et provoquer une **fixation** — la victime navigue alors dans le compte
de l'attaquant — ou injecter un cookie d'état et rouvrir le CSRF de connexion.
`vercel.app` figurant sur la Public Suffix List, la production actuelle est
protégée **par accident** : brancher un domaine propre ferait tomber cette
protection. Le préfixe est en outre impossible à rétrofitter sans invalider
toutes les sessions.
"""
import pytest

from app.api.v1.auth import session_cookie_name, state_cookie_name
from app.core.config import get_settings


def _entetes_set_cookie(reponse) -> list[str]:
    return reponse.headers.get_list("set-cookie")


def _cookie(reponse, prefixe: str) -> str:
    correspondants = [e for e in _entetes_set_cookie(reponse) if e.startswith(prefixe)]
    assert correspondants, f"aucun Set-Cookie ne commence par {prefixe!r}"
    return correspondants[0]


@pytest.fixture
def en_https(monkeypatch):
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")
    get_settings.cache_clear()


@pytest.fixture
def client_https(db_session, en_https):
    """Client dont l'URL de base est en HTTPS.

    Indispensable dès que `AUTH_COOKIE_SECURE` est actif : un client sur
    `http://testserver` **n'émet pas** un cookie `Secure` qu'il a pourtant reçu,
    donc le retour de parcours n'aurait jamais son cookie d'état et échouerait
    en `state_mismatch` — un artefact du bac à sable, pas un défaut du code.
    """
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    app.dependency_overrides.clear()


def test_le_nom_porte_le_prefixe_host_en_production(en_https):
    settings = get_settings()

    assert session_cookie_name(settings) == "__Host-tcn_session"
    assert state_cookie_name(settings) == "__Host-tcn_auth_state"


def test_le_prefixe_est_retire_sans_tls():
    """Le préfixe **exige** `Secure` : le conserver en clair ferait rejeter le
    cookie par le navigateur, et la connexion échouerait sans rien dire."""
    settings = get_settings()  # la fixture du paquet pose AUTH_COOKIE_SECURE=false

    assert session_cookie_name(settings) == "tcn_session"
    assert state_cookie_name(settings) == "tcn_auth_state"


def test_le_nom_est_derive_jamais_bricole():
    """Un seul point de dérivation, pour les deux cookies et les deux modes."""
    import inspect

    from app.api.v1 import auth

    source = inspect.getsource(auth)
    assert source.count('"__Host-') <= 1


def test_le_cookie_d_etat_porte_les_bons_attributs(client_https, doublure):
    reponse = client_https.get("/api/v1/auth/doublure/authorize", follow_redirects=False)

    entete = _cookie(reponse, "__Host-tcn_auth_state=")
    assert "HttpOnly" in entete
    assert "Secure" in entete
    assert "SameSite=lax" in entete.replace("SameSite=Lax", "SameSite=lax")
    assert "Path=/" in entete
    assert "Domain" not in entete


def test_le_cookie_de_session_porte_les_bons_attributs(client_https, doublure):
    from app.services.auth import state

    client_https.get("/api/v1/auth/doublure/authorize", follow_redirects=False)
    charge = state.read(client_https.cookies["__Host-tcn_auth_state"])
    reponse = client_https.get(
        f"/api/v1/auth/doublure/callback?code=c&state={charge.state}",
        follow_redirects=False,
    )

    entete = _cookie(reponse, "__Host-tcn_session=")
    assert "HttpOnly" in entete
    assert "Secure" in entete
    assert "SameSite=lax" in entete.replace("SameSite=Lax", "SameSite=lax")
    assert "Path=/" in entete
    assert "Domain" not in entete


def test_aucun_cookie_ne_porte_d_attribut_domain(client, doublure):
    """`__Host-` **interdit** `Domain` ; le vérifier aussi en clair garantit que
    les deux modes se comportent pareil sur ce point."""
    reponse = client.get("/api/v1/auth/doublure/authorize", follow_redirects=False)

    for entete in _entetes_set_cookie(reponse):
        assert "Domain" not in entete


def test_le_cookie_de_session_survit_a_la_fermeture_de_l_onglet(client_https, doublure):
    """Scénario 3 d'US1 : une session de navigateur ne suffirait pas."""
    from app.services.auth import state

    client_https.get("/api/v1/auth/doublure/authorize", follow_redirects=False)
    charge = state.read(client_https.cookies["__Host-tcn_auth_state"])
    reponse = client_https.get(
        f"/api/v1/auth/doublure/callback?code=c&state={charge.state}",
        follow_redirects=False,
    )

    entete = _cookie(reponse, "__Host-tcn_session=")
    assert "Max-Age" in entete or "Expires" in entete


def _efface(reponse, nom: str) -> str:
    entetes = [e for e in _entetes_set_cookie(reponse) if e.startswith(f"{nom}=")]
    assert entetes, f"aucun Set-Cookie d'effacement pour {nom!r}"
    entete = entetes[0]
    assert "Max-Age=0" in entete or "1970" in entete, entete
    return entete


def test_l_effacement_de_l_etat_porte_secure_en_production(client_https, doublure):
    """RFC 6265bis §4.1.3 : un `Set-Cookie` `__Host-` **sans** `Secure` est ignoré.

    L'effacement était donc inopérant en production, et le jeton d'état
    survivait ses 600 s dans le navigateur — l'usage unique de FR-023 tombait
    précisément là où il compte. Invisible jusqu'ici : les tests d'effacement
    tournent sous `AUTH_COOKIE_SECURE=false`, où le nom n'a pas de préfixe.
    """
    from app.services.auth import state

    client_https.get("/api/v1/auth/doublure/authorize", follow_redirects=False)
    charge = state.read(client_https.cookies["__Host-tcn_auth_state"])
    reponse = client_https.get(
        f"/api/v1/auth/doublure/callback?code=c&state={charge.state}",
        follow_redirects=False,
    )

    assert "Secure" in _efface(reponse, "__Host-tcn_auth_state")


def test_l_effacement_de_la_session_porte_secure_en_production(client_https, db_session):
    from app.repositories import user_repository
    from app.services.auth import session

    user = user_repository.create(db_session, email="a@exemple.fr", display_name="a")
    db_session.flush()
    client_https.cookies.set("__Host-tcn_session", session.open_for(db_session, user))
    db_session.commit()

    reponse = client_https.post("/api/v1/auth/logout")

    assert "Secure" in _efface(reponse, "__Host-tcn_session")


def test_l_effacement_conserve_les_autres_attributs(client_https, doublure):
    """`HttpOnly`, `Path=/` et l'absence de `Domain` doivent tenir aussi sur
    l'effacement : un `Set-Cookie` qui ne correspond pas à celui posé ne
    remplace rien."""
    reponse = client_https.get("/api/v1/auth/doublure/callback?code=c&state=faux",
                               follow_redirects=False)

    entete = _efface(reponse, "__Host-tcn_auth_state")
    assert "HttpOnly" in entete
    assert "Path=/" in entete
    assert "Domain" not in entete


def test_le_cookie_de_presence_ne_porte_jamais_le_prefixe_host(en_https):
    """#427 — signal lisible en JS pour éviter d'émettre `/auth/me` en pure
    perte pour un visiteur anonyme. Il ne porte aucun secret : contrairement à
    la session et à l'état, son nom n'a pas besoin de varier avec l'environnement."""
    from app.api.v1.auth import LOGGED_IN_COOKIE

    assert LOGGED_IN_COOKIE == "tcn_logged_in"


def test_le_cookie_de_presence_est_pose_a_la_connexion_sans_httponly(client_https, doublure):
    from app.services.auth import state

    client_https.get("/api/v1/auth/doublure/authorize", follow_redirects=False)
    charge = state.read(client_https.cookies["__Host-tcn_auth_state"])
    reponse = client_https.get(
        f"/api/v1/auth/doublure/callback?code=c&state={charge.state}",
        follow_redirects=False,
    )

    entete = _cookie(reponse, "tcn_logged_in=")
    assert "HttpOnly" not in entete
    assert "Path=/" in entete
    assert "Domain" not in entete


def test_l_effacement_du_cookie_de_presence_a_la_deconnexion_reste_lisible(client_https, db_session):
    from app.repositories import user_repository
    from app.services.auth import session

    user = user_repository.create(db_session, email="a@exemple.fr", display_name="a")
    db_session.flush()
    client_https.cookies.set("__Host-tcn_session", session.open_for(db_session, user))
    db_session.commit()

    reponse = client_https.post("/api/v1/auth/logout")

    entete = _efface(reponse, "tcn_logged_in")
    assert "HttpOnly" not in entete
