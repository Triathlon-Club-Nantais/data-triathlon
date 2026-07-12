from app import cli
from app.core.config import Settings


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def test_run_rescrape_force_et_compte(db_session, monkeypatch):
    from datetime import date

    from app.repositories import course_repository
    from app.services import import_service

    course_repository.get_or_create(
        db_session, name="A", event_date=date(2026, 1, 1),
        event_type="triathlon-m", source_url="https://k/1", provider="klikego",
    )
    db_session.flush()

    calls = []

    def _import(db, url, settings, force=False):
        calls.append((url, force))
        return {"imported": 3, "skipped": 0}

    monkeypatch.setattr(import_service, "import_event", _import)

    out = cli.run_rescrape_db(db_session, _settings(), delay=0.0)
    assert out.total == 1
    assert out.imported == 3
    assert out.errors == 0
    # force=True : c'est le cœur de la commande
    assert calls == [("https://k/1", True)]


def test_run_rescrape_dry_run_liste_sans_scraper(db_session, monkeypatch):
    from datetime import date

    from app.repositories import course_repository
    from app.services import import_service

    course_repository.get_or_create(
        db_session, name="A", event_date=date(2026, 1, 1),
        event_type="triathlon-m", source_url="https://k/1", provider="klikego",
    )
    db_session.flush()

    appels = []
    monkeypatch.setattr(import_service, "import_event", lambda *a, **k: appels.append(1))

    out = cli.run_rescrape_db(db_session, _settings(), dry_run=True, delay=0.0)
    assert appels == []
    assert out.dry_run_urls == ["https://k/1"]
    assert out.total == 1


def test_run_rescrape_ignore_les_courses_sans_url(db_session, monkeypatch):
    from datetime import date

    from app.repositories import course_repository
    from app.services import import_service

    course_repository.get_or_create(
        db_session, name="SansUrl", event_date=date(2026, 1, 1),
        event_type="triathlon-m", source_url="", provider="klikego",
    )
    db_session.flush()

    appels = []
    monkeypatch.setattr(import_service, "import_event", lambda *a, **k: appels.append(1))

    out = cli.run_rescrape_db(db_session, _settings(), delay=0.0)
    assert out.total == 0
    assert appels == []


def test_run_rescrape_un_echec_n_interrompt_pas_le_batch(db_session, monkeypatch):
    from datetime import date

    from app.repositories import course_repository
    from app.services import import_service

    course_repository.get_or_create(
        db_session, name="Boom", event_date=date(2026, 1, 1),
        event_type="triathlon-m", source_url="https://k/boom", provider="klikego",
    )
    course_repository.get_or_create(
        db_session, name="Ok", event_date=date(2026, 1, 2),
        event_type="triathlon-m", source_url="https://k/ok", provider="klikego",
    )
    db_session.flush()

    def _import(db, url, settings, force=False):
        if "boom" in url:
            raise RuntimeError("échec")
        return {"imported": 1, "skipped": 0}

    monkeypatch.setattr(import_service, "import_event", _import)

    out = cli.run_rescrape_db(db_session, _settings(), delay=0.0)
    assert out.total == 2
    assert out.errors == 1
    assert out.imported == 1
