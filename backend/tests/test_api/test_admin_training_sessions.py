"""Le calendrier des entraînements jeunes (#868, epic #863).

`tests/test_api/conftest.py` ouvre une session **superutilisateur** pour
chaque test de ce dossier : les gardes elles-mêmes sont éprouvées à part,
`_session_avec` ci-dessous posant un rôle qui ne porte que les pouvoirs
demandés — même patron que `test_admin_counter_scope.py`.
"""
import pytest

from app.api.v1.auth import session_cookie_name
from app.core.config import get_settings
from app.core.permissions import P
from app.models.organisation import Organisation
from app.models.role_permission import RolePermission
from app.repositories import (
    profile_repository,
    role_repository,
    user_repository,
    user_role_repository,
)
from app.services.auth import session as session_service

BASE = "/api/v1/admin/training-sessions"


@pytest.fixture
def profile_id(db_session) -> int:
    """Un profil jeune réel (#867) — `profile_id` référence `personal_profiles.id`
    depuis le resserrement de la contrainte (merge de #867 dans l'epic)."""
    organisation = db_session.query(Organisation).filter_by(slug="tcn").one()
    profil = profile_repository.create(
        db_session, organisation_id=organisation.id, first_name="Alix", last_name="Martin"
    )
    db_session.commit()
    return profil.id


def _session_avec(client, db_session, *permission_codes: str):
    """Ouvre, sur `client`, une session dont le rôle ne porte que ces pouvoirs."""
    organisation = db_session.query(Organisation).filter_by(slug="tcn").one()
    role = role_repository.create(
        db_session, slug=f"role-{'-'.join(permission_codes) or 'vide'}", name="Rôle de test"
    )
    for code in permission_codes:
        role.permissions.append(RolePermission(permission_code=code))
    db_session.flush()
    user = user_repository.create(db_session, email=f"{'-'.join(permission_codes) or 'anonyme'}@exemple.fr")
    db_session.flush()
    user_role_repository.grant(
        db_session, user_id=user.id, role_id=role.id, organisation_id=organisation.id
    )
    jeton = session_service.open_for(db_session, user)
    db_session.commit()
    client.cookies.set(session_cookie_name(get_settings()), jeton)
    return user


# --- Consultation (US1) -------------------------------------------------------


def test_the_list_comes_out_sorted_by_date(client):
    client.post(BASE, json={"date": "2026-09-27"})
    client.post(BASE, json={"date": "2026-09-20"})

    body = client.get(BASE).json()

    assert [e["date"] for e in body] == ["2026-09-20", "2026-09-27"]


def test_optional_fields_come_out_null_not_missing(client):
    client.post(BASE, json={"date": "2026-09-20"})

    training_session = client.get(BASE).json()[0]

    assert training_session["start_time"] is None
    assert training_session["location"] is None
    assert training_session["session_type"] is None
    assert training_session["participant_count"] == 0


def test_the_detail_lists_its_participants(client, profile_id):
    created = client.post(BASE, json={"date": "2026-09-20"}).json()
    client.post(f"{BASE}/{created['id']}/participants", json={"profile_id": profile_id})

    body = client.get(f"{BASE}/{created['id']}").json()

    assert [p["profile_id"] for p in body["participants"]] == [profile_id]
    assert body["participant_count"] == 1


def test_adding_an_unknown_jeune_returns_404(client):
    """`profile_id` référence `personal_profiles.id` (#867) : un profil inexistant
    est refusé, jamais inscrit silencieusement."""
    created = client.post(BASE, json={"date": "2026-09-20"}).json()

    response = client.post(f"{BASE}/{created['id']}/participants", json={"profile_id": 9999})

    assert response.status_code == 404


def test_an_unknown_entrainement_returns_404(client):
    assert client.get(f"{BASE}/9999").status_code == 404


# --- Création et modification (US2) -------------------------------------------


def test_creating_an_entrainement_with_only_a_date(client):
    response = client.post(BASE, json={"date": "2026-09-20"})

    assert response.status_code == 201
    body = response.json()
    assert body["date"] == "2026-09-20"
    assert body["participants"] == []


def test_creating_without_a_date_is_refused(client):
    assert client.post(BASE, json={}).status_code == 422


def test_updating_only_writes_provided_fields(client):
    created = client.post(
        BASE, json={"date": "2026-09-20", "location": "Base nautique", "session_type": "Natation"}
    ).json()

    response = client.patch(f"{BASE}/{created['id']}", json={"location": "Gymnase"})

    assert response.status_code == 200
    body = response.json()
    assert body["location"] == "Gymnase"
    assert body["session_type"] == "Natation"


def test_updating_an_unknown_entrainement_returns_404(client):
    assert client.patch(f"{BASE}/9999", json={"location": "Gymnase"}).status_code == 404


# --- Participants (US3) --------------------------------------------------------


def test_adding_a_participant_twice_is_idempotent(client, profile_id):
    created = client.post(BASE, json={"date": "2026-09-20"}).json()
    path = f"{BASE}/{created['id']}/participants"

    premiere = client.post(path, json={"profile_id": profile_id})
    seconde = client.post(path, json={"profile_id": profile_id})

    assert premiere.status_code == 201
    assert seconde.status_code == 201
    assert seconde.json()["participant_count"] == 1


def test_removing_a_participant_who_was_not_registered_succeeds(client):
    created = client.post(BASE, json={"date": "2026-09-20"}).json()

    response = client.delete(f"{BASE}/{created['id']}/participants/99")

    assert response.status_code == 204


def test_removing_a_participant_removes_only_this_entrainement(client, profile_id):
    e1 = client.post(BASE, json={"date": "2026-09-20"}).json()
    e2 = client.post(BASE, json={"date": "2026-09-27"}).json()
    client.post(f"{BASE}/{e1['id']}/participants", json={"profile_id": profile_id})
    client.post(f"{BASE}/{e2['id']}/participants", json={"profile_id": profile_id})

    client.delete(f"{BASE}/{e1['id']}/participants/{profile_id}")

    assert client.get(f"{BASE}/{e1['id']}").json()["participant_count"] == 0
    assert client.get(f"{BASE}/{e2['id']}").json()["participant_count"] == 1


def test_adding_a_participant_to_an_unknown_entrainement_returns_404(client):
    assert (
        client.post(f"{BASE}/9999/participants", json={"profile_id": 1}).status_code == 404
    )


# --- Appel de présence (#869) ----------------------------------------------


def test_adding_a_participant_can_mark_it_present_in_the_same_call(client, profile_id):
    created = client.post(BASE, json={"date": "2026-09-20"}).json()

    response = client.post(
        f"{BASE}/{created['id']}/participants", json={"profile_id": profile_id, "present": True}
    )

    assert response.status_code == 201
    participant = response.json()["participants"][0]
    assert participant["present"] is True


def test_a_new_participant_defaults_to_not_yet_pointed(client, profile_id):
    created = client.post(BASE, json={"date": "2026-09-20"}).json()

    response = client.post(f"{BASE}/{created['id']}/participants", json={"profile_id": profile_id})

    assert response.json()["participants"][0]["present"] is None


def test_setting_presence_updates_the_participant(client, profile_id):
    created = client.post(BASE, json={"date": "2026-09-20"}).json()
    client.post(f"{BASE}/{created['id']}/participants", json={"profile_id": profile_id})

    response = client.patch(
        f"{BASE}/{created['id']}/participants/{profile_id}/presence", json={"present": True}
    )

    assert response.status_code == 200
    participant = response.json()["participants"][0]
    assert participant["present"] is True


def test_setting_presence_survives_a_subsequent_get(client, profile_id):
    """SC-002 : le statut posé par le `PATCH` reste identique à une lecture
    ultérieure, indépendante de la réponse du `PATCH` lui-même."""
    created = client.post(BASE, json={"date": "2026-09-20"}).json()
    client.post(f"{BASE}/{created['id']}/participants", json={"profile_id": profile_id})
    client.patch(f"{BASE}/{created['id']}/participants/{profile_id}/presence", json={"present": True})

    relu = client.get(f"{BASE}/{created['id']}").json()

    assert relu["participants"][0]["present"] is True


def test_setting_presence_can_be_corrected(client, profile_id):
    """Seul le dernier statut fait foi (FR-005) — pas d'historique."""
    created = client.post(BASE, json={"date": "2026-09-20"}).json()
    client.post(f"{BASE}/{created['id']}/participants", json={"profile_id": profile_id})
    client.patch(f"{BASE}/{created['id']}/participants/{profile_id}/presence", json={"present": False})

    response = client.patch(
        f"{BASE}/{created['id']}/participants/{profile_id}/presence", json={"present": True}
    )

    assert response.json()["participants"][0]["present"] is True


def test_setting_presence_for_an_unregistered_jeune_returns_404(client, profile_id):
    created = client.post(BASE, json={"date": "2026-09-20"}).json()

    response = client.patch(
        f"{BASE}/{created['id']}/participants/{profile_id}/presence", json={"present": True}
    )

    assert response.status_code == 404


def test_setting_presence_for_an_unknown_entrainement_returns_404(client):
    response = client.patch(f"{BASE}/9999/participants/1/presence", json={"present": True})

    assert response.status_code == 404


def test_the_seance_note_can_be_read_and_updated(client):
    created = client.post(BASE, json={"date": "2026-09-20"}).json()
    assert created["note"] == ""

    response = client.patch(f"{BASE}/{created['id']}", json={"note": "Bassin partagé."})

    assert response.json()["note"] == "Bassin partagé."


# --- Gardes ---------------------------------------------------------------

READS = [("GET", BASE), ("GET", f"{BASE}/1")]
WRITES = [
    ("POST", BASE, {"date": "2026-09-20"}),
    ("PATCH", f"{BASE}/1", {"location": "Gymnase"}),
    ("POST", f"{BASE}/1/participants", {"profile_id": 1}),
    ("DELETE", f"{BASE}/1/participants/1", None),
    ("PATCH", f"{BASE}/1/participants/1/presence", {"present": True}),
]


def test_a_read_resource_refuses_the_anonymous(client):
    client.cookies.clear()
    for method, path in READS:
        assert client.request(method, path).status_code == 401


def test_a_read_resource_refuses_a_session_without_privilege(client, db_session):
    _session_avec(client, db_session)
    for method, path in READS:
        assert client.request(method, path).status_code == 403


def test_jeunes_read_alone_passes_reads_but_not_writes(client, db_session):
    _session_avec(client, db_session, str(P.JEUNES_READ))

    for method, path in READS:
        assert client.request(method, path).status_code in (200, 404)
    for method, path, body in WRITES:
        assert client.request(method, path, json=body).status_code == 403


def test_a_write_resource_refuses_the_anonymous(client):
    client.cookies.clear()
    for method, path, body in WRITES:
        assert client.request(method, path, json=body).status_code == 401


def test_a_write_resource_refuses_a_session_without_privilege(client, db_session):
    _session_avec(client, db_session)
    for method, path, body in WRITES:
        assert client.request(method, path, json=body).status_code == 403


def test_jeunes_write_alone_does_not_pass_reads(client, db_session):
    """`jeunes:read` et `jeunes:write` sont deux pouvoirs réellement distincts,
    sur le même patron que `groups:write`/`groups:read` (#197)."""
    _session_avec(client, db_session, str(P.JEUNES_WRITE))

    assert client.get(BASE).status_code == 403


def test_jeunes_read_and_write_together_pass_the_full_flow(client, db_session, profile_id):
    created = client.post(BASE, json={"date": "2026-09-20"}).json()
    _session_avec(client, db_session, str(P.JEUNES_READ), str(P.JEUNES_WRITE))

    assert client.get(BASE).status_code == 200
    assert client.get(f"{BASE}/{created['id']}").status_code == 200
    patched = client.patch(f"{BASE}/{created['id']}", json={"location": "Gymnase"})
    assert patched.status_code == 200
    enrolled = client.post(f"{BASE}/{created['id']}/participants", json={"profile_id": profile_id})
    assert enrolled.status_code == 201
    unenrolled = client.delete(f"{BASE}/{created['id']}/participants/{profile_id}")
    assert unenrolled.status_code == 204
