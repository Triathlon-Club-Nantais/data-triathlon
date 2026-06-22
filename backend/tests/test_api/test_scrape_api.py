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
