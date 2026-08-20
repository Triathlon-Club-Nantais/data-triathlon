"""Ouverture/fermeture/vérification de la session site (#509)."""
import pytest

from app.repositories import user_repository
from app.services import site_access

MOT_DE_PASSE = "secret-du-club"


@pytest.fixture
def administrateur(db_session):
    compte = user_repository.create(
        db_session, email="admin-test@exemple.fr", display_name="Admin Test"
    )
    db_session.flush()
    return compte


@pytest.fixture(autouse=True)
def mot_de_passe_configure(db_session, administrateur):
    site_access.replace_password(db_session, password=MOT_DE_PASSE, admin_user_id=administrateur.id)
    db_session.commit()


def _client_anonyme(client):
    """`client` neutralise `require_site_access` par défaut (Task 8) — ce
    fichier teste précisément ce mécanisme, il le retire."""
    from app.api.deps import require_site_access
    from app.main import app

    app.dependency_overrides.pop(require_site_access, None)
    return client


def test_ouvre_une_session_avec_le_bon_mot_de_passe(client):
    reponse = _client_anonyme(client).post("/api/v1/site-access/session", json={"password": MOT_DE_PASSE})
    assert reponse.status_code == 204
    assert site_access.SITE_SESSION_COOKIE in reponse.cookies


def test_refuse_un_mauvais_mot_de_passe(client):
    reponse = _client_anonyme(client).post(
        "/api/v1/site-access/session", json={"password": "mauvais-mot-de-passe"}
    )
    assert reponse.status_code == 401
    assert site_access.SITE_SESSION_COOKIE not in reponse.cookies


def test_ferme_la_session(client):
    c = _client_anonyme(client)
    c.post("/api/v1/site-access/session", json={"password": MOT_DE_PASSE})
    reponse = c.delete("/api/v1/site-access/session")
    assert reponse.status_code == 204


def test_verification_refuse_sans_cookie(client):
    reponse = _client_anonyme(client).get("/api/v1/site-access/session")
    assert reponse.status_code == 401


def test_verification_accepte_apres_ouverture(client):
    c = _client_anonyme(client)
    c.post("/api/v1/site-access/session", json={"password": MOT_DE_PASSE})
    reponse = c.get("/api/v1/site-access/session")
    assert reponse.status_code == 200
