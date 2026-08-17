"""Plafond de débit par IP sur les routes publiques coûteuses (#395).

Constats A04-2 et A07-1 de l'audit OWASP. Le garde SSRF de `core/http.py` ferme
la **destination**, jamais le **volume** ; le cache TTL de `services/cache.py`
limite le re-scraping d'une **même** épreuve, jamais le nombre d'épreuves
distinctes demandées. Ce plafond est le seul qui borne le volume.

Le plafond n'a de sens que parce que #393 a fixé la chaîne d'IP : c'est la
**première** entrée de `X-Forwarded-For` qui fait foi, donc celle posée par la
plateforme et non celle que l'appelant choisit.
"""
from datetime import date

import pytest

from app.api import deps
from app.core.config import get_settings
from app.scrapers.base import ScrapedResult

_SCRAPE = "/api/v1/scrape/event"
_STREAM = "/api/v1/scrape/event/stream"
_URL = {"url": "https://www.klikego.com/x"}


@pytest.fixture
def scraper_muet(monkeypatch):
    """Neutralise le réseau : le plafond se mesure sur le nombre d'appels."""
    from app.services import import_service

    monkeypatch.setattr(
        import_service,
        "registry_scrape_event_all",
        lambda url, **kwargs: [
            ScrapedResult(
                source_url="http://detail",
                provider="klikego",
                athlete_name="DUPONT",
                athlete_firstname="Jean",
                bib_number="1",
                event_name="Triathlon de Nantes",
                event_date=date(2026, 5, 16),
                event_type="triathlon-m",
                total_time="01:59:00",
            )
        ],
    )


def test_scrape_au_dela_du_plafond_rend_429(client, monkeypatch, scraper_muet):
    monkeypatch.setattr(get_settings(), "scrape_rate_limit_max_per_window", 2)

    assert client.post(_SCRAPE, json=_URL).status_code == 200
    assert client.post(_SCRAPE, json=_URL).status_code == 200
    refus = client.post(_SCRAPE, json=_URL)

    assert refus.status_code == 429
    # `Retry-After` dit quand réessayer : sans lui, un client légitime bloqué
    # n'a que le tâtonnement.
    assert int(refus.headers["Retry-After"]) > 0


def test_le_sse_partage_le_plafond_de_la_route_bloquante(client, monkeypatch, scraper_muet):
    """Un seul seau pour les deux routes : elles déclenchent le même travail.

    Deux compteurs distincts doubleraient le plafond réel pour qui alterne.
    """
    monkeypatch.setattr(get_settings(), "scrape_rate_limit_max_per_window", 1)

    assert client.post(_SCRAPE, json=_URL).status_code == 200
    assert client.post(_STREAM, json=_URL).status_code == 429


def test_le_plafond_est_par_ip(client, monkeypatch, scraper_muet):
    monkeypatch.setattr(get_settings(), "scrape_rate_limit_max_per_window", 1)

    def envoi(ip: str):
        return client.post(_SCRAPE, json=_URL, headers={"X-Forwarded-For": ip})

    assert envoi("203.0.113.7").status_code == 200
    assert envoi("203.0.113.8").status_code == 200
    assert envoi("203.0.113.7").status_code == 429


def test_l_ip_usurpee_ne_contourne_pas_le_plafond(client, monkeypatch, scraper_muet):
    """Même piège que #393 : seule la première entrée de l'en-tête fait foi."""
    monkeypatch.setattr(get_settings(), "scrape_rate_limit_max_per_window", 1)

    def envoi(usurpee: str):
        return client.post(
            _SCRAPE, json=_URL, headers={"X-Forwarded-For": f"203.0.113.7, {usurpee}"}
        )

    assert envoi("198.51.100.1").status_code == 200
    assert envoi("198.51.100.2").status_code == 429


def test_l_ouverture_de_parcours_est_plafonnee(client, monkeypatch):
    """A07-1 : `GET /auth/{provider}/authorize` est publique et sans plafond.

    Le statut des appels sous le plafond n'a pas d'importance ici (503 sur une
    installation de test sans secrets) : ce qui se vérifie, c'est que le refus
    de débit arrive, et qu'il arrive **avant** le corps de la route.
    """
    monkeypatch.setattr(deps, "AUTHORIZE_RATE_LIMIT_MAX_PER_WINDOW", 1)

    assert client.get("/api/v1/auth/github/authorize").status_code != 429
    assert client.get("/api/v1/auth/github/authorize").status_code == 429


def test_le_sse_trace_qui_l_appelle(client, caplog, monkeypatch):
    """Le SSE ne prenait même pas `optional_user` : aucune trace de l'appelant."""
    from app.services import import_service

    monkeypatch.setattr(
        import_service,
        "iter_import_event",
        lambda db, url, settings, force=False, persist=True: iter(
            [{"phase": "done", "imported": 0, "total": 0}]
        ),
    )

    with caplog.at_level("INFO", logger="app.api.v1.scrape"):
        with client.stream("POST", _STREAM, json=_URL) as resp:
            assert resp.status_code == 200
            "".join(resp.iter_text())

    assert any("SSE import requested" in record.message for record in caplog.records)
