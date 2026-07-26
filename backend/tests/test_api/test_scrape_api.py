import json
from datetime import date

import pytest

from app.scrapers.base import ScrapedResult


def _result(bib, nom):
    return ScrapedResult(
        source_url="http://detail",
        provider="klikego",
        athlete_name=nom,
        athlete_firstname="Jean",
        bib_number=bib,
        event_name="Triathlon de Nantes",
        event_date=date(2026, 5, 16),
        event_type="triathlon-m",
        total_time="01:59:00",
    )


def test_detect(client):
    resp = client.get("/api/v1/scrape/detect", params={"url": "https://www.klikego.com/x"})
    assert resp.json() == {"provider": "klikego", "supported": True}


@pytest.mark.parametrize(
    ("url", "provider"),
    [
        ("https://www.ironman.com/races/im703-vichy/results", "competitor"),
        ("https://my.raceresult.com/406211/results", "raceresult"),
        ("https://chronoplace.fr/evenement/x", "chronoplace"),
    ],
)
def test_detect_expose_le_support_des_providers_recents(client, url, provider):
    """`supported` est dérivé du registre, jamais d'une liste à tenir à jour.

    Le front affichait « Non supporté (competitor) » sur une URL ironman.com :
    il portait sa propre liste de providers, figée à six noms — Competitor,
    RaceResult et Chronoplace en étaient absents (même piège de définition
    dupliquée que #76). C'est l'API qui tranche désormais.
    """
    resp = client.get("/api/v1/scrape/detect", params={"url": url})
    assert resp.json() == {"provider": provider, "supported": True}


def test_detect_url_inconnue_reste_non_supportee(client):
    resp = client.get("/api/v1/scrape/detect", params={"url": "https://chronopuce.test/x"})
    assert resp.json() == {"provider": "playwright", "supported": False}


def test_detect_sur_host_ipv6_malforme_ne_leve_pas_500(client):
    """Résidu du finding Important n°2 (revue #49) : `WiclaxProvider.matches`
    faisait son propre `urlparse` non protégé, appelé avant tout garde-fou —
    cet endpoint ne passe ni par `HttpUrl` ni par `_validate_url`. Une entrée
    dégradée doit rester un non-match (fallback `playwright`), jamais une
    exception qui remonte en 500."""
    resp = client.get("/api/v1/scrape/detect", params={"url": "https://[oops/x"})
    assert resp.status_code == 200
    assert resp.json() == {"provider": "playwright", "supported": False}


def test_import_event(client, monkeypatch):
    from app.services import import_service

    monkeypatch.setattr(
        import_service, "registry_scrape_event_all",
        lambda url: [_result("1", "DUPONT"), _result("2", "MARTIN")],
    )
    resp = client.post("/api/v1/scrape/event", json={"url": "https://www.klikego.com/x"})
    assert resp.status_code == 200
    assert resp.json() == {"imported": 2, "updated": 0, "skipped": 0, "cached": False}


def test_import_event_stream_serializes_reassignments(client, monkeypatch):
    """Régression : la phase `done` du SSE porte des `Reassignment` (dataclass
    frozen, non sérialisable par `json.dumps` nu) dès qu'une réconciliation a
    eu lieu. Sans le `default=` sur `json.dumps` dans scrape.py, ce test
    échoue avec un TypeError (« Object of type Reassignment is not JSON
    serializable ») levé pendant la consommation du flux.
    """
    from app.services import import_service

    def fake_iter_import_event(db, url, settings, force=False, persist=True):
        yield {"phase": "scraping", "message": "Récupération des participants…"}
        yield {
            "phase": "done",
            "imported": 1,
            "skipped": 0,
            "reconciled": 1,
            "reassignments": [
                import_service.Reassignment(
                    ancien="DUPOND | Jean", nouveau="DUPONT | Jean", fusion=True
                ),
            ],
            "total": 1,
        }

    monkeypatch.setattr(import_service, "iter_import_event", fake_iter_import_event)

    with client.stream(
        "POST", "/api/v1/scrape/event/stream", json={"url": "https://www.klikego.com/x"}
    ) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())

    frames = [
        json.loads(line[len("data: "):])
        for line in body.splitlines()
        if line.startswith("data: ")
    ]
    done = next(f for f in frames if f["phase"] == "done")
    assert done["reassignments"] == [
        {"ancien": "DUPOND | Jean", "nouveau": "DUPONT | Jean", "fusion": True}
    ]


def test_import_event_expose_updated_counter(client, monkeypatch):
    """Le compteur `updated` (upsert) doit être exposé dans la réponse — pas seulement
    calculé en interne : `ImportResult` doit le déclarer, sinon Pydantic le tait."""
    from app.services import import_service

    monkeypatch.setattr(
        import_service, "registry_scrape_event_all",
        lambda url: [_result("1", "DUPONT")],
    )
    resp = client.post("/api/v1/scrape/event", json={"url": "https://www.klikego.com/x"})
    assert resp.status_code == 200
    body = resp.json()
    assert "updated" in body
    assert body == {"imported": 1, "updated": 0, "skipped": 0, "cached": False}


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "gopher://169.254.169.254/",
    "javascript:alert(1)",
    "pas-une-url",
    "",
])
@pytest.mark.parametrize("route", ["/api/v1/scrape/event", "/api/v1/scrape/event/stream"])
def test_schema_non_http_rejete_a_la_porte(client, route, url):
    """422 de Pydantic, avant d'atteindre le service : le schéma d'entrée est
    la première garde des deux endpoints d'import (#49)."""
    resp = client.post(route, json={"url": url})
    assert resp.status_code == 422


def test_url_http_valide_toujours_acceptee(client, monkeypatch):
    """Non-régression : `HttpUrl` ne doit refuser aucune URL de chronométrage réelle."""
    from app.services import import_service

    vues: list[str] = []

    def fake_scrape(url):
        vues.append(url)
        return [_result("1", "DUPONT")]

    monkeypatch.setattr(import_service, "registry_scrape_event_all", fake_scrape)

    url = "https://www.prolivesport.fr/index.php?chap=event&eventId=979&race=Triathlon%20M"
    resp = client.post("/api/v1/scrape/event", json={"url": url})

    assert resp.status_code == 200
    # Le service reçoit bien une `str`, pas un objet `HttpUrl`, et l'URL n'a pas
    # été réécrite : `source_url` est la clé du cache TTL.
    assert vues == [url]
    assert isinstance(vues[0], str)


@pytest.mark.parametrize("url, attendu", [
    # Port par défaut supprimé — cas réel, cf. `_ROUTAGE_LEGITIME` de test_registry.py.
    (
        "https://my.raceresult.com:443/399938/results",
        "https://my.raceresult.com/399938/results",
    ),
    # Espaces du chemin percent-encodés.
    (
        "https://chronosmetron.wiclax-results.com/Triathlon de la Roche 2026/",
        "https://chronosmetron.wiclax-results.com/Triathlon%20de%20la%20Roche%202026/",
    ),
    # Caractères non-ASCII percent-encodés.
    (
        "https://www.klikego.com/résultats/été",
        "https://www.klikego.com/r%C3%A9sultats/%C3%A9t%C3%A9",
    ),
])
def test_httpurl_normalise_la_cle_de_cache(url, attendu):
    """Épingle la normalisation de `HttpUrl` (mesurée sur pydantic 2.13.4) :
    `source_url` en dérive sur ces trois familles d'entrée. Pas un bug — le
    commentaire de `ScrapeRequest.url` documente la conséquence exacte (cache
    TTL inefficace sur ces URLs, mais pas de doublon de course) — mais si
    pydantic change de comportement, ce test doit le signaler."""
    from app.schemas.scrape import ScrapeRequest

    assert str(ScrapeRequest(url=url).url) == attendu
