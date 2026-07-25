"""`federal_only` sort les disciplines hors fédération des compteurs (#76)."""


def _payload(bib: str, nom: str, event_name: str, event_type: str) -> dict:
    return {
        "athlete_name": nom,
        "athlete_firstname": "Test",
        "club": "TRI CLUB NANTAIS",
        "bib_number": bib,
        "event_name": event_name,
        "event_date": "2026-05-31",
        "event_type": event_type,
        "total_time": "01:30:00",
        "provider": "manuel",
    }


def _peupler(client):
    client.post("/api/v1/participations", json=_payload("1", "DUPONT", "Tri M", "triathlon-m"))
    client.post("/api/v1/participations", json=_payload("2", "MARTIN", "Urban Trail", "trail"))
    client.post("/api/v1/participations", json=_payload("3", "DURAND", "10 km", "course-a-pied-10k"))


def test_sans_le_parametre_rien_n_est_filtre(client):
    """L'API reste neutre par défaut : c'est l'écran qui décide, pas le backend."""
    _peupler(client)
    rows = client.get("/api/v1/participations", params={"scope": "club"}).json()
    assert len(rows) == 3


def test_federal_only_retire_trail_et_course_a_pied(client):
    _peupler(client)
    rows = client.get(
        "/api/v1/participations", params={"scope": "club", "federal_only": "true"}
    ).json()
    assert [r["course"]["event_type"] for r in rows] == ["triathlon-m"]


def test_les_stats_suivent_le_meme_filtre(client):
    _peupler(client)

    tout = client.get("/api/v1/stats", params={"scope": "club"}).json()
    federal = client.get(
        "/api/v1/stats", params={"scope": "club", "federal_only": "true"}
    ).json()

    assert tout["total"] == 3
    assert tout["events"] == 3
    assert federal["total"] == 1
    assert federal["events"] == 1
    assert set(federal["by_type"]) == {"triathlon-m"}


def test_les_epreuves_agregees_suivent_le_meme_filtre(client):
    _peupler(client)

    tout = client.get("/api/v1/courses/events", params={"scope": "club"}).json()
    federal = client.get(
        "/api/v1/courses/events", params={"scope": "club", "federal_only": "true"}
    ).json()

    assert tout["total_events"] == 3
    assert federal["total_events"] == 1
    assert federal["total_participations"] == 1
