from datetime import date

from app.core.config import Settings
from app.repositories import course_repository
from app.services import import_service, rescrape_service


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def _course(db, nom: str, url: str, jour: int = 1) -> None:
    course_repository.get_or_create(
        db, name=nom, event_date=date(2026, 1, jour),
        event_type="triathlon-m", source_url=url, provider="klikego",
    )
    db.flush()


def test_run_rescrape_force_et_compte(db_session, monkeypatch):
    _course(db_session, "A", "https://k/1")
    vus: list[tuple[str, bool]] = []

    def _iter(db, url, settings, force=False):
        vus.append((url, force))
        yield {"phase": "done", "imported": 3, "skipped": 0, "total": 3}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    out = rescrape_service.run_rescrape_db(db_session, _settings(), delay=0.0)
    assert out.total == 1
    assert out.imported == 3
    assert out.errors == 0
    # force=True : c'est le cœur de la commande
    assert vus == [("https://k/1", True)]


def test_run_rescrape_dry_run_liste_sans_scraper(db_session, monkeypatch):
    _course(db_session, "A", "https://k/1")
    vus: list[str] = []

    def _iter(db, url, settings, force=False):
        vus.append(url)
        yield {"phase": "done", "imported": 0, "skipped": 0, "total": 0}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    out = rescrape_service.run_rescrape_db(db_session, _settings(), dry_run=True, delay=0.0)
    assert vus == []
    assert out.dry_run_urls == ["https://k/1"]
    assert out.total == 1


def test_run_rescrape_ignore_les_courses_sans_url(db_session, monkeypatch):
    _course(db_session, "SansUrl", "")
    vus: list[str] = []

    def _iter(db, url, settings, force=False):
        vus.append(url)
        yield {"phase": "done", "imported": 0, "skipped": 0, "total": 0}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    out = rescrape_service.run_rescrape_db(db_session, _settings(), delay=0.0)
    assert out.total == 0
    assert vus == []


def test_run_rescrape_un_echec_n_interrompt_pas_le_batch(db_session, monkeypatch):
    _course(db_session, "Boom", "https://k/boom", jour=1)
    _course(db_session, "Ok", "https://k/ok", jour=2)

    def _iter(db, url, settings, force=False):
        if "boom" in url:
            yield {"phase": "error", "message": "échec"}
            return
        yield {"phase": "done", "imported": 1, "skipped": 0, "total": 1}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    out = rescrape_service.run_rescrape_db(db_session, _settings(), delay=0.0)
    assert out.total == 2
    assert out.errors == 1
    assert out.imported == 1


def test_run_rescrape_libelle_avec_le_nom_de_course(db_session, monkeypatch, fake_reporter):
    """Ici le nom vient de la DB : contrairement à import-sheet, on l'a avant le scrape."""
    _course(db_session, "Triathlon de Nantes", "https://k/1")

    def _iter(db, url, settings, force=False):
        yield {"phase": "done", "imported": 1, "skipped": 0, "total": 1}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    rescrape_service.run_rescrape_db(db_session, _settings(), delay=0.0, reporter=fake_reporter)

    assert ("item_start", 0, "klikego · Triathlon de Nantes") in fake_reporter.calls
