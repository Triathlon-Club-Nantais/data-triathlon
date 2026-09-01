"""API admin du workflow de validation des actions de bénévolat (#779) —
contracts/admin-volunteer-actions-api.md.

`session_de_saisie` (autouse, `tests/test_api/conftest.py`) ouvre une session
superutilisateur — les tests de refus utilisent `_session_etroite` pour
l'écraser (patron `test_admin_volunteer_declarations_api.py`).
"""
from app.api.v1.auth import session_cookie_name
from app.core.config import get_settings
from app.models.organisation import Organisation
from app.models.role_permission import RolePermission
from app.repositories import (
    athlete_repository,
    role_repository,
    user_repository,
    user_role_repository,
    volunteer_action_repository,
)
from app.services.auth import session as session_service

_URL = "/api/v1/admin/volunteer-actions"


def _session_etroite(client, db_session, *codes):
    organisation = db_session.query(Organisation).first()
    user = user_repository.create(db_session, email="etroit@exemple.fr")
    db_session.flush()
    if codes:
        role = role_repository.create(db_session, slug="etroit-quota", name="Étroit")
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


def _athlete(db_session, nom="DUPONT"):
    athlete = athlete_repository.get_or_create(db_session, nom=nom, prenom="Jean", club="TCN")
    db_session.flush()
    return athlete


def _declaration(db_session, *, status="en_attente", auteur_id=None):
    athlete = _athlete(db_session)
    if auteur_id is None:
        auteur = user_repository.create(db_session, email="adherent@exemple.fr")
        db_session.flush()
        auteur_id = auteur.id
    action = volunteer_action_repository.create_pending(
        db_session, athlete_id=athlete.id, season=2025, declared_by_user_id=auteur_id,
        title="Ravitaillement", description="Poste eau.",
    )
    db_session.flush()
    if status != "en_attente":
        volunteer_action_repository.set_status(db_session, action.id, status)
    db_session.commit()
    return athlete, action


# --- File d'attente (US1) ----------------------------------------------------


def test_lister_ne_rend_que_les_declarations_en_attente(client, db_session):
    _, en_attente = _declaration(db_session)
    _declaration(db_session, status="validee")

    reponse = client.get(f"{_URL}/pending")

    corps = reponse.json()
    assert [d["id"] for d in corps] == [en_attente.id]


def test_lister_rend_null_pour_une_ligne_creee_par_le_chemin_admin(client, db_session):
    """Chemin admin existant (#709) — jamais de titre ni de description."""
    athlete = _athlete(db_session)
    auteur = user_repository.create(db_session, email="admin@exemple.fr")
    db_session.flush()
    action = volunteer_action_repository.create(
        db_session, athlete_id=athlete.id, season=2025, declared_by_user_id=auteur.id
    )
    db_session.commit()

    reponse = client.get(f"{_URL}/pending")

    corps = next(d for d in reponse.json() if d["id"] == action.id)
    assert corps["title"] is None
    assert corps["description"] is None


def test_lister_sans_le_pouvoir_rend_403(client, db_session):
    _session_etroite(client, db_session)

    assert client.get(f"{_URL}/pending").status_code == 403


# --- Accepter (US2) -----------------------------------------------------------


def test_accepter_fait_passer_en_attente_a_validee(client, db_session):
    _, action = _declaration(db_session)

    reponse = client.post(f"{_URL}/{action.id}/accept")

    assert reponse.status_code == 200
    assert reponse.json()["status"] == "validee"


def test_accepter_credite_le_quota_de_saison(client, db_session):
    athlete, action = _declaration(db_session)

    client.post(f"{_URL}/{action.id}/accept")

    quota = client.get(f"/api/v1/admin/athletes/{athlete.id}/season-quota", params={"season": 2025})
    assert quota.json()["has_volunteer_action"] is True


def test_accepter_un_id_inconnu_rend_404(client):
    assert client.post(f"{_URL}/999999/accept").status_code == 404


def test_accepter_sans_le_pouvoir_rend_403(client, db_session):
    _, action = _declaration(db_session)
    _session_etroite(client, db_session)

    assert client.post(f"{_URL}/{action.id}/accept").status_code == 403


# --- Refuser (US3) -------------------------------------------------------------


def test_refuser_depuis_en_attente(client, db_session):
    _, action = _declaration(db_session)

    reponse = client.post(f"{_URL}/{action.id}/reject")

    assert reponse.status_code == 200
    assert reponse.json()["status"] == "refusee"


def test_refuser_depuis_validee(client, db_session):
    _, action = _declaration(db_session, status="validee")

    reponse = client.post(f"{_URL}/{action.id}/reject")

    assert reponse.json()["status"] == "refusee"


def test_refuser_retire_le_credit_du_quota_de_saison(client, db_session):
    """Seule ligne validée de l'athlète/saison — le refus la retire du quota."""
    athlete, action = _declaration(db_session, status="validee")

    client.post(f"{_URL}/{action.id}/reject")

    quota = client.get(f"/api/v1/admin/athletes/{athlete.id}/season-quota", params={"season": 2025})
    assert quota.json()["has_volunteer_action"] is False


def test_refuser_sans_le_pouvoir_rend_403(client, db_session):
    """`/speckit-analyze` finding E1 — FR-007 non testé sur ce chemin jusqu'ici."""
    _, action = _declaration(db_session)
    _session_etroite(client, db_session)

    assert client.post(f"{_URL}/{action.id}/reject").status_code == 403
