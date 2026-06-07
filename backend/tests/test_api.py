"""
Tests des routes FastAPI via TestClient avec SQLite en mémoire.

Cas couverts :
- POST /api/results : création, déduplication (409)
- GET /api/results : filtres nom, club, event_name, event_type, pagination
- GET /api/results/events : regroupement par (event_name, event_date, event_type)
- DELETE /api/results/{id}
- DELETE /api/results/event/delete
- POST /api/scrape : erreur URL invalide
- POST /api/scrape/event/preview : erreur URL invalide, provider non supporté
- GET /api/health
"""
import os

# Override DB avant tout import de l'app
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database import Base, get_db

# ── Fixture DB ───────────────────────────────────────────────────────────────

# StaticPool : toutes les connexions partagent la même DB en mémoire
_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def _override_get_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.create_all(bind=_engine)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture
def client():
    return TestClient(app)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _result(
    athlete_name="DUPONT", athlete_firstname="Jean",
    club="TRI CLUB NANTAIS", event_name="Triathlon Test 2025",
    event_type="triathlon-s", event_date="2025-06-01",
    bib_number="42", total_time="01:30:00", rank_overall=10,
    **kwargs,
):
    return {
        "source_url": "https://example.com",
        "provider": "test",
        "athlete_name": athlete_name,
        "athlete_firstname": athlete_firstname,
        "club": club,
        "category": "S1M",
        "gender": "M",
        "bib_number": bib_number,
        "event_name": event_name,
        "event_date": event_date,
        "event_type": event_type,
        "rank_overall": rank_overall,
        "total_time": total_time,
        **kwargs,
    }


# ── /api/health ──────────────────────────────────────────────────────────────

def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── POST /api/results ────────────────────────────────────────────────────────

def test_create_result(client):
    r = client.post("/api/results", json=_result())
    assert r.status_code == 201
    data = r.json()
    assert data["athlete_name"] == "DUPONT"
    assert data["event_type"] == "triathlon-s"
    assert "id" in data


def test_create_result_duplicate_409(client):
    client.post("/api/results", json=_result())
    r = client.post("/api/results", json=_result())  # same bib+event+type
    assert r.status_code == 409
    assert "déjà" in r.json()["detail"]


def test_create_result_different_type_no_conflict(client):
    """Même bib + event_name mais event_type différent → pas de conflit."""
    client.post("/api/results", json=_result(event_type="triathlon-s"))
    r = client.post("/api/results", json=_result(event_type="triathlon-m"))
    assert r.status_code == 201


# ── GET /api/results ─────────────────────────────────────────────────────────

def test_list_results_empty(client):
    r = client.get("/api/results")
    assert r.status_code == 200
    assert r.json() == []


def test_list_results_filter_by_name(client):
    client.post("/api/results", json=_result(athlete_name="DUPONT"))
    client.post("/api/results", json=_result(athlete_name="MARTIN", bib_number="99"))
    r = client.get("/api/results?name=DUPONT")
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["athlete_name"] == "DUPONT"


def test_list_results_filter_by_club(client):
    client.post("/api/results", json=_result(club="TRI CLUB NANTAIS"))
    client.post("/api/results", json=_result(club="AUTRE CLUB", bib_number="99"))
    r = client.get("/api/results?club=nantais")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_list_results_filter_by_event_type(client):
    client.post("/api/results", json=_result(event_type="triathlon-s"))
    client.post("/api/results", json=_result(event_type="triathlon-m", bib_number="99"))
    r = client.get("/api/results?event_type=triathlon-s")
    assert len(r.json()) == 1
    assert r.json()[0]["event_type"] == "triathlon-s"


def test_list_results_pagination(client):
    for i in range(5):
        client.post("/api/results", json=_result(bib_number=str(i)))
    r = client.get("/api/results?page=1&page_size=3")
    assert len(r.json()) == 3
    r2 = client.get("/api/results?page=2&page_size=3")
    assert len(r2.json()) == 2


def test_list_results_tcn_variants(client):
    """Le filtre club reconnaît TCN, TRI CLUB NANTAIS, nantais."""
    for club, bib in [("TCN", "1"), ("TRI CLUB NANTAIS", "2"), ("Triathlon Club Nantais", "3"), ("AUTRE", "4")]:
        client.post("/api/results", json=_result(club=club, bib_number=bib))
    r = client.get("/api/results?club=nantais|TCN")
    names = {res["club"] for res in r.json()}
    assert "AUTRE" not in names
    assert len(r.json()) == 3


# ── GET /api/results/events ──────────────────────────────────────────────────

def test_list_events_groups_by_event_type(client):
    """Un même événement avec deux disciplines → deux lignes distinctes."""
    client.post("/api/results", json=_result(event_type="triathlon-s", bib_number="1"))
    client.post("/api/results", json=_result(event_type="triathlon-m", bib_number="2"))
    r = client.get("/api/results/events")
    assert r.status_code == 200
    events = r.json()
    types = {e["event_type"] for e in events}
    assert "triathlon-s" in types
    assert "triathlon-m" in types


def test_list_events_tcn_count(client):
    """tcn_count ne compte que les résultats du club TCN."""
    client.post("/api/results", json=_result(club="TRI CLUB NANTAIS", bib_number="1"))
    client.post("/api/results", json=_result(club="AUTRE CLUB", bib_number="2"))
    r = client.get("/api/results/events")
    ev = r.json()[0]
    assert ev["total"] == 2
    assert ev["tcn_count"] == 1


# ── DELETE /api/results/{id} ─────────────────────────────────────────────────

def test_delete_result(client):
    created = client.post("/api/results", json=_result()).json()
    r = client.delete(f"/api/results/{created['id']}")
    assert r.status_code == 204
    r2 = client.get(f"/api/results/{created['id']}")
    assert r2.status_code == 404


def test_delete_result_not_found(client):
    r = client.delete("/api/results/99999")
    assert r.status_code == 404


# ── DELETE /api/results/event/delete ─────────────────────────────────────────

def test_delete_event(client):
    client.post("/api/results", json=_result(bib_number="1"))
    client.post("/api/results", json=_result(bib_number="2"))
    r = client.delete("/api/results/event/delete?event_name=Triathlon+Test+2025")
    assert r.status_code == 200
    assert r.json()["deleted"] == 2
    assert client.get("/api/results").json() == []


# ── POST /api/scrape ─────────────────────────────────────────────────────────

def test_scrape_invalid_url(client):
    r = client.post("/api/scrape", json={"url": "not-a-url"})
    assert r.status_code == 400


def test_scrape_prolivesport_listing_raises(client):
    """URL ProLiveSport sans event ID → 422 avec message d'erreur."""
    r = client.post("/api/scrape", json={"url": "https://www.prolivesport.fr/fftri/circuit"})
    assert r.status_code == 422


# ── POST /api/scrape/event/preview ───────────────────────────────────────────

def test_preview_invalid_url(client):
    r = client.post("/api/scrape/event/preview", json={"url": "not-a-url"})
    assert r.status_code == 400


def test_preview_listing_page_error(client):
    """URL ProLiveSport sans event ID → 422 avec message explicatif."""
    r = client.post(
        "/api/scrape/event/preview",
        json={"url": "https://www.prolivesport.fr/fftri/grand-prix-duathlon"},
    )
    assert r.status_code == 422
    assert "liste" in r.json()["detail"].lower() or "identifiant" in r.json()["detail"].lower()
