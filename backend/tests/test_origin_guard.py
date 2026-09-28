"""Refus des requêtes d'écriture same-site ou cross-site (#946).

`SameSite=Lax` ne bloque que le cross-site : une page de l'apex ou d'un autre
sous-domaine (le site vitrine est un mutualisé hors de notre contrôle) porte les
cookies de session sur un `<form>` ou un `fetch` sans preflight.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.origin_guard import OriginGuardMiddleware

FRONT = "https://data.triathlon-club-nantais.com"


@pytest.fixture
def client():
    app = FastAPI()

    @app.post("/ecrire")
    def ecrire():
        return {"ok": True}

    @app.get("/lire")
    def lire():
        return {"ok": True}

    app.add_middleware(OriginGuardMiddleware, allowed_origins=[FRONT, "http://localhost:3000"])
    return TestClient(app)


@pytest.mark.parametrize("site", ["same-site", "cross-site"])
def test_a_write_from_another_site_is_refused(client, site):
    resp = client.post("/ecrire", headers={"Sec-Fetch-Site": site, "Origin": FRONT})

    assert resp.status_code == 403


def test_a_write_from_the_showcase_apex_is_refused_without_fetch_metadata(client):
    resp = client.post("/ecrire", headers={"Origin": "https://triathlon-club-nantais.com"})

    assert resp.status_code == 403
    assert "origine" in resp.json()["detail"]


@pytest.mark.parametrize(
    "headers",
    [
        {"Sec-Fetch-Site": "same-origin", "Origin": FRONT},
        {"Sec-Fetch-Site": "none"},
        {"Origin": FRONT},
        {"Origin": f"{FRONT}/"},
        {},
    ],
    ids=["same-origin", "typed-url", "front-origin", "front-origin-slash", "server-to-server"],
)
def test_legitimate_writes_pass(client, headers):
    assert client.post("/ecrire", headers=headers).status_code == 200


def test_reads_are_never_filtered(client):
    resp = client.get("/lire", headers={"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.example"})

    assert resp.status_code == 200


def test_the_application_mounts_the_guard():
    from app.main import app

    assert any(m.cls is OriginGuardMiddleware for m in app.user_middleware)
