"""API des retours utilisateurs (#267) — contracts/feedback-api.md."""
from app.core.config import get_settings
from app.repositories import feedback_repository

_URL = "/api/v1/admin/feedback"


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
