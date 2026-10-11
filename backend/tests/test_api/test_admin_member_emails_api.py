"""Member e-mail list, administration screen (#1334)."""
import pytest

from app.api.deps import require_site_access
from app.core.season import current_season
from app.main import app
from app.models.member_email import SOURCE_IMPORT, SOURCE_MANUAL, MemberEmail

from .test_admin_data_api import _session_etroite

URL = "/api/v1/admin/member-emails"


def _csv(content: bytes = b"email\nanne@exemple.fr\n"):
    return {"file": ("export.csv", content, "text/csv")}


def _seed(db_session, *entries: tuple[str, int, str]) -> list[MemberEmail]:
    rows = [MemberEmail(email=email, season=season, source=source) for email, season, source in entries]
    db_session.add_all(rows)
    db_session.commit()
    return rows


def test_read_a_season_sorted_with_the_counting_season(client, db_session):
    season = current_season()
    _seed(
        db_session,
        ("zoe@exemple.fr", season - 1, SOURCE_IMPORT),
        ("anne@exemple.fr", season - 1, SOURCE_MANUAL),
    )

    body = client.get(URL, params={"season": season - 1}).json()

    assert body["season"] == season - 1
    assert body["counting_season"] == season - 1
    assert body["seasons"] == [season - 1]
    assert [e["email"] for e in body["entries"]] == ["anne@exemple.fr", "zoe@exemple.fr"]
    assert set(body["entries"][0]) == {"id", "email", "season", "source", "created_at"}


def test_the_season_defaults_to_the_current_one(client):
    assert client.get(URL).json()["season"] == current_season()


def test_a_season_out_of_range_is_refused(client):
    assert client.get(URL, params={"season": 1999}).status_code == 422


def test_import_a_file(client):
    response = client.post(
        f"{URL}/import", data={"season": "2026"},
        files=_csv(b"Email\nanne@exemple.fr\nPAUL@exemple.fr\nfaux\n"),
    )

    assert response.status_code == 200
    assert response.json() == {"season": 2026, "added": 2, "removed": 0, "unchanged": 0, "ignored": 1}


def test_an_unreadable_import_is_refused_without_writing(client, db_session):
    client.post(f"{URL}/import", data={"season": "2026"}, files=_csv())

    response = client.post(f"{URL}/import", data={"season": "2026"}, files=_csv(b"Nom\nMARTIN\n"))

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert [e["email"] for e in client.get(URL, params={"season": 2026}).json()["entries"]] == ["anne@exemple.fr"]


def test_add_an_address_by_hand(client):
    response = client.post(URL, json={"email": "Anne@Exemple.fr", "season": 2026})

    assert response.status_code == 201
    assert response.json() | {"id": 0, "created_at": ""} == {
        "id": 0, "email": "anne@exemple.fr", "season": 2026, "source": "manual", "created_at": "",
    }
    assert client.post(URL, json={"email": "anne@exemple.fr", "season": 2026}).status_code == 409
    assert client.post(URL, json={"email": "faux", "season": 2026}).status_code == 422


def test_remove_an_address(client, db_session):
    (entry,) = _seed(db_session, ("anne@exemple.fr", 2026, SOURCE_IMPORT))

    assert client.delete(f"{URL}/{entry.id}").status_code == 204
    assert client.delete(f"{URL}/{entry.id}").status_code == 404


def test_every_route_requires_the_permission(client, db_session):
    _session_etroite(client, db_session, "club_members:manage")

    assert client.get(URL).status_code == 403
    assert client.post(f"{URL}/import", data={"season": "2026"}, files=_csv()).status_code == 403
    assert client.post(URL, json={"email": "a@exemple.fr", "season": 2026}).status_code == 403
    assert client.delete(f"{URL}/1").status_code == 403


def test_the_permission_opens_every_route(client, db_session):
    _session_etroite(client, db_session, "member_emails:manage")

    assert client.get(URL).status_code == 200
    assert client.post(f"{URL}/import", data={"season": "2026"}, files=_csv()).status_code == 200
    created = client.post(URL, json={"email": "a@exemple.fr", "season": 2026})
    assert created.status_code == 201
    assert client.delete(f"{URL}/{created.json()['id']}").status_code == 204


def test_a_named_address_is_refused_in_french(client):
    response = client.post(URL, json={"email": "Jeanne <jeanne@exemple.fr>", "season": 2026})

    assert response.status_code == 422
    assert "prenom.nom@exemple.fr" in response.json()["detail"]


def test_every_route_requires_a_session(client):
    client.cookies.clear()

    assert client.get(URL).status_code == 401
    assert client.post(f"{URL}/import", data={"season": "2026"}, files=_csv()).status_code == 401
    assert client.post(URL, json={"email": "a@exemple.fr", "season": 2026}).status_code == 401
    assert client.delete(f"{URL}/1").status_code == 401


@pytest.fixture
def real_site_gate(client):
    app.dependency_overrides.pop(require_site_access, None)
    yield


def test_the_site_access_gate_applies(client, real_site_gate):
    response = client.get(URL)

    assert response.status_code == 401
    assert response.json()["code"] == "site_access_required"
