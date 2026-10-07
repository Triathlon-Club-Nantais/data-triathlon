"""Licenciés du club, écran d'administration (#1202)."""
import pytest

from app.models.admin_action_log import AdminActionLog
from app.models.athlete import Athlete
from app.models.club_member import LINK_MANUAL
from app.scrapers.fftri_club_members import ClubRoster, RosterMember
from app.services import club_members_service

from .test_admin_data_api import _session_etroite


@pytest.fixture
def roster(monkeypatch):
    monkeypatch.setattr(
        club_members_service.fftri_club_members, "fetch_club_roster",
        lambda url: ClubRoster(licence_year=2027, members=[RosterMember("MARTIN", "Anne", "F", "C1")]),
    )


def _csv_file():
    return {"file": ("l.csv", b"Nom,Prenom\nA,B\n", "text/csv")}


def test_sync_then_read_the_season(client, db_session, roster):
    athlete = Athlete(nom="MARTIN", prenom="Anne")
    db_session.add(athlete)
    db_session.commit()

    synced = client.post("/api/v1/admin/club-members/sync")
    assert synced.status_code == 200
    assert synced.json() == {"season": 2026, "total": 1, "linked": 1, "unlinked": 0, "ambiguous": 0}

    read = client.get("/api/v1/admin/club-members", params={"season": 2026})
    assert read.status_code == 200
    body = read.json()
    assert body["seasons"] == [2026]
    assert body["members"][0] | {"id": 0} == {
        "id": 0, "season": 2026, "licence_id": "C1", "nom": "MARTIN", "prenom": "Anne",
        "gender": "F", "athlete_id": athlete.id, "link_status": "auto", "source": "fftri",
    }


def test_import_a_past_season_from_a_file(client):
    response = client.post(
        "/api/v1/admin/club-members/import",
        data={"season": "2024"},
        files={"file": ("licencies.csv", b"Nom,Prenom\nDURAND,Paul\n", "text/csv")},
    )

    assert response.status_code == 200
    assert response.json()["season"] == 2024
    assert response.json()["unlinked"] == 1


def test_a_file_too_large_is_refused(client):
    response = client.post(
        "/api/v1/admin/club-members/import",
        data={"season": "2024"},
        files={"file": ("l.csv", b"x" * (2 * 1024 * 1024 + 1), "text/csv")},
    )

    assert response.status_code == 413


def test_link_a_member_by_hand(client, db_session, roster):
    client.post("/api/v1/admin/club-members/sync")
    other = Athlete(nom="MARTIN", prenom="Anne-Marie")
    db_session.add(other)
    db_session.commit()
    member_id = client.get("/api/v1/admin/club-members", params={"season": 2026}).json()["members"][0]["id"]

    response = client.post(f"/api/v1/admin/club-members/{member_id}/link", json={"athlete_id": other.id})

    assert response.status_code == 200
    assert (response.json()["athlete_id"], response.json()["link_status"]) == (other.id, LINK_MANUAL)


def test_undoing_a_manual_link_returns_the_member_to_the_queue(client, db_session, roster):
    client.post("/api/v1/admin/club-members/sync")
    other = Athlete(nom="DURAND", prenom="Anne")
    db_session.add(other)
    db_session.commit()
    member_id = client.get("/api/v1/admin/club-members", params={"season": 2026}).json()["members"][0]["id"]
    client.post(f"/api/v1/admin/club-members/{member_id}/link", json={"athlete_id": other.id})

    response = client.delete(f"/api/v1/admin/club-members/{member_id}/link")

    assert response.status_code == 200
    assert (response.json()["athlete_id"], response.json()["link_status"]) == (None, "unlinked")
    db_session.expire_all()
    last = db_session.query(AdminActionLog).order_by(AdminActionLog.id.desc()).first()
    assert (last.action, last.entity_id) == ("club_member.unlink", member_id)
    assert client.delete(f"/api/v1/admin/club-members/{member_id}/link").status_code == 400
    assert client.delete("/api/v1/admin/club-members/99999/link").status_code == 404


def test_undoing_a_manual_link_restores_the_automatic_match(client, db_session, roster):
    anne = Athlete(nom="MARTIN", prenom="Anne")
    other = Athlete(nom="DURAND", prenom="Anne")
    db_session.add_all([anne, other])
    db_session.commit()
    client.post("/api/v1/admin/club-members/sync")
    member_id = client.get("/api/v1/admin/club-members", params={"season": 2026}).json()["members"][0]["id"]
    client.post(f"/api/v1/admin/club-members/{member_id}/link", json={"athlete_id": other.id})

    response = client.delete(f"/api/v1/admin/club-members/{member_id}/link")

    assert (response.json()["athlete_id"], response.json()["link_status"]) == (anne.id, "auto")


def test_every_route_requires_the_permission(client, db_session):
    _session_etroite(client, db_session, "athletes:read")

    assert client.delete("/api/v1/admin/club-members/1/link").status_code == 403

    assert client.get("/api/v1/admin/club-members", params={"season": 2026}).status_code == 403
    assert client.post("/api/v1/admin/club-members/sync").status_code == 403
    assert client.post("/api/v1/admin/club-members/1/link", json={"athlete_id": 1}).status_code == 403
    assert client.post(
        "/api/v1/admin/club-members/import", data={"season": "2024"}, files=_csv_file()
    ).status_code == 403


def test_every_route_requires_a_session(client):
    client.cookies.clear()

    assert client.delete("/api/v1/admin/club-members/1/link").status_code == 401
    assert client.get("/api/v1/admin/club-members", params={"season": 2026}).status_code == 401
    assert client.post("/api/v1/admin/club-members/sync").status_code == 401
    assert client.post("/api/v1/admin/club-members/1/link", json={"athlete_id": 1}).status_code == 401
    assert client.post(
        "/api/v1/admin/club-members/import", data={"season": "2024"}, files=_csv_file()
    ).status_code == 401


def test_count_the_members_to_settle_in_the_current_season(client, db_session):
    """#1232 : la pastille compte les licenciés sans fiche ou à plusieurs fiches."""
    from app.core.season import current_season

    db_session.add_all([
        Athlete(nom="MARTIN", prenom="Anne"),
        Athlete(nom="MARTIN", prenom="Anne", homonym_rank=2),
        Athlete(nom="PETIT", prenom="Luc"),
    ])
    db_session.commit()
    content = b"Nom,Prenom\nMARTIN,Anne\nPETIT,Luc\nDURAND,Paul\n"
    for season in (current_season() - 1, current_season()):
        imported = client.post(
            "/api/v1/admin/club-members/import",
            data={"season": str(season)},
            files={"file": ("l.csv", content, "text/csv")},
        )
        assert imported.json()["unlinked"] + imported.json()["ambiguous"] == 2

    assert client.get("/api/v1/admin/club-members/count").json() == {"total": 2}


def test_counting_needs_the_members_power(client, db_session):
    _session_etroite(client, db_session, "athletes:read")

    assert client.get("/api/v1/admin/club-members/count").status_code == 403
