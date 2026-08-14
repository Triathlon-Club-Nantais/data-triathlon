from tests.test_api.conftest import valider_toutes_les_participations


def _payload(bib="42", nom="DUPONT", club="TCN", provider="manuel"):
    """Payload de création, avec l'URL source qu'implique le fournisseur.

    Depuis #279, `Course.provider` se lit sur la **source active** de l'épreuve,
    et une source ne naît que d'une `source_url`. Un provider sans URL laisse
    donc la course sans fournisseur : c'est exactement l'état d'une saisie
    manuelle, et c'est pour ça que « manuel » n'en porte pas ici.
    """
    return {
        "provider": provider,
        "source_url": "" if provider == "manuel" else f"https://example.test/{provider}/nantes",
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


def test_list_filters(client, db_session):
    client.post("/api/v1/participations", json=_payload(bib="1", nom="DUPONT", club="TCN"))
    client.post("/api/v1/participations", json=_payload(bib="2", nom="MARTIN", club="ASPTT"))
    valider_toutes_les_participations(db_session)

    by_name = client.get("/api/v1/participations", params={"name": "dupont"})
    assert len(by_name.json()) == 1

    by_club = client.get("/api/v1/participations", params={"scope": "club"})
    assert by_club.status_code == 200
    assert by_club.json()[0]["club"] == "TCN"


def test_delete_participation(client):
    pid = client.post("/api/v1/participations", json=_payload()).json()["id"]
    # La suppression est hors de l'`assert` : sous `python -O` elle ne partirait
    # pas, et le 404 attendu ensuite ne prouverait plus rien.
    suppression = client.delete(f"/api/v1/participations/{pid}")
    assert suppression.status_code == 204
    assert client.get(f"/api/v1/participations/{pid}").status_code == 404


def test_get_missing_404(client):
    assert client.get("/api/v1/participations/9999").status_code == 404


def test_is_pending_validation_est_force_a_la_creation(client):
    """FR-016 — et un client qui tente de poser `false` lui-même ne le peut pas."""
    payload = _payload()
    payload["is_pending_validation"] = False
    resp = client.post("/api/v1/participations", json=payload)
    assert resp.status_code == 201
    assert resp.json()["is_pending_validation"] is True


def test_sortie_porte_les_nouveaux_champs(client):
    payload = _payload(bib="99")
    payload["team_name"] = "Les Foulées"
    payload["evidence_url"] = "https://club.example/resultats"
    resp = client.post("/api/v1/participations", json=payload)
    body = resp.json()
    assert body["team_name"] == "Les Foulées"
    assert body["evidence_url"] == "https://club.example/resultats"


def test_is_tcn_expose_le_verdict_du_backend(client, db_session):
    """Le front n'a plus à deviner : le backend tranche et le dit."""
    client.post("/api/v1/participations", json=_payload(bib="1", nom="DUPONT", club="TRI CLUB NANTAIS"))
    client.post("/api/v1/participations", json=_payload(bib="2", nom="MARTIN", club="RACING CLUB NANTAIS *"))
    valider_toutes_les_participations(db_session)

    rows = client.get("/api/v1/participations").json()
    par_club = {r["club"]: r["is_tcn"] for r in rows}

    assert par_club["TRI CLUB NANTAIS"] is True
    assert par_club["RACING CLUB NANTAIS *"] is False


def test_stats_is_null_when_provider_is_not_eligible(client):
    """Une saisie manuelle n'ouvre jamais l'état détaillé, quel que soit son contenu (FR-003)."""
    pid = client.post("/api/v1/participations", json=_payload()).json()["id"]
    assert client.get(f"/api/v1/participations/{pid}").json()["stats"] is None


def test_stats_is_null_for_a_relay(client):
    payload = _payload(bib="9", provider="raceresult")
    payload["is_relay"] = True
    pid = client.post("/api/v1/participations", json=payload).json()["id"]
    assert client.get(f"/api/v1/participations/{pid}").json()["stats"] is None


def test_stats_is_populated_for_an_eligible_course(client):
    client.post("/api/v1/participations", json=_payload(bib="1", nom="DUPONT", provider="raceresult"))
    pid = client.post("/api/v1/participations", json=_payload(bib="2", nom="MARTIN", provider="raceresult")).json()["id"]

    stats = client.get(f"/api/v1/participations/{pid}").json()["stats"]

    assert stats is not None
    assert set(stats) == {"segments", "ranking_evolution", "comparison", "improvement"}


def test_stats_ignores_club_membership(client):
    """FR-004 : les splits sont déjà publics ailleurs, la page n'ajoute aucune confidentialité."""
    pid = client.post(
        "/api/v1/participations",
        json=_payload(bib="3", nom="MARTIN", club="ASPTT", provider="raceresult"),
    ).json()["id"]

    body = client.get(f"/api/v1/participations/{pid}").json()

    assert body["is_tcn"] is False
    assert body["stats"] is not None


def test_course_listing_carries_the_field_without_computing_it(client):
    """Le champ est additif partout où `ParticipationOut` est sérialisé ; le calcul, lui, ne l'est pas."""
    created = client.post("/api/v1/participations", json=_payload(bib="4", provider="raceresult")).json()

    rows = client.get(f"/api/v1/courses/{created['course']['id']}").json()["participations"]

    assert [row["stats"] for row in rows] == [None]
