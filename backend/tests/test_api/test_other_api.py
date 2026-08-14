from tests.test_api.conftest import valider_toutes_les_participations


def _payload(bib="1", nom="DUPONT", club="TCN"):
    return {
        "provider": "manuel",
        "athlete_name": nom,
        "athlete_firstname": "Jean",
        "gender": "M",
        "club": club,
        "event_name": "Triathlon de Nantes",
        "event_date": "2026-05-16",
        "event_type": "triathlon-m",
        "bib_number": bib,
        "total_time": "01:59:00",
    }


def test_athletes_search_and_detail(client):
    client.post("/api/v1/participations", json=_payload())
    athletes = client.get("/api/v1/athletes", params={"name": "dupont"}).json()
    assert len(athletes) == 1
    aid = athletes[0]["id"]
    detail = client.get(f"/api/v1/athletes/{aid}").json()
    assert detail["athlete"]["nom"] == "DUPONT"
    assert len(detail["participations"]) == 1


def test_courses_events_and_detail(client, db_session):
    client.post("/api/v1/participations", json=_payload(bib="1", club="TCN"))
    client.post("/api/v1/participations", json=_payload(bib="2", nom="MARTIN", club="ASPTT"))
    valider_toutes_les_participations(db_session)

    page = client.get("/api/v1/courses/events").json()
    assert page["total_events"] == 1
    assert page["total_participations"] == 2
    assert len(page["items"]) == 1
    event = page["items"][0]
    assert event["total"] == 2
    assert event["tcn_count"] == 1
    assert event["id"] > 0

    courses = client.get("/api/v1/courses").json()
    assert len(courses) == 1
    cid = courses[0]["id"]
    detail = client.get(f"/api/v1/courses/{cid}").json()
    assert len(detail["participations"]) == 2

    # course_id sur /participations → participants d'une épreuve précise.
    by_course = client.get("/api/v1/participations", params={"course_id": event["id"]}).json()
    assert len(by_course) == 2


def test_course_saisie_hors_import_na_pas_dindice(client):
    """Aucun import ne l'a évaluée : `is_reliable` vaut None, pas False."""
    client.post("/api/v1/participations", json=_payload())
    cid = client.get("/api/v1/courses").json()[0]["id"]

    course = client.get(f"/api/v1/courses/{cid}").json()["course"]
    assert course["is_reliable"] is None
    assert course["quality_issues"] is None


def test_course_importee_expose_ses_anomalies(client, db_session, monkeypatch):
    from datetime import date

    from app.core.config import get_settings
    from app.scrapers.base import ScrapedResult
    from app.services import import_service

    scraped = ScrapedResult(
        source_url="https://chrono/detail",
        provider="klikego",
        athlete_name="DURAND",
        athlete_firstname="Paul",
        bib_number="7",
        event_name="Duathlon de Vertou",
        event_date=date(2026, 3, 1),
        event_type="duathlon-s",
        total_time="",
        status="DQ",  # hors nomenclature finisher/DNF/DNS/DSQ
    )
    monkeypatch.setattr(import_service, "registry_scrape_event_all", lambda url, **kwargs: [scraped])
    import_service.import_event(db_session, "https://chrono/epreuve", get_settings())

    courses = client.get("/api/v1/courses").json()
    cid = next(c["id"] for c in courses if c["name"] == "Duathlon de Vertou")

    course = client.get(f"/api/v1/courses/{cid}").json()["course"]
    assert course["is_reliable"] is False
    assert course["quality_issues"] == {"unknown_status": 1}


def test_stats(client, db_session):
    client.post("/api/v1/participations", json=_payload(bib="1", club="TCN"))
    valider_toutes_les_participations(db_session)
    stats = client.get("/api/v1/stats").json()
    assert stats["total"] == 1
    assert stats["by_type"] == {"triathlon-m": 1}


def test_stats_seasons_endpoint_et_filtre(client, db_session):
    # Saison 2025 (2026-05-16) et saison 2023 (2023-10-01).
    client.post("/api/v1/participations", json=_payload(bib="1", club="TCN"))
    client.post(
        "/api/v1/participations",
        json={**_payload(bib="2", nom="MARTIN", club="TCN"), "event_name": "Tri 2023", "event_date": "2023-10-01"},
    )
    valider_toutes_les_participations(db_session)

    seasons = client.get("/api/v1/stats/seasons").json()
    years = [s["start_year"] for s in seasons]
    assert 2025 in years and 2023 in years
    assert years == sorted(years, reverse=True)
    s2025 = next(s for s in seasons if s["start_year"] == 2025)
    assert s2025["label"] == "Saison 2025 — 2026"
    assert "is_current" in s2025

    # Filtre /stats par saison.
    stats_2025 = client.get("/api/v1/stats", params={"seasons": "2025"}).json()
    assert stats_2025["total"] == 1
    stats_multi = client.get("/api/v1/stats", params={"seasons": "2025,2023"}).json()
    assert stats_multi["total"] == 2


def test_courses_events_filtre_par_saison(client, db_session):
    client.post("/api/v1/participations", json=_payload(bib="1", club="TCN"))  # saison 2025
    client.post(
        "/api/v1/participations",
        json={**_payload(bib="2", club="TCN"), "event_name": "Tri 2023", "event_date": "2023-10-01"},
    )
    valider_toutes_les_participations(db_session)
    page = client.get("/api/v1/courses/events", params={"seasons": "2025"}).json()
    assert page["total_events"] == 1
    assert page["items"][0]["event_name"] == "Triathlon de Nantes"


def test_participations_filtre_par_saison(client, db_session):
    client.post("/api/v1/participations", json=_payload(bib="1", club="TCN"))  # saison 2025
    client.post(
        "/api/v1/participations",
        json={**_payload(bib="2", club="TCN"), "event_name": "Tri 2023", "event_date": "2023-10-01"},
    )
    valider_toutes_les_participations(db_session)
    rows = client.get("/api/v1/participations", params={"seasons": "2023"}).json()
    assert len(rows) == 1
    assert rows[0]["course"]["event_date"] == "2023-10-01"


def test_admin_pending_providers_flow(client):
    created = client.post(
        "/api/v1/admin/pending-providers", json={"url": "https://newchrono.fr/abc"}
    ).json()
    assert created["provider_hint"] == "newchrono.fr"

    listed = client.get("/api/v1/admin/pending-providers").json()
    assert len(listed) == 1

    # Hors de l'`assert` : sous `python -O` la suppression ne partirait pas, et la
    # liste vide attendue ensuite ne prouverait plus rien.
    suppression = client.delete(f"/api/v1/admin/pending-providers/{created['id']}")
    assert suppression.status_code == 204
    assert client.get("/api/v1/admin/pending-providers").json() == []


def test_athlete_detail_expose_le_nombre_de_finishers_classes(client, db_session):
    client.post("/api/v1/participations", json={**_payload(bib="1"), "rank_overall": 1})
    client.post(
        "/api/v1/participations",
        json={**_payload(bib="2", nom="MARTIN"), "rank_overall": 2},
    )
    client.post(
        "/api/v1/participations",
        json={**_payload(bib="3", nom="DURAND"), "rank_overall": None},
    )
    valider_toutes_les_participations(db_session)

    athletes = client.get("/api/v1/athletes", params={"name": "dupont"}).json()
    detail = client.get(f"/api/v1/athletes/{athletes[0]['id']}").json()

    participation = detail["participations"][0]
    assert participation["rank_overall"] == 1
    # DURAND a un temps mais pas de rang : hors du classement.
    assert participation["course_finishers"] == 2


def test_athlete_detail_le_relais_ne_recoit_pas_le_compte_des_solos(client, db_session):
    """Le groupe (course_id, is_relay) est bien celui de la *participation*, pas de la course."""
    from datetime import date

    from app.repositories import athlete_repository, course_repository, participation_repository

    course = course_repository.get_or_create(
        db_session, name="Tri Relais", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    solo1 = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean", club="TCN")
    solo2 = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul", club="TCN")
    relayeur = athlete_repository.get_or_create(db_session, nom="DURAND", prenom="Luc", club="TCN")

    participation_repository.create(
        db_session, athlete_id=solo1.id, course_id=course.id, bib_number="1",
        status="finisher", rank_overall=1, is_relay=False,
    )
    participation_repository.create(
        db_session, athlete_id=solo2.id, course_id=course.id, bib_number="2",
        status="finisher", rank_overall=2, is_relay=False,
    )
    participation_repository.create(
        db_session, athlete_id=relayeur.id, course_id=course.id, bib_number="3",
        status="finisher", rank_overall=1, is_relay=True,
    )
    db_session.commit()

    detail_relayeur = client.get(f"/api/v1/athletes/{relayeur.id}").json()
    assert detail_relayeur["participations"][0]["course_finishers"] == 1

    detail_solo = client.get(f"/api/v1/athletes/{solo1.id}").json()
    assert detail_solo["participations"][0]["course_finishers"] == 2


def test_athlete_detail_course_finishers_null_sans_finisher_classe(client):
    """Aucun finisher classé dans la course : `course_finishers` est `null` dans le JSON."""
    client.post(
        "/api/v1/participations",
        json={**_payload(bib="1"), "rank_overall": None, "total_time": ""},
    )

    athletes = client.get("/api/v1/athletes", params={"name": "dupont"}).json()
    detail = client.get(f"/api/v1/athletes/{athletes[0]['id']}").json()

    assert detail["participations"][0]["course_finishers"] is None
