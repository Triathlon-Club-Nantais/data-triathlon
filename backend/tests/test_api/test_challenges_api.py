"""Exposition des classements Challenge (#1008)."""
from datetime import date

from app.models.athlete import Athlete
from app.models.course import Course
from app.repositories import challenge_repository

DAY = date(2026, 5, 13)


def _seed(db):
    xs = Course(name="E - XS", event_date=DAY, event_type="triathlon-xs")
    db.add(xs)
    first, second = Athlete(nom="DUPONT", prenom="Jean"), Athlete(nom="MARTIN", prenom="Paul")
    db.add_all([first, second])
    db.flush()
    challenge = challenge_repository.upsert(db, name="E - START CHALLENGE", event_date=DAY, source_url="u")
    challenge_repository.replace_links(db, challenge, [xs.id])
    for athlete, rank, bib in ((second, 2, "2"), (first, 1, "1")):
        challenge_repository.upsert_result(
            db, challenge, athlete_id=athlete.id, bib_number=bib, rank_overall=rank,
            rank_gender=None, rank_category=None, total_time=f"06:5{rank}:00", status="finisher",
            raw_data={},
        )
    db.commit()
    return xs, first, challenge


def test_athlete_detail_lists_challenges(client, db_session):
    xs, athlete, challenge = _seed(db_session)
    body = client.get(f"/api/v1/athletes/{athlete.id}").json()
    assert body["challenges"] == [{
        "id": challenge.id, "name": "E - START CHALLENGE", "event_date": "2026-05-13",
        "rank_overall": 1, "ranked_count": 2, "total_time": "06:51:00",
        "courses": [{"id": xs.id, "name": "E - XS"}],
    }]
    assert body["participations"] == []


def test_course_summary_lists_challenges(client, db_session):
    xs, _, challenge = _seed(db_session)
    body = client.get(f"/api/v1/courses/{xs.id}/summary").json()
    assert body["challenges"] == [{"id": challenge.id, "name": "E - START CHALLENGE", "ranked_count": 2}]


def test_course_summary_without_challenge_has_an_empty_list(client, db_session):
    course = Course(name="Seule", event_date=DAY, event_type="triathlon-m")
    db_session.add(course)
    db_session.commit()
    assert client.get(f"/api/v1/courses/{course.id}/summary").json()["challenges"] == []


def test_challenge_detail_is_ranked(client, db_session):
    _, _, challenge = _seed(db_session)
    body = client.get(f"/api/v1/challenges/{challenge.id}").json()
    assert [r["nom"] for r in body["results"]] == ["DUPONT", "MARTIN"]
    assert body["courses"] == [{"id": body["courses"][0]["id"], "name": "E - XS"}]
    assert body["event_date"] == "2026-05-13"


def test_unknown_challenge_is_404(client):
    assert client.get("/api/v1/challenges/999").status_code == 404
