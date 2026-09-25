from datetime import date

from app.repositories import athlete_repository, course_repository, participation_repository


def test_club_summary_club_vide(client, db_session):
    resp = client.get("/api/v1/club/summary")
    assert resp.status_code == 200
    assert resp.json() == {
        "roster": [],
        "podiums": {"scratch": [], "category": [], "gender": [], "all": []},
        "podiums_by_discipline": {},
        "composition": {"gender": {}, "category": {}},
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
    assert body["podiums_by_discipline"]["triathlon-m"]["overall"] == 1
    assert body["composition"]["gender"] == {"": 1}


def test_club_summary_nomme_les_equipiers_d_un_podium_de_relais(client, db_session):
    """#894 : un podium de relais reste une entrée, qui nomme toute l'équipe."""
    jean = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean", club="TCN")
    paul = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul", club="TCN")
    course = course_repository.get_or_create(
        db_session, name="Relais", event_date=date(2026, 6, 1), event_type="triathlon-s",
        is_relay=True,
    )
    relais = participation_repository.create(
        db_session, athlete_id=jean.id, course_id=course.id, bib_number="7",
        club="TCN", status="finisher", rank_overall=2, is_relay=True,
    )
    participation_repository.replace_teammates(db_session, relais, [jean.id, paul.id])
    individuel = participation_repository.create(
        db_session, athlete_id=paul.id, course_id=course_repository.get_or_create(
            db_session, name="Solo", event_date=date(2026, 5, 1), event_type="triathlon-m",
        ).id, bib_number="1", club="TCN", status="finisher", rank_overall=1,
    )
    db_session.commit()

    entrees = {
        e["participation_id"]: e
        for e in client.get("/api/v1/club/summary").json()["podiums"]["scratch"]
    }

    assert len(entrees) == 2
    assert entrees[relais.id]["teammate_names"] == ["Jean DUPONT", "Paul MARTIN"]
    assert entrees[individuel.id]["teammate_names"] == []


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


def test_club_roster_rank_renvoie_le_rang(client, db_session):
    ath = athlete_repository.get_or_create(db_session, nom="A", prenom="Alice", club="TCN")
    course = course_repository.get_or_create(
        db_session, name="C", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher",
    )
    db_session.commit()

    resp = client.get(f"/api/v1/club/roster/rank/{ath.id}")

    assert resp.status_code == 200
    assert resp.json() == {"rank": 1, "total": 1}


def test_club_roster_rank_404_hors_roster(client, db_session):
    ath = athlete_repository.get_or_create(db_session, nom="A", prenom="Alice", club="TCN")
    db_session.commit()

    resp = client.get(f"/api/v1/club/roster/rank/{ath.id}")

    assert resp.status_code == 404
