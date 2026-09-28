"""Les routes qui rendaient des `dict` publient leur schéma de réponse (#1055).

Sans `response_model`, `/docs` et `openapi.json` décrivent la réponse par `{}` :
le contrat `/api/v1` (Principe IV) n'y est pas écrit.
"""
import pytest

from app.main import app

ROUTES = [
    ("get", "/api/v1/athletes/{athlete_id}", "200"),
    ("get", "/api/v1/stats", "200"),
    ("get", "/api/v1/stats/events-geo", "200"),
    ("get", "/api/v1/scrape/detect", "200"),
    ("get", "/api/v1/scrape/providers", "200"),
    ("post", "/api/v1/admin/pending-providers", "201"),
    ("get", "/api/v1/admin/pending-providers", "200"),
    ("get", "/api/v1/admin/athletes/{athlete_id}/season-quota", "200"),
]


@pytest.mark.parametrize(("methode", "chemin", "code"), ROUTES)
def test_the_route_publishes_its_response_schema(methode, chemin, code):
    schema = app.openapi()["paths"][chemin][methode]["responses"][code]["content"][
        "application/json"
    ]["schema"]

    assert schema, f"{methode.upper()} {chemin} : réponse non décrite"


def test_the_stats_payload_keeps_its_keys(client):
    corps = client.get("/api/v1/stats").json()

    assert set(corps) == {"total", "athletes", "events", "by_type", "by_month", "recent", "rank_counters"}
    assert set(corps["rank_counters"]) == {"scratch", "category", "all", "gender"}
    assert set(corps["rank_counters"]["gender"]) == {"women", "men"}
    assert set(corps["rank_counters"]["scratch"]) == {"victories", "podiums", "top10"}


def test_the_detect_payload_keeps_its_keys(client):
    corps = client.get("/api/v1/scrape/detect", params={"url": "https://www.klikego.com/x"}).json()

    assert set(corps) == {"provider", "supported", "fanout", "default_single_heat"}


def test_a_pending_report_keeps_its_keys(client):
    cree = client.post("/api/v1/admin/pending-providers", json={"url": "https://newchrono.fr/a"})
    liste = client.get("/api/v1/admin/pending-providers").json()

    assert set(cree.json()) == {"id", "url", "provider_hint"}
    assert set(liste[0]) == {"id", "url", "provider_hint", "reported_at"}
    assert liste[0]["reported_at"] is not None
