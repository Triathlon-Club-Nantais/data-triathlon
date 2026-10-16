"""API publique de soumission d'un signalement (#267) — contracts/feedback-api.md.

Miroir du découpage des routers : la soumission est publique et vit sous
`/feedback`, son instruction est gardée et vit sous `/admin/feedback`
(`test_admin_feedback_api.py`).
"""
from app.core.config import get_settings
from app.repositories import feedback_repository

_URL = "/api/v1/feedback"


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


def test_page_url_trop_longue_rend_422(client):
    assert client.post(_URL, json=_payload(page_url="x" * 2001)).status_code == 422


def test_user_agent_trop_long_rend_422(client):
    assert client.post(_URL, json=_payload(user_agent="x" * 501)).status_code == 422


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


def test_a_forged_leading_forwarded_entry_does_not_bypass_the_limit(client, monkeypatch):
    """#1533: Cloudflare appends to `X-Forwarded-For`, so its leading entry is
    whatever the caller wrote. Measured on production on 2026-10-16, 32 calls
    with a different leading entry never hit a limit of 30.
    """
    client.cookies.clear()
    monkeypatch.setattr(get_settings(), "feedback_rate_limit_max_per_window", 2)

    def send(forged: str):
        chain = f"{forged},90.49.125.30, 172.71.119.62, 10.28.198.73"
        return client.post(_URL, json=_payload(), headers={"X-Forwarded-For": chain})

    assert send("198.51.100.1").status_code == 201
    assert send("198.51.100.2").status_code == 201
    assert send("198.51.100.3").status_code == 429


def test_the_stored_ip_is_the_one_cloudflare_saw(client, db_session):
    client.cookies.clear()

    chain = "203.0.113.7,90.49.125.30, 172.71.119.62, 10.28.198.73"
    reponse = client.post(_URL, json=_payload(), headers={"X-Forwarded-For": chain})

    entry = feedback_repository.get(db_session, reponse.json()["id"])
    assert entry.ip_address == "90.49.125.30"


def test_an_ipv6_64_counts_as_one_sender(client, monkeypatch, db_session):
    """#1552: the count and the stored value both key on the /64."""
    client.cookies.clear()
    monkeypatch.setattr(get_settings(), "feedback_rate_limit_max_per_window", 1)

    def send(ip: str):
        chain = f"{ip}, 172.71.119.62, 10.28.198.73"
        return client.post(_URL, json=_payload(), headers={"X-Forwarded-For": chain})

    first = send("2001:db8:1:2::1")
    assert first.status_code == 201
    assert send("2001:db8:1:2::2").status_code == 429
    entry = feedback_repository.get(db_session, first.json()["id"])
    assert entry.ip_address == "2001:db8:1:2::/64"


def test_la_soumission_ne_vit_pas_sous_admin(client):
    """La revue de #315 : un verbe public sous `/admin` se lit comme une garde
    oubliée. Plus aucun POST n'y répond.

    `405` et non `404` : le chemin existe toujours pour `GET`, seul le verbe a
    disparu — c'est exactement ce qu'on veut prouver, la ressource reste sous
    `/admin` pour tout ce qui est gardé.
    """
    client.cookies.clear()

    assert client.post("/api/v1/admin/feedback", json=_payload()).status_code == 405


def test_une_demande_de_retrait_de_donnees_est_un_type_a_part(client, db_session):
    """#334 : le canal du droit d'opposition, distinct des bugs et des suggestions."""
    reponse = client.post(_URL, json=_payload(type="retrait"))

    assert reponse.status_code == 201
    assert feedback_repository.list_sorted(db_session)[0].type == "retrait"
