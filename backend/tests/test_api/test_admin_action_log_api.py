"""GET /admin/action-log — lecture du journal d'administration (#501)."""
from app.api.v1.auth import session_cookie_name
from app.core.config import get_settings
from app.core.permissions import P
from app.models.organisation import Organisation
from app.models.role_permission import RolePermission
from app.repositories import (
    admin_action_log_repository,
    role_repository,
    user_repository,
    user_role_repository,
)
from app.services.auth import session as session_service


def _session_etroite(client, db_session, *codes, email="etroit@exemple.fr"):
    """Remplace la session superutilisateur du conftest par une session à pouvoirs comptés."""
    organisation = db_session.query(Organisation).first()
    user = user_repository.create(db_session, email=email)
    db_session.flush()
    if codes:
        role = role_repository.create(db_session, slug="etroit", name="Étroit")
        for code in codes:
            role.permissions.append(RolePermission(permission_code=str(code)))
        db_session.flush()
        user_role_repository.grant(
            db_session, user_id=user.id, role_id=role.id, organisation_id=organisation.id
        )
    jeton = session_service.open_for(db_session, user)
    db_session.commit()
    client.cookies.set(session_cookie_name(get_settings()), jeton)
    return user


def _semer(db_session, *, n=3, user_id):
    for indice in range(n):
        admin_action_log_repository.create(
            db_session,
            user_id=user_id,
            action="athlete.update",
            entity_type="athlete",
            entity_id=indice,
            payload={"rang": indice},
        )
    db_session.commit()


def test_lister_rend_la_page_par_defaut(client, db_session):
    auteur = user_repository.create(db_session, email="auteur@exemple.fr")
    db_session.flush()
    _semer(db_session, user_id=auteur.id)

    reponse = client.get("/api/v1/admin/action-log")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["total"] == 3
    assert [e["payload"]["rang"] for e in corps["entries"]] == [2, 1, 0]
    # `user_repository.create` pose `display_name=""` par défaut (aucun
    # fournisseur SSO ici) : la route retombe sur l'adresse.
    assert corps["entries"][0]["user_name"] == "auteur@exemple.fr"


def test_lister_pagine(client, db_session):
    auteur = user_repository.create(db_session, email="auteur@exemple.fr")
    db_session.flush()
    _semer(db_session, n=5, user_id=auteur.id)

    reponse = client.get("/api/v1/admin/action-log?page=2&page_size=2")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert [e["payload"]["rang"] for e in corps["entries"]] == [2, 1]
    assert corps["total"] == 5


def test_lister_sans_session_rend_401(client):
    client.cookies.clear()

    assert client.get("/api/v1/admin/action-log").status_code == 401


def test_lister_sans_le_pouvoir_rend_403(client, db_session):
    _session_etroite(client, db_session)

    assert client.get("/api/v1/admin/action-log").status_code == 403


def test_lister_avec_le_seul_pouvoir_utile_reussit(client, db_session):
    _session_etroite(client, db_session, P.ADMIN_LOG_READ)

    assert client.get("/api/v1/admin/action-log").status_code == 200
