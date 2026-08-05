"""La garde de pouvoir : 401 avant 403, structurellement (#115, FR-015, FR-019).

L'application monte sa première route gardée en US1. Ici, la garde est éprouvée
**seule**, sur une application jetable : ce qu'on mesure est la fabrique, pas le
choix de ce qu'elle protège.
"""
import logging

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.deps import require_permission
from app.api.v1.auth import session_cookie_name
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers
from app.core.permissions import P
from app.models.organisation import Organisation
from app.models.role_permission import RolePermission
from app.models.user import User
from app.repositories import role_repository, user_repository, user_role_repository
from app.services.auth import session as session_service


@pytest.fixture
def application(db_session) -> FastAPI:
    """Une application minimale portant **une** route gardée."""
    api = FastAPI()
    register_exception_handlers(api)

    @api.get("/protege")
    def protege(user: User = Depends(require_permission(P.QUALITY_OVERRIDE))):
        return {"id": user.id}

    def _get_db():
        yield db_session

    api.dependency_overrides[get_db] = _get_db
    return api


@pytest.fixture
def visiteur(application) -> TestClient:
    with TestClient(application) as client:
        yield client


def _connecte(visiteur, db_session, *, codes=(), superutilisateur=False, actif=True):
    organisation = Organisation(slug="tcn", name="TCN")
    db_session.add(organisation)
    db_session.flush()
    user = user_repository.create(db_session, email="a@exemple.fr")
    user.is_active = actif
    db_session.flush()
    if codes or superutilisateur:
        role = role_repository.create(
            db_session, slug="role", name="Rôle", is_superuser=superutilisateur
        )
        for code in codes:
            role.permissions.append(RolePermission(permission_code=code))
        db_session.flush()
        user_role_repository.grant(
            db_session,
            user_id=user.id,
            role_id=role.id,
            organisation_id=organisation.id,
        )
    jeton = session_service.open_for(db_session, user)
    db_session.flush()
    visiteur.cookies.set(session_cookie_name(get_settings()), jeton)
    return user


def test_sans_session_la_ressource_gardee_rend_401(visiteur):
    reponse = visiteur.get("/protege")

    assert reponse.status_code == 401
    assert reponse.json()["detail"] == (
        "Vous devez être connecté pour accéder à cette ressource."
    )


def test_connecte_sans_le_pouvoir_la_ressource_rend_403(visiteur, db_session):
    _connecte(visiteur, db_session)

    assert visiteur.get("/protege").status_code == 403


def test_connecte_avec_le_pouvoir_la_ressource_repond(visiteur, db_session):
    user = _connecte(visiteur, db_session, codes=[P.QUALITY_OVERRIDE.code])

    reponse = visiteur.get("/protege")

    assert reponse.status_code == 200
    assert reponse.json() == {"id": user.id}


def test_un_superutilisateur_franchit_la_garde(visiteur, db_session):
    _connecte(visiteur, db_session, superutilisateur=True)

    assert visiteur.get("/protege").status_code == 200


def test_401_et_403_ne_se_confondent_jamais(visiteur, db_session):
    """FR-015 — et l'ordre est **structurel**, pas défensif.

    La fabrique compose `current_user` : une requête sans session n'atteint
    jamais le contrôle de pouvoir. Il n'y a donc pas de chemin où l'ordre
    pourrait s'inverser par inadvertance.
    """
    anonyme = visiteur.get("/protege").status_code
    _connecte(visiteur, db_session)
    connecte = visiteur.get("/protege").status_code

    assert (anonyme, connecte) == (401, 403)


def test_un_compte_desactive_rend_401_et_non_403(visiteur, db_session):
    """La session est déjà tombée (#114) : ce n'est pas un refus de droit.

    Dire 403 à quelqu'un dont le compte est désactivé lui ferait chercher un
    pouvoir manquant là où c'est son compte qui est fermé.
    """
    _connecte(visiteur, db_session, codes=[P.QUALITY_OVERRIDE.code], actif=False)

    assert visiteur.get("/protege").status_code == 401


def test_le_403_ne_nomme_ni_le_pouvoir_exige_ni_ceux_portes(visiteur, db_session):
    """FR-019 — un refus ne dresse pas la carte des droits pour qui insiste."""
    _connecte(visiteur, db_session, codes=[P.ROLES_READ.code])

    corps = visiteur.get("/protege").text

    assert "quality:override" not in corps
    assert "roles:read" not in corps
    assert "permission" not in corps.lower()


def test_le_message_de_refus_est_en_francais(visiteur, db_session):
    """Principe I : ce qui est visible d'un utilisateur est en français."""
    _connecte(visiteur, db_session)

    assert visiteur.get("/protege").json()["detail"] == (
        "Vous n'avez pas les droits nécessaires pour cette action."
    )


def test_un_refus_est_journalise_avec_l_utilisateur_et_la_ressource(
    visiteur, db_session, caplog
):
    """FR-034 — sans quoi un refus n'est diagnosticable par personne.

    En anglais (couche technique invisible), et sans jeton ni secret (FR-035) :
    le journal part chez l'hébergeur.
    """
    user = _connecte(visiteur, db_session)

    with caplog.at_level(logging.WARNING, logger="app.api.deps"):
        visiteur.get("/protege")

    trace = "\n".join(enregistrement.getMessage() for enregistrement in caplog.records)
    assert str(user.id) in trace
    assert "/protege" in trace
    assert "quality:override" in trace


def test_le_journal_de_refus_ne_porte_aucun_jeton(visiteur, db_session, caplog):
    _connecte(visiteur, db_session)
    jeton = visiteur.cookies.get(session_cookie_name(get_settings()))

    with caplog.at_level(logging.DEBUG):
        visiteur.get("/protege")

    trace = "\n".join(enregistrement.getMessage() for enregistrement in caplog.records)
    assert jeton not in trace


def test_la_garde_accepte_un_code_en_chaine(visiteur, db_session):
    """Le méta-test AST le tolère, la fabrique aussi — les deux formes se valent.

    Passer par `P.X` reste la forme recommandée : une chaîne mal orthographiée
    refuserait tout le monde en silence, et c'est le test AST qui la rattrape.
    """
    api = FastAPI()
    register_exception_handlers(api)

    @api.get("/chaine")
    def chaine(user: User = Depends(require_permission("quality:override"))):
        return {"id": user.id}

    def _get_db():
        yield db_session

    api.dependency_overrides[get_db] = _get_db
    _connecte(visiteur, db_session, codes=[P.QUALITY_OVERRIDE.code])
    with TestClient(api, cookies=visiteur.cookies) as client:
        assert client.get("/chaine").status_code == 200
