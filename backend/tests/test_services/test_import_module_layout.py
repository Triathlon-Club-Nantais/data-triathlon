"""Le découpage d'`import_service` (#1186) : chaque symbole vit dans un seul module.

L'absence de l'ancien nom compte autant que la présence du nouveau :
`monkeypatch.setattr` lève sur un attribut absent, donc un test resté pointé sur
l'ancien module échoue au lieu de laisser passer le vrai scrape ou la vraie écriture.
"""
from datetime import date

from app.core.config import Settings
from app.scrapers.base import FanoutTrace, ScrapedResult
from app.services import import_dispatch, import_persistence, import_service

URL = "https://chrono.example/epreuve-1186"


def test_persistence_lives_in_import_persistence():
    assert callable(import_persistence.persist_steps)
    assert callable(import_persistence.persist_results)
    assert import_persistence.PassiveSource.__name__ == "PassiveSource"
    assert import_persistence.Reassignment.__name__ == "Reassignment"
    for name in (
        "persist_steps", "persist_results", "PassiveSource", "Reassignment",
        "_Persister", "_TRANCHE_SIZE", "split_relay_teammates", "mapping",
    ):
        assert not hasattr(import_service, name), name


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def _one_result() -> ScrapedResult:
    return ScrapedResult(
        source_url=URL, provider="klikego", athlete_name="DUPONT", athlete_firstname="Jean",
        bib_number="1", event_name="Triathlon 1186", event_date=date(2026, 5, 16),
        event_type="triathlon-m", total_time="01:59:00",
    )


def test_dispatch_lives_in_import_dispatch():
    for name in (
        "validate_url", "cached_result", "scrape_all", "scrape_all_streaming",
        "fanout_counters", "merge_cached_courses",
    ):
        assert callable(getattr(import_dispatch, name)), name
    for name in (
        "registry_scrape_event_all", "SessionLocal", "registry", "scrape_all_streaming",
        "_scrape_all", "_cached_result", "_validate_url", "_make_cache_probe",
    ):
        assert not hasattr(import_service, name), name


def test_patching_the_dispatch_scraper_reaches_import_event(db_session, monkeypatch):
    calls = []

    def fake(url, **kwargs):
        calls.append(url)
        return [_one_result()], FanoutTrace(heats_enumerated=1)

    monkeypatch.setattr(import_dispatch, "registry_scrape_event_all", fake)
    outcome = import_service.import_event(db_session, URL, _settings(), force=True)

    assert calls == [URL]
    assert outcome["imported"] == 1


def test_patching_the_dispatch_scraper_reaches_iter_import_event(db_session, monkeypatch):
    calls = []

    def fake(url, **kwargs):
        calls.append(url)
        return [_one_result()], FanoutTrace(heats_enumerated=1)

    monkeypatch.setattr(import_dispatch, "registry_scrape_event_all", fake)
    phases = list(import_service.iter_import_event(db_session, URL, _settings(), force=True))

    assert calls == [URL]
    assert phases[-1]["phase"] == "done"
    assert phases[-1]["imported"] == 1


def test_admin_rescrape_lives_in_course_rescrape_service():
    from app.services import admin_actions, course_rescrape_service

    for name in ("iter_rescrape_course", "iter_switch_course_source", "delete_course_source"):
        assert callable(getattr(course_rescrape_service, name)), name
        assert not hasattr(admin_actions, name), name
    assert callable(admin_actions.course_or_404)
    assert callable(admin_actions.instantane)
    assert admin_actions.CHAMPS_COURSE == ("name", "event_date", "event_type", "is_relay")
