"""Les pastilles du rail admin en un seul appel (#1385)."""
from tests.test_api.test_admin_data_api import _session_etroite

URL = "/api/v1/admin/badge-counts"


def test_an_admin_gets_every_badge(client):
    client.post("/api/v1/admin/pending-providers", json={"url": "https://chrono.example/x"})

    assert client.get(URL).json() == {
        "quality": 0,
        "duplicates": 0,
        "providers": 1,
        "feedback": 0,
        "identities": 0,
        "members": 0,
        "volunteer": 0,
        "claims": 0,
        "validation": 0,
    }


def test_a_partial_role_gets_only_its_badges(client, db_session):
    _session_etroite(client, db_session, "athletes:write", "feedback:read")

    assert client.get(URL).json() == {"feedback": 0, "identities": 0}


def test_the_volunteer_access_power_opens_the_validation_badge(client, db_session):
    _session_etroite(client, db_session, "benevole_access:manage")

    assert client.get(URL).json() == {"validation": 0}


def test_a_hidden_badge_is_not_computed(client, db_session, monkeypatch):
    from app.services import admin_badge_counts

    monkeypatch.setitem(admin_badge_counts._BADGES, "identities", ("athletes:write", lambda db: 1 / 0))
    _session_etroite(client, db_session, "feedback:read")

    assert client.get(URL).json() == {"feedback": 0}


def test_a_session_without_power_gets_nothing(client, db_session):
    _session_etroite(client, db_session)

    assert client.get(URL).json() == {}


def test_an_anonymous_visitor_is_refused(client):
    client.cookies.clear()

    assert client.get(URL).status_code == 401
