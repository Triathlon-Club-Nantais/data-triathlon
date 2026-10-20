"""Sign-in identities of the session account over HTTP (#1663)."""
from app.models.identity import Identity

from .test_admin_data_api import _session_etroite

URL = "/api/v1/auth/me/identities"


def test_identities_requires_session(client):
    client.cookies.clear()

    assert client.get(URL).status_code == 401


def test_identities_lists_only_own_accounts_identities(client, db_session):
    other = _session_etroite(client, db_session, email="autre@exemple.fr", slug="autre")
    mine = _session_etroite(client, db_session, email="moi@exemple.fr", slug="moi")
    db_session.add_all([
        Identity(user_id=other.id, provider="github", subject="43", email="autre@exemple.fr"),
        Identity(user_id=mine.id, provider="github", subject="42", email="moi@exemple.fr", secret_hash="h"),
    ])
    db_session.commit()

    response = client.get(URL)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["provider"] == "github"
    assert body[0]["label"] == "GitHub"
    assert body[0]["email"] == "moi@exemple.fr"
    assert set(body[0]) == {"provider", "label", "email", "created_at"}


def test_identity_of_unregistered_provider_falls_back_to_slug(client, db_session):
    mine = _session_etroite(client, db_session, email="moi@exemple.fr", slug="moi")
    db_session.add(Identity(user_id=mine.id, provider="ancien", subject="1", email="moi@exemple.fr"))
    db_session.commit()

    assert client.get(URL).json()[0]["label"] == "ancien"
