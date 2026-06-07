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


def test_courses_events_and_detail(client):
    client.post("/api/v1/participations", json=_payload(bib="1", club="TCN"))
    client.post("/api/v1/participations", json=_payload(bib="2", nom="MARTIN", club="ASPTT"))

    events = client.get("/api/v1/courses/events").json()
    assert len(events) == 1
    assert events[0]["total"] == 2
    assert events[0]["tcn_count"] == 1

    courses = client.get("/api/v1/courses").json()
    assert len(courses) == 1
    cid = courses[0]["id"]
    detail = client.get(f"/api/v1/courses/{cid}").json()
    assert len(detail["participations"]) == 2


def test_stats(client):
    client.post("/api/v1/participations", json=_payload(bib="1", club="TCN"))
    stats = client.get("/api/v1/stats").json()
    assert stats["total"] == 1
    assert stats["by_type"] == {"triathlon-m": 1}


def test_admin_pending_providers_flow(client):
    created = client.post(
        "/api/v1/admin/pending-providers", json={"url": "https://newchrono.fr/abc"}
    ).json()
    assert created["provider_hint"] == "newchrono.fr"

    listed = client.get("/api/v1/admin/pending-providers").json()
    assert len(listed) == 1

    assert client.delete(f"/api/v1/admin/pending-providers/{created['id']}").status_code == 204
    assert client.get("/api/v1/admin/pending-providers").json() == []
