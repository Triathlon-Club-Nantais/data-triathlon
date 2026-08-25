from datetime import date

from app.repositories import athlete_repository, course_repository, participation_repository


def test_club_summary_club_vide(client, db_session):
    resp = client.get("/api/v1/club/summary")
    assert resp.status_code == 200
    assert resp.json() == {
        "roster": [],
        "podiums": {"scratch": [], "category": [], "gender": [], "all": []},
    }


def test_club_summary_forme_de_la_reponse(client, db_session):
    ath = athlete_repository.get_or_create(db_session, nom="A", prenom="Alice", club="TCN")
    course = course_repository.get_or_create(
        db_session, name="C", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", rank_overall=1,
    )
    db_session.commit()

    resp = client.get("/api/v1/club/summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["roster"][0]["nom"] == "A"
    assert body["roster"][0]["count"] == 1
    assert len(body["podiums"]["scratch"]) == 1
    assert body["podiums"]["scratch"][0]["athlete_name"] == "Alice A"


def test_club_summary_accessible_sans_authentification(client, db_session):
    """FR-006 — pas de cookie de session requis, comme les autres routes de lecture."""
    resp = client.get("/api/v1/club/summary")
    assert resp.status_code == 200


def test_club_summary_federal_only(client, db_session):
    ath = athlete_repository.get_or_create(db_session, nom="T", prenom="T", club="TCN")
    course = course_repository.get_or_create(
        db_session, name="Trail", event_date=date(2026, 5, 16), event_type="trail"
    )
    participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", rank_overall=1,
    )
    db_session.commit()

    resp = client.get("/api/v1/club/summary", params={"federal_only": "true"})
    assert resp.json()["roster"] == []
