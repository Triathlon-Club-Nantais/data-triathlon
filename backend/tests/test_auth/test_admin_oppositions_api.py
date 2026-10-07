"""Les trois ressources de `/api/v1/admin/oppositions` (#334), gardées par `oppositions:manage`."""
from datetime import date, timedelta

import pytest

from app.core.permissions import P
from app.repositories import athlete_repository
from app.services.opposition_service import club_today

BASE = "/api/v1/admin/oppositions"
TODAY = club_today()


@pytest.fixture
def jean(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean")
    db_session.commit()
    return athlete


def test_preview_counts_without_writing(client, ouvrir_session, jean):
    ouvrir_session(P.OPPOSITIONS_MANAGE)

    reponse = client.post(f"{BASE}/preview", json={"athlete_id": jean.id})

    assert reponse.status_code == 200
    assert reponse.json() == {"athletes": 1, "results": 0, "already_opposed": False}
    assert client.get(BASE).json() == []


def test_applying_creates_then_reuses_the_opposition(client, ouvrir_session, jean):
    ouvrir_session(P.OPPOSITIONS_MANAGE, nom="Admin")
    demande = (TODAY - timedelta(days=3)).isoformat()

    premiere = client.post(BASE, json={"athlete_id": jean.id, "requested_on": demande})
    seconde = client.post(BASE, json={"nom": "Dupont", "prenom": "JEAN", "requested_on": demande})

    assert premiere.status_code == 201
    corps = premiere.json()
    assert (corps["requested_on"], corps["delay_days"], corps["overdue"], corps["applied_by_name"]) == (
        demande, 3, False, "Admin",
    )
    assert seconde.status_code == 200 and seconde.json()["id"] == corps["id"]
    assert [o["id"] for o in client.get(BASE).json()] == [corps["id"]]


def test_an_unknown_athlete_is_404(client, ouvrir_session):
    ouvrir_session(P.OPPOSITIONS_MANAGE)

    reponse = client.post(BASE, json={"athlete_id": 9999, "requested_on": TODAY.isoformat()})

    assert reponse.status_code == 404


@pytest.mark.parametrize(
    "corps",
    [
        {"requested_on": TODAY.isoformat()},
        {"athlete_id": 1, "nom": "Dupont", "prenom": "Jean", "requested_on": TODAY.isoformat()},
        {"nom": "Dupont", "prenom": "Jean", "requested_on": (TODAY + timedelta(days=1)).isoformat()},
    ],
)
def test_an_identity_and_a_past_date_are_required(client, ouvrir_session, corps):
    ouvrir_session(P.OPPOSITIONS_MANAGE)

    assert client.post(BASE, json=corps).status_code in (400, 422)


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [("GET", BASE, None), ("POST", f"{BASE}/preview", {"nom": "A", "prenom": "B"}),
     ("POST", BASE, {"nom": "A", "prenom": "B", "requested_on": date(2026, 1, 1).isoformat()})],
)
def test_the_resources_refuse_the_anonymous_and_the_unprivileged(client, ouvrir_session, method, path, body):
    assert client.request(method, path, json=body).status_code == 401
    ouvrir_session(P.ATHLETES_WRITE)
    assert client.request(method, path, json=body).status_code == 403
