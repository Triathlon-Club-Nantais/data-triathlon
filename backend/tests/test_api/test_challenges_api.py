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


def _seed_by_sex(db, rows):
    """rows: (nom, gender, rank_overall, rank_gender, status)."""
    challenge = challenge_repository.upsert(db, name="SEXE CHALLENGE", event_date=DAY, source_url="u")
    for index, (nom, gender, rank, rank_gender, status) in enumerate(rows):
        athlete = Athlete(nom=nom, prenom="X", gender=gender)
        db.add(athlete)
        db.flush()
        challenge_repository.upsert_result(
            db, challenge, athlete_id=athlete.id, bib_number=str(index), rank_overall=rank,
            rank_gender=rank_gender, rank_category=None, total_time=None, status=status, raw_data={},
        )
    db.commit()
    return challenge


WOMEN_AMONG_MEN = [
    ("A", "F", 3, 1, "finisher"), ("B", "M", 4, 1, "finisher"),
    ("C", "F", 5, 2, "finisher"), ("D", "F", 8, 4, "finisher"),
]


def test_challenge_detail_exposes_gender_and_rank_gender(client, db_session):
    challenge = _seed_by_sex(db_session, WOMEN_AMONG_MEN)
    body = client.get(f"/api/v1/challenges/{challenge.id}").json()
    assert [(r["gender"], r["rank_gender"]) for r in body["results"]] == [
        ("F", 1), ("M", 1), ("F", 2), ("F", 4),
    ]
    assert all(r["gender_place"] is None for r in body["results"])
    assert body["unknown_gender_count"] is None


def test_challenge_detail_gender_official_places(client, db_session):
    challenge = _seed_by_sex(db_session, WOMEN_AMONG_MEN)
    body = client.get(f"/api/v1/challenges/{challenge.id}?gender=F").json()
    assert [r["gender_place"] for r in body["results"]] == [1, 2, 4]
    assert all(r["gender_place_official"] is True for r in body["results"])
    assert [r["nom"] for r in body["results"]] == ["A", "C", "D"]


def test_challenge_detail_gender_recalculated_places(client, db_session):
    rows = [*WOMEN_AMONG_MEN[:2], ("C", "F", 5, None, "finisher"), WOMEN_AMONG_MEN[3]]
    challenge = _seed_by_sex(db_session, rows)
    body = client.get(f"/api/v1/challenges/{challenge.id}?gender=F").json()
    assert [r["gender_place"] for r in body["results"]] == [1, 2, 3]
    assert all(r["gender_place_official"] is False for r in body["results"])


def test_challenge_detail_gender_unranked_follow_without_place(client, db_session):
    rows = [("A", "F", None, None, "DNF"), ("B", "F", 2, 1, "finisher")]
    challenge = _seed_by_sex(db_session, rows)
    body = client.get(f"/api/v1/challenges/{challenge.id}?gender=F").json()
    assert [(r["nom"], r["gender_place"]) for r in body["results"]] == [("B", 1), ("A", None)]


def test_challenge_detail_gender_counts_unknown(client, db_session):
    challenge = _seed_by_sex(db_session, [*WOMEN_AMONG_MEN, ("Z", "", 9, None, "finisher")])
    body = client.get(f"/api/v1/challenges/{challenge.id}?gender=F").json()
    assert body["unknown_gender_count"] == 1
    assert "Z" not in [r["nom"] for r in body["results"]]


def test_challenge_detail_rejects_unknown_gender(client, db_session):
    challenge = _seed_by_sex(db_session, WOMEN_AMONG_MEN)
    assert client.get(f"/api/v1/challenges/{challenge.id}?gender=X").status_code == 422
