"""Le calendrier des entraînements jeunes (#868, epic #863).

`tests/test_api/conftest.py` ouvre une session **superutilisateur** pour
chaque test de ce dossier : les gardes elles-mêmes sont éprouvées à part,
`_session_avec` ci-dessous posant un rôle qui ne porte que les pouvoirs
demandés — même patron que `test_admin_counter_scope.py`.
"""
from app.api.v1.auth import session_cookie_name
from app.core.config import get_settings
from app.core.permissions import P
from app.models.organisation import Organisation
from app.models.role_permission import RolePermission
from app.repositories import role_repository, user_repository, user_role_repository
from app.services.auth import session as session_service

BASE = "/api/v1/admin/jeunes/entrainements"


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

    entrainement = client.get(BASE).json()[0]

    assert entrainement["heure_debut"] is None
    assert entrainement["lieu"] is None
    assert entrainement["type_seance"] is None
    assert entrainement["participant_count"] == 0


def test_the_detail_lists_its_participants(client):
    created = client.post(BASE, json={"date": "2026-09-20"}).json()
    client.post(f"{BASE}/{created['id']}/participants", json={"jeune_id": 42})

    body = client.get(f"{BASE}/{created['id']}").json()

    assert [p["jeune_id"] for p in body["participants"]] == [42]
    assert body["participant_count"] == 1


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
        BASE, json={"date": "2026-09-20", "lieu": "Base nautique", "type_seance": "Natation"}
    ).json()

    response = client.patch(f"{BASE}/{created['id']}", json={"lieu": "Gymnase"})

    assert response.status_code == 200
    body = response.json()
    assert body["lieu"] == "Gymnase"
    assert body["type_seance"] == "Natation"


def test_updating_an_unknown_entrainement_returns_404(client):
    assert client.patch(f"{BASE}/9999", json={"lieu": "Gymnase"}).status_code == 404


# --- Participants (US3) --------------------------------------------------------


def test_adding_a_participant_twice_is_idempotent(client):
    created = client.post(BASE, json={"date": "2026-09-20"}).json()
    path = f"{BASE}/{created['id']}/participants"

    premiere = client.post(path, json={"jeune_id": 42})
    seconde = client.post(path, json={"jeune_id": 42})

    assert premiere.status_code == 201
    assert seconde.status_code == 201
    assert seconde.json()["participant_count"] == 1


def test_removing_a_participant_who_was_not_registered_succeeds(client):
    created = client.post(BASE, json={"date": "2026-09-20"}).json()

    response = client.delete(f"{BASE}/{created['id']}/participants/99")

    assert response.status_code == 204


def test_removing_a_participant_removes_only_this_entrainement(client):
    e1 = client.post(BASE, json={"date": "2026-09-20"}).json()
    e2 = client.post(BASE, json={"date": "2026-09-27"}).json()
    client.post(f"{BASE}/{e1['id']}/participants", json={"jeune_id": 42})
    client.post(f"{BASE}/{e2['id']}/participants", json={"jeune_id": 42})

    client.delete(f"{BASE}/{e1['id']}/participants/42")

    assert client.get(f"{BASE}/{e1['id']}").json()["participant_count"] == 0
    assert client.get(f"{BASE}/{e2['id']}").json()["participant_count"] == 1


def test_adding_a_participant_to_an_unknown_entrainement_returns_404(client):
    assert (
        client.post(f"{BASE}/9999/participants", json={"jeune_id": 1}).status_code == 404
    )


# --- Gardes ---------------------------------------------------------------

READS = [("GET", BASE), ("GET", f"{BASE}/1")]
WRITES = [
    ("POST", BASE, {"date": "2026-09-20"}),
    ("PATCH", f"{BASE}/1", {"lieu": "Gymnase"}),
    ("POST", f"{BASE}/1/participants", {"jeune_id": 1}),
    ("DELETE", f"{BASE}/1/participants/1", None),
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


def test_jeunes_read_and_write_together_pass_the_full_flow(client, db_session):
    created = client.post(BASE, json={"date": "2026-09-20"}).json()
    _session_avec(client, db_session, str(P.JEUNES_READ), str(P.JEUNES_WRITE))

    assert client.get(BASE).status_code == 200
    assert client.get(f"{BASE}/{created['id']}").status_code == 200
    assert client.patch(f"{BASE}/{created['id']}", json={"lieu": "Gymnase"}).status_code == 200
    assert (
        client.post(f"{BASE}/{created['id']}/participants", json={"jeune_id": 1}).status_code
        == 201
    )
    assert (
        client.delete(f"{BASE}/{created['id']}/participants/1").status_code == 204
    )
