from datetime import date

import pytest

from app.core.config import Settings
from app.core.exceptions import ProviderNotSupportedError
from app.repositories import participation_repository
from app.scrapers.base import ScrapedResult
from app.services import import_service


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def _result(bib, nom, prenom="Jean", **kw) -> ScrapedResult:
    base = dict(
        source_url="http://detail",
        provider="klikego",
        athlete_name=nom,
        athlete_firstname=prenom,
        bib_number=bib,
        event_name="Triathlon de Nantes",
        event_date=date(2026, 5, 16),
        event_type="triathlon-m",
        total_time="01:59:00",
    )
    base.update(kw)
    return ScrapedResult(**base)


@pytest.fixture
def patch_scraper(monkeypatch):
    def _set(results):
        monkeypatch.setattr(
            import_service, "registry_scrape_event_all", lambda url: results
        )
    return _set


URL = "https://www.klikego.com/resultats/event/123"


def test_import_creates_entities(db_session, patch_scraper):
    patch_scraper([_result("1", "DUPONT"), _result("2", "MARTIN")])
    out = import_service.import_event(db_session, URL, _settings())
    assert out == {"imported": 2, "skipped": 0}
    assert len(participation_repository.list_participations(db_session, page_size=100)) == 2


def test_reimport_is_cached_and_skips(db_session, patch_scraper):
    patch_scraper([_result("1", "DUPONT"), _result("2", "MARTIN")])
    import_service.import_event(db_session, URL, _settings())

    # 2e import immédiat → court-circuité par le cache TTL
    out = import_service.import_event(db_session, URL, _settings())
    assert out["cached"] is True
    assert out["imported"] == 0
    assert out["skipped"] == 2


def test_reimport_after_cache_dedups_by_bib(db_session, patch_scraper):
    patch_scraper([_result("1", "DUPONT")])
    import_service.import_event(db_session, URL, _settings())

    # Force l'expiration du cache → re-scrape, mais le dossard 1 existe déjà
    from app.repositories import course_repository
    course = course_repository.get_latest_by_source_url(db_session, URL)
    from datetime import timedelta

    from app.core.time import utcnow
    course.scraped_at = utcnow() - timedelta(days=40)
    db_session.flush()

    patch_scraper([_result("1", "DUPONT"), _result("2", "MARTIN")])
    out = import_service.import_event(db_session, URL, _settings())
    assert out == {"imported": 1, "skipped": 1}


def test_unsupported_provider_raises(db_session, monkeypatch):
    def _raise(url):
        raise ValueError("Import non supporté")

    monkeypatch.setattr(import_service, "registry_scrape_event_all", _raise)
    with pytest.raises(ProviderNotSupportedError):
        import_service.import_event(db_session, URL, _settings())
