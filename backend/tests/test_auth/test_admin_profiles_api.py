"""Les cinq ressources de `/api/v1/admin/profiles` (#867, epic #863).

Trois volets : lecture (US1/US2), écriture (US3), journal de bord (US4), plus
les gardes de chacun. Patron `test_admin_groups_api.py`.
"""
from datetime import date, datetime

import pytest

from app.core.permissions import P
from app.repositories import training_session_repository
from app.services import profile_service
from app.services.fftri_category import fftri_category

BASE = "/api/v1/admin/profiles"


@pytest.fixture
def profile(client, ouvrir_session):
    """Un profil créé par l'API, cookie laissé sur une session pleine (lecture
    et écriture) pour que le test qui suit puisse enchaîner un `GET`."""
    ouvrir_session(P.YOUTH_READ, P.YOUTH_WRITE)
    response = client.post(BASE, json={"first_name": "Alix", "last_name": "Martin"})
    assert response.status_code == 201
    return response.json()


# --- US1/US2, volet lecture --------------------------------------------------


def test_the_list_comes_out_sorted_by_last_name(client, ouvrir_session):
    ouvrir_session(P.YOUTH_WRITE)
    client.post(BASE, json={"first_name": "Alix", "last_name": "Roux"})
    client.post(BASE, json={"first_name": "Zoé", "last_name": "Dupont"})
    ouvrir_session(P.YOUTH_READ)

    body = client.get(BASE).json()

    assert [p["last_name"] for p in body] == ["Dupont", "Roux"]
    assert "log_entries" not in body[0]


def test_the_detail_carries_the_empty_journal_of_a_fresh_profile(client, profile):
    body = client.get(f"{BASE}/{profile['id']}").json()

    assert body["log_entries"] == []
    assert body["emergency_contact"] == ""
    assert body["notes"] == ""


def test_an_unknown_profile_returns_404(client, ouvrir_session):
    ouvrir_session(P.YOUTH_READ)

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
    ouvrir_session(P.YOUTH_WRITE)

    assert client.get(BASE).status_code == 403


# --- US3, volet écriture ------------------------------------------------------


def test_a_profile_is_created_with_minimal_fields(client, ouvrir_session):
    ouvrir_session(P.YOUTH_READ, P.YOUTH_WRITE)

    response = client.post(BASE, json={"first_name": "Alix", "last_name": "Martin"})

    assert response.status_code == 201
    body = response.json()
    assert body["first_name"] == "Alix"
    assert body["organisation_id"] is not None
    assert body["log_entries"] == []


def test_an_empty_first_name_is_refused(client, ouvrir_session):
    ouvrir_session(P.YOUTH_WRITE)

    response = client.post(BASE, json={"first_name": "", "last_name": "Martin"})

    assert response.status_code == 422


def test_updating_a_profile_changes_only_the_given_field(client, ouvrir_session, profile):
    ouvrir_session(P.YOUTH_READ, P.YOUTH_WRITE)

    response = client.patch(
        f"{BASE}/{profile['id']}", json={"emergency_contact": "Mère — 06 00 00 00 00"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["emergency_contact"] == "Mère — 06 00 00 00 00"
    assert body["first_name"] == "Alix"


def test_the_membership_end_is_set_then_cleared(client, ouvrir_session, profile):
    """#1158 : la fin d'adhésion fait courir la purge ; une saisie erronée doit pouvoir s'effacer."""
    ouvrir_session(P.YOUTH_READ, P.YOUTH_WRITE)
    assert client.get(f"{BASE}/{profile['id']}").json()["membership_ended_on"] is None

    posee = client.patch(f"{BASE}/{profile['id']}", json={"membership_ended_on": "2026-06-30"})
    assert posee.json()["membership_ended_on"] == "2026-06-30"

    autre_champ = client.patch(f"{BASE}/{profile['id']}", json={"notes": "x"})
    assert autre_champ.json()["membership_ended_on"] == "2026-06-30"

    effacee = client.patch(f"{BASE}/{profile['id']}", json={"membership_ended_on": None})
    assert effacee.json()["membership_ended_on"] is None


def test_updating_an_unknown_profile_returns_404(client, ouvrir_session):
    ouvrir_session(P.YOUTH_WRITE)

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
    ouvrir_session(P.YOUTH_READ)

    response = client.request(method, path, json=body)

    assert response.status_code == 403


# --- US4, volet journal de bord -----------------------------------------------


def test_adding_a_log_entry_makes_it_appear_first(client, ouvrir_session, profile):
    ouvrir_session(P.YOUTH_READ, P.YOUTH_WRITE)

    response = client.post(
        f"{BASE}/{profile['id']}/log-entries",
        json={"text": "Première séance, bon niveau natation."},
    )

    assert response.status_code == 201
    entries = response.json()["log_entries"]
    assert entries[0]["text"] == "Première séance, bon niveau natation."


def test_several_log_entries_all_remain_visible(client, ouvrir_session, profile):
    """FR-006 — aucune entrée n'écrase la précédente."""
    ouvrir_session(P.YOUTH_READ, P.YOUTH_WRITE)
    path = f"{BASE}/{profile['id']}/log-entries"

    client.post(path, json={"text": "Première entrée"})
    response = client.post(path, json={"text": "Seconde entrée"})

    texts = [entry["text"] for entry in response.json()["log_entries"]]
    assert texts == ["Seconde entrée", "Première entrée"]


def test_an_empty_log_entry_text_is_refused(client, ouvrir_session, profile):
    ouvrir_session(P.YOUTH_WRITE)

    response = client.post(f"{BASE}/{profile['id']}/log-entries", json={"text": "  "})

    assert response.status_code == 422


def test_a_log_entry_on_an_unknown_profile_returns_404(client, ouvrir_session):
    ouvrir_session(P.YOUTH_WRITE)

    response = client.post(f"{BASE}/9999/log-entries", json={"text": "x"})

    assert response.status_code == 404


def test_the_log_entry_author_is_named(client, ouvrir_session, profile):
    actor = ouvrir_session(P.YOUTH_READ, P.YOUTH_WRITE, nom="Encadrant Un")

    response = client.post(
        f"{BASE}/{profile['id']}/log-entries", json={"text": "Note de séance"}
    )

    assert response.json()["log_entries"][0]["created_by_name"] == "Encadrant Un"
    assert actor.display_name == "Encadrant Un"


def test_timestamps_are_serialized_as_utc(client, ouvrir_session, profile):
    """Colonnes naïves en UTC : sans suffixe `Z`, le client les lirait comme
    une heure locale (même sérialiseur que `ParticipantRead`)."""
    ouvrir_session(P.YOUTH_READ, P.YOUTH_WRITE)
    client.post(f"{BASE}/{profile['id']}/log-entries", json={"text": "Bonne séance"})

    detail = client.get(f"{BASE}/{profile['id']}").json()
    liste = client.get(BASE).json()

    assert detail["created_at"].endswith("Z")
    assert detail["log_entries"][0]["created_at"].endswith("Z")
    assert liste[0]["created_at"].endswith("Z")


# --- #1291 : catégorie FFTri et groupes ----------------------------------------


def test_the_list_carries_the_fftri_category_and_membership_end(client, ouvrir_session):
    ouvrir_session(P.YOUTH_READ, P.YOUTH_WRITE)
    client.post(BASE, json={"first_name": "Alix", "last_name": "Martin", "birth_date": "2013-05-02"})
    client.post(BASE, json={"first_name": "Zoé", "last_name": "Roux"})

    alix, zoe = client.get(BASE).json()

    assert alix["category"] == fftri_category(date(2013, 5, 2), date.today())
    assert zoe["category"] is None
    assert zoe["membership_ended_on"] is None


def test_the_detail_lists_the_groups_of_the_profile(client, ouvrir_session, profile):
    beta = client.post("/api/v1/admin/training-groups", json={"name": "Beta"}).json()
    alpha = client.post("/api/v1/admin/training-groups", json={"name": "Alpha"}).json()
    for group in (beta, alpha):
        client.post(f"/api/v1/admin/training-groups/{group['id']}/members", json={"profile_id": profile["id"]})

    body = client.get(f"{BASE}/{profile['id']}").json()

    assert body["groups"] == [{"id": alpha["id"], "name": "Alpha"}, {"id": beta["id"], "name": "Beta"}]


def test_detail_reports_the_season_attendance(client, profile, db_session, monkeypatch):
    monkeypatch.setattr(profile_service, "utcnow", lambda: datetime(2026, 10, 15, 12, 0))
    for day, present in ((date(2026, 9, 2), True), (date(2026, 9, 9), False)):
        session = training_session_repository.create(db_session, date=day)
        training_session_repository.add_participant(
            db_session, training_session_id=session.id, profile_id=profile["id"], present=present
        )
    db_session.commit()

    body = client.get(f"{BASE}/{profile['id']}").json()

    assert body["attendance"] == {"attended": 1, "pointed": 2, "absence_streak": 1}


# --- #1472 : sans `jeunes:read`, les écritures taisent les données personnelles ---


PERSONAL_FIELDS = ("emergency_contact", "notes", "log_entries", "attendance")


@pytest.fixture
def profile_with_personal_data(client, ouvrir_session):
    ouvrir_session(P.YOUTH_READ, P.YOUTH_WRITE)
    created = client.post(
        BASE,
        json={
            "first_name": "Zoé",
            "last_name": "Roux",
            "emergency_contact": "Mère 06 12 34 56 78",
            "notes": "Asthme",
        },
    ).json()
    client.post(f"{BASE}/{created['id']}/log-entries", json={"text": "Bonne séance"})
    return created


def _profile_writes(client, profile_id: int):
    return [
        client.post(
            BASE,
            json={
                "first_name": "Alix",
                "last_name": "Martin",
                "emergency_contact": "Père 06 98 76 54 32",
                "notes": "Allergie",
            },
        ),
        client.patch(f"{BASE}/{profile_id}", json={}),
        client.post(f"{BASE}/{profile_id}/log-entries", json={"text": "Autre séance"}),
    ]


def test_writes_hide_personal_data_from_a_session_without_jeunes_read(
    client, ouvrir_session, profile_with_personal_data
):
    """Un `PATCH` vide ne doit pas lire ce que la garde de lecture refuse :
    contact d'urgence, notes et journal de bord (#1405)."""
    ouvrir_session(P.YOUTH_WRITE)

    responses = _profile_writes(client, profile_with_personal_data["id"])

    assert [response.status_code for response in responses] == [201, 200, 201]
    for response in responses:
        body = response.json()
        for field in PERSONAL_FIELDS:
            assert body[field] is None, field


@pytest.mark.parametrize(
    "session",
    [
        pytest.param({"codes": (P.YOUTH_READ, P.YOUTH_WRITE)}, id="jeunes-read-write"),
        pytest.param({"codes": (), "superutilisateur": True}, id="superuser"),
    ],
)
def test_writes_show_personal_data_with_jeunes_read(
    client, ouvrir_session, profile_with_personal_data, session
):
    ouvrir_session(*session["codes"], superutilisateur=session.get("superutilisateur", False))

    created, patched, logged = _profile_writes(client, profile_with_personal_data["id"])

    assert created.json()["emergency_contact"] == "Père 06 98 76 54 32"
    assert created.json()["notes"] == "Allergie"
    assert patched.json()["emergency_contact"] == "Mère 06 12 34 56 78"
    assert patched.json()["notes"] == "Asthme"
    assert [entry["text"] for entry in logged.json()["log_entries"]] == ["Autre séance", "Bonne séance"]
