"""API des retours utilisateurs (#267) — contracts/feedback-api.md."""
from app.api.v1.auth import session_cookie_name
from app.core.config import get_settings
from app.core.permissions import P
from app.models.organisation import Organisation
from app.models.role_permission import RolePermission
from app.repositories import (
    feedback_repository,
    role_repository,
    user_repository,
    user_role_repository,
)
from app.services.auth import session as session_service

_URL = "/api/v1/admin/feedback"


def _session_etroite(client, db_session, *codes):
    """Ce fichier vit sous `tests/test_api/` : la session de saisie du conftest
    local est superutilisateur. Un test de refus a besoin d'une session plus
    étroite pour l'écraser — même patron que `test_course_reliability_api.py`."""
    organisation = db_session.query(Organisation).first()
    user = user_repository.create(db_session, email="etroit@exemple.fr")
    db_session.flush()
    if codes:
        role = role_repository.create(db_session, slug="etroit-feedback", name="Étroit")
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


def _payload(**overrides):
    defaults = {"type": "bug", "title": "Un titre", "body": "Une description."}
    return {**defaults, **overrides}


def test_soumission_publique_sans_session_repond_201(client):
    client.cookies.clear()

    reponse = client.post(_URL, json=_payload())

    assert reponse.status_code == 201
    assert reponse.json()["status"] == "nouveau"


def test_soumission_sans_session_ne_porte_aucune_identite(client, db_session):
    client.cookies.clear()

    reponse = client.post(_URL, json=_payload())

    entry = feedback_repository.get(db_session, reponse.json()["id"])
    assert entry.user_id is None


def test_soumission_connectee_associe_lauteur(client, db_session):
    # `session_de_saisie` (autouse) a déjà ouvert une session superutilisateur.
    reponse = client.post(_URL, json=_payload())

    entry = feedback_repository.get(db_session, reponse.json()["id"])
    assert entry.user_id is not None


def test_titre_vide_rend_422(client):
    assert client.post(_URL, json=_payload(title="")).status_code == 422


def test_titre_trop_long_rend_422(client):
    assert client.post(_URL, json=_payload(title="x" * 201)).status_code == 422


def test_corps_vide_rend_422(client):
    assert client.post(_URL, json=_payload(body="")).status_code == 422


def test_type_inconnu_rend_422(client):
    assert client.post(_URL, json=_payload(type="autre")).status_code == 422


def test_honeypot_rempli_repond_201_sans_persister(client, db_session):
    client.cookies.clear()

    reponse = client.post(_URL, json=_payload(honeypot="je-suis-un-bot"))

    assert reponse.status_code == 201
    assert feedback_repository.list_sorted(db_session) == []


def test_debit_depasse_rend_429(client, monkeypatch):
    client.cookies.clear()
    monkeypatch.setattr(get_settings(), "feedback_rate_limit_max_per_window", 2)

    client.post(_URL, json=_payload())
    client.post(_URL, json=_payload())
    reponse = client.post(_URL, json=_payload())

    assert reponse.status_code == 429
    assert "réessayez" in reponse.json()["detail"]


# --- Consultation de la liste (US2) ------------------------------------------


def test_lister_rend_les_signalements(client, db_session):
    feedback_repository.create(db_session, type="bug", title="Un bug", body="Détail")
    db_session.commit()

    reponse = client.get(_URL)

    assert reponse.status_code == 200
    titres = [ligne["title"] for ligne in reponse.json()]
    assert "Un bug" in titres


def test_lister_ne_rend_jamais_lip(client, db_session):
    feedback_repository.create(
        db_session, type="bug", title="Un bug", body="Détail", ip_address="203.0.113.1"
    )
    db_session.commit()

    ligne = client.get(_URL).json()[0]

    assert "ip_address" not in ligne


def test_lister_respecte_le_tri_demande(client, db_session):
    feedback_repository.create(db_session, type="feedback", title="F", body="x")
    feedback_repository.create(db_session, type="bug", title="B", body="x")
    db_session.commit()

    reponse = client.get(_URL, params={"sort": "type", "order": "asc"})

    assert [ligne["type"] for ligne in reponse.json()] == ["bug", "feedback"]


def test_lister_sans_le_pouvoir_rend_403(client, db_session):
    _session_etroite(client, db_session)

    assert client.get(_URL).status_code == 403


def test_lister_avec_le_pouvoir_rend_200(client, db_session):
    _session_etroite(client, db_session, P.FEEDBACK_READ)

    assert client.get(_URL).status_code == 200
