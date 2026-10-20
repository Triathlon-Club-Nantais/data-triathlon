"""`gender` filter on the stats, club and participations endpoints (#1646)."""
from datetime import date

import pytest

from app.core import season
from app.models.club_member import LINK_UNLINKED, SOURCE_FFTRI, ClubMember
from app.repositories import athlete_repository, course_repository, participation_repository

ENDPOINTS = ["/api/v1/stats", "/api/v1/club/summary", "/api/v1/club/podiums", "/api/v1/participations"]


@pytest.fixture
def mixed_club(db_session):
    """Two women (one podium), one man (one podium), one athlete without sex."""
    people = [("ALICE", "F", 1), ("BEA", "F", 5), ("CARL", "M", 2), ("DANI", "", 9)]
    for index, (nom, gender, rank) in enumerate(people):
        athlete = athlete_repository.get_or_create(db_session, nom=nom, prenom="T", gender=gender, club="TCN")
        course = course_repository.get_or_create(
            db_session, name=f"C{index}", event_date=date(2026, 5, 16), event_type="triathlon-m"
        )
        participation_repository.create(
            db_session, athlete_id=athlete.id, course_id=course.id, bib_number=str(index),
            club="TCN", status="finisher", rank_overall=rank, rank_gender=rank if gender else None,
        )
    db_session.commit()


def test_stats_gender_filter_counts_only_that_sex(client, mixed_club):
    totals = {g: client.get("/api/v1/stats", params={"gender": g} if g else {}).json()["total"] for g in ("", "F", "M")}
    assert totals == {"": 4, "F": 2, "M": 1}


def test_club_podiums_gender_filter(client, mixed_club):
    body = client.get("/api/v1/club/podiums", params={"gender": "F"}).json()
    entries = [e for mode in body.values() for e in mode]
    assert entries
    assert {e["athlete_name"] for e in entries} == {"T ALICE"}


def test_club_summary_gender_filter(client, mixed_club):
    unfiltered = client.get("/api/v1/club/summary").json()
    assert len(unfiltered["roster"]) == 4
    body = client.get("/api/v1/club/summary", params={"gender": "F"}).json()
    assert {r["nom"] for r in body["roster"]} == {"ALICE", "BEA"}
    assert {e["athlete_name"] for e in body["podiums"]["scratch"]} == {"T ALICE"}
    assert body["composition"]["gender"] == {"F": 2}


def test_participations_gender_filter(client, mixed_club):
    rows = client.get("/api/v1/participations", params={"scope": "club", "gender": "F"}).json()
    assert len(rows) == 2


@pytest.mark.parametrize("url", ENDPOINTS)
def test_gender_param_rejects_unknown_value(client, url):
    assert client.get(url, params={"gender": "X"}).status_code == 422


def test_club_summary_gender_filters_licensees_by_licence_gender(client, db_session):
    year = season.current_season()
    db_session.add_all([
        ClubMember(season=year, nom="A", prenom="Alice", gender="F", licence_id="L1",
                   link_status=LINK_UNLINKED, source=SOURCE_FFTRI),
        ClubMember(season=year, nom="B", prenom="Bob", gender="M", licence_id="L2",
                   link_status=LINK_UNLINKED, source=SOURCE_FFTRI),
    ])
    db_session.commit()
    assert client.get("/api/v1/club/summary").json()["licensees"]["total"] == 2
    assert client.get("/api/v1/club/summary", params={"gender": "F"}).json()["licensees"]["total"] == 1
