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


# ── Écritures publiques (#398, constat A04-3) ─────────────────────────────────

_SIGNALEMENT = "/api/v1/admin/pending-providers"
_PARTICIPATIONS = "/api/v1/participations"
_RESULTAT = {
    "provider": "manuel",
    "athlete_name": "DUPONT",
    "athlete_firstname": "Jean",
    "event_name": "Triathlon de Nantes",
    "event_date": "2026-05-16",
    "event_type": "triathlon-m",
    "bib_number": "1",
    "total_time": "01:59:00",
}


def test_les_deux_ecritures_publiques_partagent_un_plafond(client, monkeypatch):
    """A04-3 : la quarantaine borne ce qui est **publié**, jamais ce qui est écrit.

    Un seul seau pour les deux routes : elles se suivent dans le même geste
    (import échoué → signalement → saisie manuelle), et deux compteurs
    n'ajouteraient qu'un plafond à contourner par alternance.
    """
    monkeypatch.setattr(deps, "PUBLIC_WRITE_RATE_LIMIT_MAX_PER_WINDOW", 2)

    assert client.post(_SIGNALEMENT, json={"url": "https://newchrono.fr/a"}).status_code == 201
    assert client.post(_PARTICIPATIONS, json=_RESULTAT).status_code == 201

    refus = client.post(_PARTICIPATIONS, json=_RESULTAT)
    assert refus.status_code == 429
    assert int(refus.headers["Retry-After"]) > 0
    assert client.post(_SIGNALEMENT, json={"url": "https://newchrono.fr/b"}).status_code == 429


def test_le_plafond_des_ecritures_publiques_est_par_ip(client, monkeypatch):
    monkeypatch.setattr(deps, "PUBLIC_WRITE_RATE_LIMIT_MAX_PER_WINDOW", 1)

    def envoi(ip: str, bib: str):
        # Dossard distinct : deux résultats identiques rendraient 409, et le
        # test ne dirait plus rien du plafond.
        return client.post(
            _PARTICIPATIONS, json={**_RESULTAT, "bib_number": bib}, headers={"X-Forwarded-For": ip}
        )

    assert envoi("203.0.113.7", "1").status_code == 201
    assert envoi("203.0.113.8", "2").status_code == 201
    assert envoi("203.0.113.7", "3").status_code == 429


@pytest.mark.parametrize(
    "url",
    [
        "x" * 5000,  # aucune longueur maximale avant #398, colonne TEXT en face
        "javascript:alert(1)",
        "pas une url",
        "",
    ],
)
def test_le_signalement_refuse_ce_qui_n_est_pas_une_url_http(client, url):
    """La route reste **publique** — c'est la forme du corps qu'on borne, pas l'accès."""
    assert client.post(_SIGNALEMENT, json={"url": url}).status_code == 422


def test_le_mot_de_passe_site_partage_le_plafond_des_ecritures_publiques(client, monkeypatch):
    """Revue finale de #509, § Plafond de débit : `POST /site-access/session`
    est désormais la seule porte publique non authentifiée du site, et elle
    rejoint le seau `public_write` déjà partagé par le signalement et la
    saisie manuelle — même dépendance, même seau, aucune infrastructure
    nouvelle.
    """
    monkeypatch.setattr(deps, "PUBLIC_WRITE_RATE_LIMIT_MAX_PER_WINDOW", 1)

    assert client.post(_SIGNALEMENT, json={"url": "https://newchrono.fr/c"}).status_code == 201

    refus = client.post("/api/v1/site-access/session", json={"password": "peu importe"})
    assert refus.status_code == 429
    assert int(refus.headers["Retry-After"]) > 0
