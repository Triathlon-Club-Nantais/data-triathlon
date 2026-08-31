"""API admin des déclarations de bénévolat (#751) —
contracts/volunteer-declaration-api.md.

`session_de_saisie` (autouse, `tests/test_api/conftest.py`) ouvre une session
superutilisateur — les tests de refus utilisent `_session_etroite` pour
l'écraser (patron `test_admin_feedback_api.py`).
"""
from app.api.v1.auth import session_cookie_name
from app.core.config import get_settings
from app.core.permissions import P
from app.models.admin_action_log import AdminActionLog
from app.models.organisation import Organisation
from app.models.role_permission import RolePermission
from app.repositories import (
    role_repository,
    user_repository,
    user_role_repository,
    volunteer_declaration_repository,
)
from app.services.auth import session as session_service

_URL = "/api/v1/admin/volunteer-declarations"


def _session_etroite(client, db_session, *codes):
    organisation = db_session.query(Organisation).first()
    user = user_repository.create(db_session, email="etroit@exemple.fr")
    db_session.flush()
    if codes:
        role = role_repository.create(db_session, slug="etroit-benevolat", name="Étroit")
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


def _beneficiaire(db_session, email="beneficiaire@exemple.fr"):
    user = user_repository.create(db_session, email=email)
    db_session.flush()
    db_session.commit()
    return user


# --- Création pour un tiers, validée d'office (US2) --------------------------


def test_creer_pour_un_tiers_est_valide_doffice(client, db_session):
    beneficiaire = _beneficiaire(db_session)

    reponse = client.post(
        _URL,
        json={"title": "Signaleur", "description": "Carrefour", "beneficiary_user_id": beneficiaire.id},
    )

    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["status"] == "validee"
    assert corps["beneficiary_user_id"] == beneficiaire.id


def test_creer_pour_un_tiers_sans_le_pouvoir_rend_403(client, db_session):
    beneficiaire = _beneficiaire(db_session)
    _session_etroite(client, db_session)

    reponse = client.post(
        _URL,
        json={"title": "T", "description": "D", "beneficiary_user_id": beneficiaire.id},
    )

    assert reponse.status_code == 403


def test_creer_pour_un_beneficiaire_inconnu_rend_404(client):
    reponse = client.post(
        _URL, json={"title": "T", "description": "D", "beneficiary_user_id": 999999}
    )

    assert reponse.status_code == 404


def test_creer_pour_un_tiers_journalise_ladmin_action_log(client, db_session):
    beneficiaire = _beneficiaire(db_session)

    client.post(
        _URL, json={"title": "T", "description": "D", "beneficiary_user_id": beneficiaire.id}
    )

    entree = db_session.query(AdminActionLog).one()
    assert entree.action == "volunteer_declaration.create_for_other"
    assert entree.entity_type == "volunteer_declaration"


# --- Validation d'une déclaration en attente (US3) ----------------------------


def _en_attente(db_session, beneficiaire_id):
    declaration = volunteer_declaration_repository.create(
        db_session,
        title="T",
        description="D",
        beneficiary_user_id=beneficiaire_id,
        author_user_id=beneficiaire_id,
        status="en_attente",
    )
    db_session.commit()
    return declaration


def test_valider_fait_passer_en_attente_a_validee(client, db_session):
    beneficiaire = _beneficiaire(db_session)
    declaration = _en_attente(db_session, beneficiaire.id)

    reponse = client.post(f"{_URL}/{declaration.id}/validate")

    assert reponse.status_code == 200
    assert reponse.json()["status"] == "validee"


def test_valider_est_idempotent(client, db_session):
    beneficiaire = _beneficiaire(db_session)
    declaration = _en_attente(db_session, beneficiaire.id)
    client.post(f"{_URL}/{declaration.id}/validate")

    reponse = client.post(f"{_URL}/{declaration.id}/validate")

    assert reponse.status_code == 200
    assert reponse.json()["status"] == "validee"


def test_valider_un_id_inconnu_rend_404(client):
    assert client.post(f"{_URL}/999999/validate").status_code == 404


def test_valider_sans_le_pouvoir_rend_403(client, db_session):
    beneficiaire = _beneficiaire(db_session)
    declaration = _en_attente(db_session, beneficiaire.id)
    _session_etroite(client, db_session)

    assert client.post(f"{_URL}/{declaration.id}/validate").status_code == 403


def test_valider_journalise_ladmin_action_log(client, db_session):
    beneficiaire = _beneficiaire(db_session)
    declaration = _en_attente(db_session, beneficiaire.id)

    client.post(f"{_URL}/{declaration.id}/validate")

    entree = db_session.query(AdminActionLog).one()
    assert entree.action == "volunteer_declaration.validate"
    assert entree.entity_id == declaration.id


# --- Suppression (US4) --------------------------------------------------------


def test_supprimer_retire_la_declaration_de_nimporte_quel_membre(client, db_session):
    beneficiaire = _beneficiaire(db_session)
    declaration = _en_attente(db_session, beneficiaire.id)

    reponse = client.delete(f"{_URL}/{declaration.id}")

    assert reponse.status_code == 204
    assert volunteer_declaration_repository.get(db_session, declaration.id) is None


def test_supprimer_journalise_ladmin_action_log(client, db_session):
    beneficiaire = _beneficiaire(db_session)
    declaration = _en_attente(db_session, beneficiaire.id)

    client.delete(f"{_URL}/{declaration.id}")

    entree = db_session.query(AdminActionLog).one()
    assert entree.action == "volunteer_declaration.delete"


def test_supprimer_un_id_inconnu_rend_404(client):
    reponse = client.delete(f"{_URL}/999999")

    assert reponse.status_code == 404


def test_supprimer_sans_le_pouvoir_rend_403(client, db_session):
    beneficiaire = _beneficiaire(db_session)
    declaration = _en_attente(db_session, beneficiaire.id)
    _session_etroite(client, db_session)

    reponse = client.delete(f"{_URL}/{declaration.id}")

    assert reponse.status_code == 403


# --- Vue d'ensemble (US5) ------------------------------------------------------


def test_lister_rend_les_declarations_de_tous_les_membres(client, db_session):
    beneficiaire = _beneficiaire(db_session)
    autre = _beneficiaire(db_session, "autre@exemple.fr")
    _en_attente(db_session, beneficiaire.id)
    volunteer_declaration_repository.create(
        db_session,
        title="Validée",
        description="D",
        beneficiary_user_id=autre.id,
        author_user_id=autre.id,
        status="validee",
    )
    db_session.commit()

    reponse = client.get(_URL)

    assert reponse.status_code == 200
    assert len(reponse.json()) == 2


def test_lister_rend_lidentite_du_beneficiaire(client, db_session):
    beneficiaire = user_repository.create(
        db_session, email="jean@exemple.fr", display_name="Jean Dupont"
    )
    db_session.flush()
    _en_attente(db_session, beneficiaire.id)

    corps = client.get(_URL).json()[0]

    assert corps["beneficiary_email"] == "jean@exemple.fr"
    assert corps["beneficiary_display_name"] == "Jean Dupont"


def test_lister_avec_le_pouvoir_read_seul_rend_200(client, db_session):
    _session_etroite(client, db_session, P.BENEVOLAT_READ)

    assert client.get(_URL).status_code == 200


def test_lister_sans_aucun_pouvoir_rend_403(client, db_session):
    _session_etroite(client, db_session)

    assert client.get(_URL).status_code == 403


def test_supprimee_disparait_de_la_vue_densemble(client, db_session):
    """Finding G2 de /speckit-analyze — FR-008 recoupé avec US4."""
    beneficiaire = _beneficiaire(db_session)
    declaration = _en_attente(db_session, beneficiaire.id)

    client.delete(f"{_URL}/{declaration.id}")
    reponse = client.get(_URL)

    assert reponse.json() == []
