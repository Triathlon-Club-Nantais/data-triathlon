"""Garde `require_site_access` (#509), isolée sur une application jetable —
patron `test_benevoles_api.py::application`/`visiteur`."""
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.deps import require_site_access
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers
from app.repositories import user_repository
from app.services import site_access


@pytest.fixture
def administrateur(db_session):
    compte = user_repository.create(
        db_session, email="admin-test@exemple.fr", display_name="Admin Test"
    )
    db_session.flush()
    return compte


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
    valeur = site_access.sign_session("autre-secret-de-session")
    visiteur.cookies.set(site_access.SITE_SESSION_COOKIE, valeur)
    assert visiteur.get("/protege").status_code == 401


def test_accepte_un_cookie_valide(db_session, visiteur):
    from app.repositories import site_access_config_repository

    config = site_access_config_repository.get_config(db_session)
    valeur = site_access.sign_session(config.session_secret)
    visiteur.cookies.set(site_access.SITE_SESSION_COOKIE, valeur)
    assert visiteur.get("/protege").status_code == 200


def test_refuse_sans_configuration(db_session, visiteur):
    from app.models.site_access_config import SiteAccessConfig

    db_session.query(SiteAccessConfig).delete()
    db_session.commit()
    assert visiteur.get("/protege").status_code == 401
