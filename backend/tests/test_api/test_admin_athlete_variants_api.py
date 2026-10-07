"""List and remove the identity variants of an athlete record through the admin API (#1242)."""
import pytest

from app.models.admin_action_log import AdminActionLog
from app.models.athlete import Athlete
from app.models.athlete_alias import AthleteAlias
from app.repositories import athlete_alias_repository
from tests.test_api.test_admin_data_api import _session_etroite


@pytest.fixture
def record(db_session):
    athlete = Athlete(nom="DANIEL", prenom="Jacques")
    other = Athlete(nom="DUPONT", prenom="Jean")
    db_session.add_all([athlete, other])
    db_session.flush()
    athlete_alias_repository.add(db_session, ("jacques", "daniel"), athlete.id)
    athlete_alias_repository.add(db_session, ("dupomt", "jean"), other.id)
    db_session.commit()
    [variant] = db_session.query(AthleteAlias).filter_by(athlete_id=athlete.id).all()
    return athlete, other, variant


def test_lists_the_variants_of_the_record_only(client, record):
    athlete, _, variant = record

    response = client.get(f"/api/v1/admin/athletes/{athlete.id}/aliases")

    assert response.status_code == 200
    [body] = response.json()["aliases"]
    assert (body["id"], body["last_name_key"], body["first_name_key"]) == (variant.id, "jacques", "daniel")
    assert body["created_at"]


def test_listing_an_unknown_record_is_404(client):
    assert client.get("/api/v1/admin/athletes/999999/aliases").status_code == 404


def test_removing_a_variant_deletes_it_and_logs_once(client, db_session, record):
    athlete, _, variant = record

    response = client.delete(f"/api/v1/admin/athletes/{athlete.id}/aliases/{variant.id}")

    assert response.status_code == 204
    db_session.expire_all()
    assert db_session.get(AthleteAlias, variant.id) is None
    [log] = db_session.query(AdminActionLog).filter_by(action="athlete.alias_remove").all()
    assert (log.entity_type, log.entity_id) == ("athlete", athlete.id)
    assert log.payload == {"alias_id": variant.id, "last_name_key": "jacques", "first_name_key": "daniel"}


def test_removing_a_variant_of_another_record_is_404(client, db_session, record):
    athlete, other, _ = record
    [foreign] = db_session.query(AthleteAlias).filter_by(athlete_id=other.id).all()

    response = client.delete(f"/api/v1/admin/athletes/{athlete.id}/aliases/{foreign.id}")

    assert response.status_code == 404
    assert db_session.get(AthleteAlias, foreign.id) is not None
    assert db_session.query(AdminActionLog).count() == 0


def test_both_routes_need_athletes_write(client, db_session, record):
    athlete, _, variant = record
    list_url = f"/api/v1/admin/athletes/{athlete.id}/aliases"
    delete_url = f"{list_url}/{variant.id}"

    client.cookies.clear()
    assert client.get(list_url).status_code == 401
    assert client.delete(delete_url).status_code == 401
    _session_etroite(client, db_session, "athletes:read", email="r@exemple.fr", slug="only-read")
    assert client.get(list_url).status_code == 403
    assert client.delete(delete_url).status_code == 403
    _session_etroite(client, db_session, "athletes:write", email="w@exemple.fr", slug="only-write")
    assert client.get(list_url).status_code == 200
