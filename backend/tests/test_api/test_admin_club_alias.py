"""Édition des alias de club (#635) — panel admin, sur le patron de la portée
des compteurs."""
from app.api.v1.auth import session_cookie_name
from app.core.config import get_settings
from app.models.admin_action_log import AdminActionLog
from app.models.role_permission import RolePermission
from app.repositories import (
    club_alias_repository,
    role_repository,
    user_repository,
    user_role_repository,
)
from app.services.auth import session as session_service

BASE = "/api/v1/admin/club-aliases"


def _semer(db_session, canonical_name: str, *alias: str) -> None:
    for a in alias:
        club_alias_repository.create_entry(
            db_session, canonical_name=canonical_name, alias_normalized=a, created_by_user_id=None
        )
    db_session.commit()


# --- GET -----------------------------------------------------------------


def test_la_lecture_rend_les_entrees(client, db_session):
    _semer(db_session, "Racing Club Nantais", "racing club nantais", "rcn 44")

    corps = client.get(BASE).json()

    assert {e["alias"] for e in corps["entries"]} == {"racing club nantais", "rcn 44"}
    assert all(e["canonical_name"] == "Racing Club Nantais" for e in corps["entries"])


def test_la_lecture_rend_une_liste_vide_sans_configuration(client):
    assert client.get(BASE).json() == {"entries": []}


# --- POST ------------------------------------------------------------------


def test_l_ajout_normalise_l_alias(client):
    reponse = client.post(
        BASE, json={"canonical_name": "Racing Club Nantais", "alias": "RACING  CLUB NANTAIS"}
    )

    assert reponse.status_code == 201
    assert reponse.json()["alias"] == "racing club nantais"
    assert reponse.json()["canonical_name"] == "Racing Club Nantais"


def test_l_ajout_nomme_son_auteur(client):
    corps = client.post(BASE, json={"canonical_name": "RCN", "alias": "rcn"}).json()

    assert corps["created_by"] is not None
    assert corps["created_at"] is not None


def test_l_ajout_refuse_un_alias_vide(client):
    reponse = client.post(BASE, json={"canonical_name": "RCN", "alias": "   "})

    assert reponse.status_code == 400
    assert "vide" in reponse.json()["detail"]


def test_l_ajout_refuse_un_nom_canonique_vide(client):
    reponse = client.post(BASE, json={"canonical_name": "   ", "alias": "rcn"})

    assert reponse.status_code == 400
    assert "vide" in reponse.json()["detail"]


def test_l_ajout_refuse_un_alias_deja_rattache(client, db_session):
    _semer(db_session, "Racing Club Nantais", "racing club nantais")

    reponse = client.post(
        BASE, json={"canonical_name": "RC Nantais", "alias": "RACING CLUB NANTAIS"}
    )

    assert reponse.status_code == 409
    assert "déjà rattaché" in reponse.json()["detail"]


def test_deux_alias_peuvent_partager_le_meme_nom_canonique(client):
    client.post(BASE, json={"canonical_name": "Racing Club Nantais", "alias": "RACING CLUB NANTAIS"})

    reponse = client.post(BASE, json={"canonical_name": "Racing Club Nantais", "alias": "RCN 44"})

    assert reponse.status_code == 201


# --- DELETE ------------------------------------------------------------------


def test_le_retrait_supprime_l_entree(client, db_session):
    _semer(db_session, "Racing Club Nantais", "racing club nantais")
    cible = club_alias_repository.find_by_alias(db_session, alias_normalized="racing club nantais")

    reponse = client.delete(f"{BASE}/{cible.id}")

    assert reponse.status_code == 204
    assert client.get(BASE).json()["entries"] == []


def test_un_identifiant_inconnu_est_introuvable(client):
    reponse = client.delete(f"{BASE}/4242")

    assert reponse.status_code == 404


# --- Journal d'administration --------------------------------------------


def test_l_ajout_est_journalise(client, db_session):
    client.post(BASE, json={"canonical_name": "RCN", "alias": "rcn"})

    ligne = db_session.query(AdminActionLog).order_by(AdminActionLog.id.desc()).first()
    assert ligne.action == "club_alias.add"
    assert ligne.entity_type == "club_alias"
    assert ligne.user_id is not None


def test_le_retrait_est_journalise(client, db_session):
    _semer(db_session, "Racing Club Nantais", "racing club nantais")
    cible = club_alias_repository.find_by_alias(db_session, alias_normalized="racing club nantais")

    client.delete(f"{BASE}/{cible.id}")

    ligne = db_session.query(AdminActionLog).order_by(AdminActionLog.id.desc()).first()
    assert ligne.action == "club_alias.remove"
    assert ligne.entity_id == cible.id


# --- La garde ----------------------------------------------------------------


def test_l_acces_anonyme_est_refuse(client):
    client.cookies.clear()

    assert client.get(BASE).status_code == 401


def test_un_compte_sans_le_pouvoir_est_refuse(client, db_session):
    from app.models.organisation import Organisation

    organisation = db_session.query(Organisation).filter_by(slug="tcn").one()
    role = role_repository.create(db_session, slug="sans-pouvoir-club-alias", name="Sans pouvoir")
    role.permissions.append(RolePermission(permission_code="feedback:read"))
    db_session.flush()
    autre = user_repository.create(db_session, email="sans-pouvoir-alias@exemple.fr")
    db_session.flush()
    user_role_repository.grant(
        db_session, user_id=autre.id, role_id=role.id, organisation_id=organisation.id
    )
    jeton = session_service.open_for(db_session, autre)
    db_session.commit()
    client.cookies.set(session_cookie_name(get_settings()), jeton)

    assert client.get(BASE).status_code == 403
