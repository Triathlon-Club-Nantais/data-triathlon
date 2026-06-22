def _payload(bib="42", nom="DUPONT", club="TCN"):
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
        "category": "V1H",
        "rank_overall": 10,
        "total_time": "01:59:00",
        "swim_time": "00:20:00",
        "bike_time": "01:00:00",
        "run_time": "00:39:00",
    }


def test_create_and_get_participation(client):
    resp = client.post("/api/v1/participations", json=_payload())
    assert resp.status_code == 201
    body = resp.json()
    pid = body["id"]
    assert body["athlete"]["nom"] == "DUPONT"
    assert body["course"]["name"] == "Triathlon de Nantes"
    assert body["splits"] == {"swim": "00:20:00", "bike": "01:00:00", "run": "00:39:00"}

    got = client.get(f"/api/v1/participations/{pid}")
    assert got.status_code == 200
    assert got.json()["bib_number"] == "42"


def test_create_participation_with_segments(client):
    # Chemin générique : segments étiquetés libres, déplafonnés, priment sur les slots.
    payload = _payload(bib="77")
    payload.pop("swim_time", None)
    payload.pop("bike_time", None)
    payload.pop("run_time", None)
    payload["event_type"] = "swimrun-l"
    payload["segments"] = [["swim1", "00:10:00"], ["run1", "00:20:00"], ["swim2", "00:08:00"]]
    resp = client.post("/api/v1/participations", json=payload)
    assert resp.status_code == 201
    assert resp.json()["splits"] == {
        "swim1": "00:10:00",
        "run1": "00:20:00",
        "swim2": "00:08:00",
    }


def test_duplicate_participation_409(client):
    client.post("/api/v1/participations", json=_payload())
    dup = client.post("/api/v1/participations", json=_payload())
    assert dup.status_code == 409


def test_list_filters(client):
    client.post("/api/v1/participations", json=_payload(bib="1", nom="DUPONT", club="TCN"))
    client.post("/api/v1/participations", json=_payload(bib="2", nom="MARTIN", club="ASPTT"))

    by_name = client.get("/api/v1/participations", params={"name": "dupont"})
    assert len(by_name.json()) == 1

    by_club = client.get("/api/v1/participations", params={"club": "nantais|tcn"})
    assert len(by_club.json()) == 1
    assert by_club.json()[0]["club"] == "TCN"


def test_delete_participation(client):
    pid = client.post("/api/v1/participations", json=_payload()).json()["id"]
    assert client.delete(f"/api/v1/participations/{pid}").status_code == 204
    assert client.get(f"/api/v1/participations/{pid}").status_code == 404


def test_get_missing_404(client):
    assert client.get("/api/v1/participations/9999").status_code == 404
