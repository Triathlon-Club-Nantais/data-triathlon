import json
from datetime import date

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
    assert resp.json() == {"provider": "klikego"}


def test_import_event(client, monkeypatch):
    from app.services import import_service

    monkeypatch.setattr(
        import_service, "registry_scrape_event_all",
        lambda url: [_result("1", "DUPONT"), _result("2", "MARTIN")],
    )
    resp = client.post("/api/v1/scrape/event", json={"url": "https://www.klikego.com/x"})
    assert resp.status_code == 200
    assert resp.json() == {"imported": 2, "skipped": 0, "cached": False}


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
