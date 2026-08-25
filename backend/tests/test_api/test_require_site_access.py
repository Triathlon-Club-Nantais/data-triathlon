"""Garde `require_site_access` (#509), isolée sur une application jetable —
patron `test_benevoles_api.py::application`/`visiteur`."""
import time

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.deps import require_site_access
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers
from app.services import shared_password, site_access


@pytest.fixture(autouse=True)
def mot_de_passe_configure(db_session, administrateur):
    site_access.replace_password(db_session, password="secret-du-site", admin_user_id=administrateur.id)
    db_session.commit()


@pytest.fixture
def application(db_session) -> FastAPI:
    api = FastAPI()
    register_exception_handlers(api)

    @api.get("/protege", dependencies=[Depends(require_site_access)])
    def protege():
        return {"ok": True}

    def _get_db():
        yield db_session

    api.dependency_overrides[get_db] = _get_db
    return api


@pytest.fixture
def visiteur(application) -> TestClient:
    with TestClient(application) as client:
        yield client


def test_refuse_sans_cookie(visiteur):
    assert visiteur.get("/protege").status_code == 401


def test_refuse_avec_un_cookie_invalide(visiteur):
    visiteur.cookies.set(site_access.SITE_SESSION_COOKIE, "n-importe-quoi")
    assert visiteur.get("/protege").status_code == 401


def test_refuse_meme_avec_un_cookie_signe_par_un_autre_secret(visiteur):
    valeur = shared_password.sign_cookie("autre-secret-de-session")
    visiteur.cookies.set(site_access.SITE_SESSION_COOKIE, valeur)
    assert visiteur.get("/protege").status_code == 401


def test_accepte_un_cookie_valide(db_session, visiteur):
    from app.repositories import site_access_config_repository

    config = site_access_config_repository.get_config(db_session)
    valeur = shared_password.sign_cookie(config.session_secret)
    visiteur.cookies.set(site_access.SITE_SESSION_COOKIE, valeur)
    assert visiteur.get("/protege").status_code == 200


def test_refuse_un_cookie_plus_vieux_que_le_ttl(db_session, visiteur):
    """C'est la garde qui porte l'expiration, pas le cookie : `max_age` côté
    navigateur est une politesse qu'un client peut ignorer. Le test forge donc
    un horodatage antérieur au TTL et vérifie que le serveur refuse — seul
    endroit où `Settings.site_access_session_ttl_days` est éprouvé de bout en
    bout (la vérification elle-même vit dans `shared_password.verify_cookie`).
    """
    from app.core.config import get_settings
    from app.repositories import site_access_config_repository

    config = site_access_config_repository.get_config(db_session)
    ttl_seconds = get_settings().site_access_session_ttl_days * 24 * 60 * 60
    horodatage = str(int(time.time()) - ttl_seconds - 60)
    valeur = f"{horodatage}.{shared_password._hmac(config.session_secret, horodatage)}"

    visiteur.cookies.set(site_access.SITE_SESSION_COOKIE, valeur)
    assert visiteur.get("/protege").status_code == 401


def test_refuse_sans_configuration(db_session, visiteur):
    from app.models.site_access_config import SiteAccessConfig

    db_session.query(SiteAccessConfig).delete()
    db_session.commit()
    assert visiteur.get("/protege").status_code == 401
