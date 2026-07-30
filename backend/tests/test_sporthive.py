"""
Harnais de test pour scrapers/sporthive.py (sans réseau) — T002.

Aucun test de comportement du scraper ici : à ce stade `scrape_event_all` lève
`NotImplementedError` (T001), il n'y a rien à en attendre. Ce fichier pose
l'outil dont dépendront les lots suivants — client HTTP factice + compteur
d'appels — et un unique test qui l'exerce lui-même, pour ne pas découvrir un
harnais cassé au moment où le lot 5 s'appuiera dessus.

Fixtures JSON attendues sous `fixtures/sporthive_*.json` (déposées au lot 2) :
chargées via `_fixture`, jamais lues à la main.
"""
import json
from pathlib import Path

import httpx
import pytest

from app.scrapers import sporthive

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(nom: str) -> dict:
    return json.loads((FIXTURES / nom).read_text(encoding="utf-8"))


class FakeResponse:
    """Réponse HTTP factice : `.status_code`, `.json()`, `.raise_for_status()`.

    Modèle `test_oktime.py::FakeResponse` — c'est tout ce que le code réel
    attendra d'une réponse `httpx`, jamais plus.
    """

    def __init__(self, payload=None, status_code: int = 200):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPError(f"HTTP {self.status_code}")


class FakeClient:
    """Client HTTP factice : gestionnaire de contexte, `.get(url, params=...)`.

    `routes` associe un **fragment d'URL** à la réponse à rendre. La
    correspondance se fait sur l'URL **effective**, `params` fusionnés dans la
    query par `httpx.URL` — donc deux appels à la même route mais avec
    `page=0` puis `page=1` peuvent porter des fragments distincts et recevoir
    des réponses différentes (pagination du lot 5). Aucune route ne matche →
    `defaut` (404 par défaut, pas un succès silencieux : un appel non prévu
    doit se voir).

    `self.calls` garde l'URL effective de **chaque** appel, dans l'ordre. Ce
    n'est pas un simple total : `calls_containing(fragment)` permet d'affirmer
    une **absence** de requête (« zéro appel vers /races/1/... ») — c'est cette
    forme d'assertion, pas le compte brut, qui verrouille T013 et T027.
    """

    def __init__(self, routes: dict[str, FakeResponse] | None = None, defaut: FakeResponse | None = None):
        self.routes = routes or {}
        self.defaut = defaut or FakeResponse({"message": "route non prevue"}, 404)
        self.calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url: str, params: dict | None = None) -> FakeResponse:
        effective = str(httpx.URL(url, params=params)) if params else url
        self.calls.append(effective)
        for fragment, reponse in self.routes.items():
            if fragment in effective:
                return reponse
        return self.defaut

    def calls_containing(self, fragment: str) -> list[str]:
        return [appel for appel in self.calls if fragment in appel]


def test_harness_repond_par_route_pagine_et_prouve_une_absence_dappel():
    """Le faux client rend la charge attendue par route, différencie deux pages
    d'une même route via `params`, simule un statut HTTP, et le compteur
    d'appels permet d'affirmer qu'aucune requête n'est partie vers une route
    donnée — exactement l'usage qu'en feront le lot 6 (course à
    `classificationsCount: 0`) et le lot 10 (garde anti-ordinal `/races/1`).
    """
    event = {"eventName": "Triathlon de Test"}
    page0 = {"content": [{"bib": "1"}], "last": False}
    page1 = {"content": [{"bib": "2"}], "last": True}

    client = FakeClient(
        {
            "/events/42": FakeResponse(event),
            "/races/111/participants?page=0": FakeResponse(page0),
            "/races/111/participants?page=1": FakeResponse(page1),
            "/events/999": FakeResponse({"message": "introuvable"}, 404),
        }
    )

    assert client.get(f"{sporthive._API_BASE}/events/42").json() == event

    reponse_p0 = client.get(
        f"{sporthive._API_BASE}/races/111/participants",
        params={"page": 0, "size": sporthive._PAGE_SIZE},
    )
    reponse_p1 = client.get(
        f"{sporthive._API_BASE}/races/111/participants",
        params={"page": 1, "size": sporthive._PAGE_SIZE},
    )
    assert reponse_p0.json() == page0
    assert reponse_p1.json() == page1

    reponse_inconnue = client.get(f"{sporthive._API_BASE}/events/999")
    assert reponse_inconnue.status_code == 404
    with pytest.raises(httpx.HTTPError):
        reponse_inconnue.raise_for_status()

    # Deux appels réellement partis vers la course 111...
    assert len(client.calls_containing("/races/111/participants")) == 2
    # ... et aucun vers l'ordinal dangereux /races/1 (piège #1 de la source) :
    # c'est cette assertion d'absence, pas un compte total, que T013 et T027
    # reproduiront sur le vrai scraper.
    assert client.calls_containing("/races/1/participants") == []
