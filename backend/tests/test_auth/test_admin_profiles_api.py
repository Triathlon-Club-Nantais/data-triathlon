"""Les cinq ressources de `/api/v1/admin/profiles` (#867, epic #863).

Trois volets : lecture (US1/US2), écriture (US3), journal de bord (US4), plus
les gardes de chacun. Patron `test_admin_groups_api.py`.
"""
import pytest

from app.core.permissions import P

BASE = "/api/v1/admin/profiles"


@pytest.fixture
def profile(client, ouvrir_session):
    """Un profil créé par l'API, cookie laissé sur une session pleine (lecture
    et écriture) pour que le test qui suit puisse enchaîner un `GET`."""
    ouvrir_session(P.JEUNES_READ, P.JEUNES_WRITE)
    response = client.post(BASE, json={"first_name": "Alix", "last_name": "Martin"})
    assert response.status_code == 201
    return response.json()


# --- US1/US2, volet lecture --------------------------------------------------


def test_the_list_comes_out_sorted_by_last_name(client, ouvrir_session):
    ouvrir_session(P.JEUNES_WRITE)
    client.post(BASE, json={"first_name": "Alix", "last_name": "Roux"})
    client.post(BASE, json={"first_name": "Zoé", "last_name": "Dupont"})
    ouvrir_session(P.JEUNES_READ)

    body = client.get(BASE).json()

    assert [p["last_name"] for p in body] == ["Dupont", "Roux"]
    assert "log_entries" not in body[0]


def test_the_detail_carries_the_empty_journal_of_a_fresh_profile(client, profile):
    body = client.get(f"{BASE}/{profile['id']}").json()

    assert body["log_entries"] == []
    assert body["emergency_contact"] == ""
    assert body["notes"] == ""


def test_an_unknown_profile_returns_404(client, ouvrir_session):
    ouvrir_session(P.JEUNES_READ)

    assert client.get(f"{BASE}/9999").status_code == 404


@pytest.mark.parametrize("path", [BASE, f"{BASE}/1"])
def test_a_read_refuses_the_anonymous(client, path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("path", [BASE, f"{BASE}/1"])
def test_a_read_refuses_a_session_without_privilege(client, ouvrir_session, path):
    ouvrir_session()

    assert client.get(path).status_code == 403


def test_jeunes_write_alone_does_not_pass_reading(client, ouvrir_session):
    """Les deux pouvoirs sont réellement distincts : écrire n'est pas consulter."""
    ouvrir_session(P.JEUNES_WRITE)

    assert client.get(BASE).status_code == 403


# --- US3, volet écriture ------------------------------------------------------


def test_a_profile_is_created_with_minimal_fields(client, ouvrir_session):
    ouvrir_session(P.JEUNES_WRITE)

    response = client.post(BASE, json={"first_name": "Alix", "last_name": "Martin"})

    assert response.status_code == 201
    body = response.json()
    assert body["first_name"] == "Alix"
    assert body["organisation_id"] is not None
    assert body["log_entries"] == []


def test_an_empty_first_name_is_refused(client, ouvrir_session):
    ouvrir_session(P.JEUNES_WRITE)

    response = client.post(BASE, json={"first_name": "", "last_name": "Martin"})

    assert response.status_code == 422


def test_updating_a_profile_changes_only_the_given_field(client, ouvrir_session, profile):
    ouvrir_session(P.JEUNES_WRITE)

    response = client.patch(
        f"{BASE}/{profile['id']}", json={"emergency_contact": "Mère — 06 00 00 00 00"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["emergency_contact"] == "Mère — 06 00 00 00 00"
    assert body["first_name"] == "Alix"


def test_updating_an_unknown_profile_returns_404(client, ouvrir_session):
    ouvrir_session(P.JEUNES_WRITE)

    response = client.patch(f"{BASE}/9999", json={"notes": "x"})

    assert response.status_code == 404


WRITES = [
    ("POST", BASE, {"first_name": "X", "last_name": "Y"}),
    ("PATCH", f"{BASE}/1", {"notes": "x"}),
    ("POST", f"{BASE}/1/log-entries", {"text": "x"}),
]


@pytest.mark.parametrize(("method", "path", "body"), WRITES)
def test_a_write_resource_refuses_the_anonymous(client, method, path, body):
    response = client.request(method, path, json=body)

    assert response.status_code == 401


@pytest.mark.parametrize(("method", "path", "body"), WRITES)
def test_a_write_resource_refuses_a_session_without_privilege(
    client, ouvrir_session, method, path, body
):
    ouvrir_session()

    response = client.request(method, path, json=body)

    assert response.status_code == 403


@pytest.mark.parametrize(("method", "path", "body"), WRITES)
def test_jeunes_read_alone_does_not_pass_any_write(client, ouvrir_session, method, path, body):
    ouvrir_session(P.JEUNES_READ)

    response = client.request(method, path, json=body)

    assert response.status_code == 403


# --- US4, volet journal de bord -----------------------------------------------


def test_adding_a_log_entry_makes_it_appear_first(client, ouvrir_session, profile):
    ouvrir_session(P.JEUNES_WRITE)

    response = client.post(
        f"{BASE}/{profile['id']}/log-entries",
        json={"text": "Première séance, bon niveau natation."},
    )

    assert response.status_code == 201
    entries = response.json()["log_entries"]
    assert entries[0]["text"] == "Première séance, bon niveau natation."


def test_several_log_entries_all_remain_visible(client, ouvrir_session, profile):
    """FR-006 — aucune entrée n'écrase la précédente."""
    ouvrir_session(P.JEUNES_WRITE)
    path = f"{BASE}/{profile['id']}/log-entries"

    client.post(path, json={"text": "Première entrée"})
    response = client.post(path, json={"text": "Seconde entrée"})

    texts = [entry["text"] for entry in response.json()["log_entries"]]
    assert texts == ["Seconde entrée", "Première entrée"]


def test_an_empty_log_entry_text_is_refused(client, ouvrir_session, profile):
    ouvrir_session(P.JEUNES_WRITE)

    response = client.post(f"{BASE}/{profile['id']}/log-entries", json={"text": "  "})

    assert response.status_code == 422


def test_a_log_entry_on_an_unknown_profile_returns_404(client, ouvrir_session):
    ouvrir_session(P.JEUNES_WRITE)

    response = client.post(f"{BASE}/9999/log-entries", json={"text": "x"})

    assert response.status_code == 404


def test_the_log_entry_author_is_named(client, ouvrir_session, profile):
    actor = ouvrir_session(P.JEUNES_WRITE, nom="Encadrant Un")

    response = client.post(
        f"{BASE}/{profile['id']}/log-entries", json={"text": "Note de séance"}
    )

    assert response.json()["log_entries"][0]["created_by_name"] == "Encadrant Un"
    assert actor.display_name == "Encadrant Un"


def test_timestamps_are_serialized_as_utc(client, ouvrir_session, profile):
    """Colonnes naïves en UTC : sans suffixe `Z`, le client les lirait comme
    une heure locale (même sérialiseur que `ParticipantRead`)."""
    ouvrir_session(P.JEUNES_READ, P.JEUNES_WRITE)
    client.post(f"{BASE}/{profile['id']}/log-entries", json={"text": "Bonne séance"})

    detail = client.get(f"{BASE}/{profile['id']}").json()
    liste = client.get(BASE).json()

    assert detail["created_at"].endswith("Z")
    assert detail["log_entries"][0]["created_at"].endswith("Z")
    assert liste[0]["created_at"].endswith("Z")
