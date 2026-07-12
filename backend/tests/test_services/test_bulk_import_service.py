from app.core.config import Settings
from app.services import bulk_import_service, import_service


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def _phases(imported: int = 2, skipped: int = 1):
    """Fabrique un faux iter_import_event qui journalise les URLs vues."""
    vus: list[tuple[str, bool]] = []

    def _iter(db, url, settings, force=False):
        vus.append((url, force))
        yield {"phase": "saving", "total": 3, "imported": 0, "skipped": 0, "progress": 0}
        yield {"phase": "done", "imported": imported, "skipped": skipped, "total": 3}

    return _iter, vus


def test_run_import_sheet_compteurs_et_rapport(db_session, monkeypatch):
    from app.scrapers import registry

    monkeypatch.setattr(
        registry, "detect_provider",
        lambda url: "klikego" if "klikego" in url else "playwright",
    )
    _iter, vus = _phases(imported=2, skipped=1)
    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    csv_text = (
        "a,Donne-nous un lien pour accéder aux résultats.\n"
        "x,https://www.klikego.com/e/1\n"
        "x,https://www.klikego.com/e/1/\n"        # doublon du précédent
        "x,https://inconnu.example/e/2\n"          # non supporté
        "x,\n"                                      # sans lien
    )
    out = bulk_import_service.run_import_sheet(db_session, csv_text, _settings(), delay=0.0)

    assert out.imported == 2
    assert out.skipped == 1
    assert out.errors == 0
    assert out.rows_without_link == 1
    assert out.ignored_by_host == {"inconnu.example": 1}
    assert out.unique_supported == 1
    # 1 seul lien supporté unique, importé avec force=False
    assert vus == [("https://www.klikego.com/e/1", False)]


def test_run_import_sheet_un_echec_n_interrompt_pas_le_batch(db_session, monkeypatch):
    from app.scrapers import registry

    monkeypatch.setattr(registry, "detect_provider", lambda url: "klikego")

    def _iter(db, url, settings, force=False):
        if "boom" in url:
            yield {"phase": "error", "message": "échec scrape"}
            return
        yield {"phase": "done", "imported": 1, "skipped": 0, "total": 1}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    csv_text = (
        "a,Donne-nous un lien pour accéder aux résultats.\n"
        "x,https://www.klikego.com/boom\n"
        "x,https://www.klikego.com/ok\n"
    )
    out = bulk_import_service.run_import_sheet(db_session, csv_text, _settings(), delay=0.0)
    assert out.errors == 1
    assert out.imported == 1


def test_run_import_sheet_dry_run_ne_scrape_pas(db_session, monkeypatch):
    from app.scrapers import registry

    monkeypatch.setattr(registry, "detect_provider", lambda url: "klikego")
    _iter, vus = _phases()
    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    csv_text = (
        "a,Donne-nous un lien pour accéder aux résultats.\n"
        "x,https://www.klikego.com/e/1\n"
    )
    out = bulk_import_service.run_import_sheet(
        db_session, csv_text, _settings(), dry_run=True, delay=0.0
    )
    assert vus == []
    assert out.unique_supported == 1


def test_run_import_sheet_only_provider_restreint(db_session, monkeypatch):
    from app.scrapers import registry

    monkeypatch.setattr(
        registry, "detect_provider",
        lambda url: "klikego" if "klikego" in url else "timepulse",
    )
    _iter, vus = _phases(imported=1, skipped=0)
    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    csv_text = (
        "a,Donne-nous un lien pour accéder aux résultats.\n"
        "x,https://www.klikego.com/e/1\n"
        "x,https://www.timepulse.fr/e/2\n"
    )
    out = bulk_import_service.run_import_sheet(
        db_session, csv_text, _settings(), only_provider="klikego", delay=0.0
    )
    assert [url for url, _ in vus] == ["https://www.klikego.com/e/1"]
    assert out.imported == 1


def test_run_import_sheet_libelle_provider_et_url(db_session, monkeypatch, fake_reporter):
    """Le label part du provider + l'URL : le nom de course n'est pas connu avant le scrape."""
    from app.scrapers import registry

    monkeypatch.setattr(registry, "detect_provider", lambda url: "klikego")
    _iter, _ = _phases()
    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    csv_text = (
        "a,Donne-nous un lien pour accéder aux résultats.\n"
        "x,https://www.klikego.com/e/1\n"
    )
    bulk_import_service.run_import_sheet(
        db_session, csv_text, _settings(), delay=0.0, reporter=fake_reporter
    )

    assert ("item_start", 0, "klikego · https://www.klikego.com/e/1") in fake_reporter.calls


def test_run_import_sheet_dry_run_ne_rapporte_aucune_progression(
    db_session, monkeypatch, fake_reporter
):
    from app.scrapers import registry

    monkeypatch.setattr(registry, "detect_provider", lambda url: "klikego")

    csv_text = (
        "a,Donne-nous un lien pour accéder aux résultats.\n"
        "x,https://www.klikego.com/e/1\n"
    )
    bulk_import_service.run_import_sheet(
        db_session, csv_text, _settings(), dry_run=True, delay=0.0, reporter=fake_reporter
    )

    assert fake_reporter.calls == []


def test_run_import_sheet_ctrl_c_remonte_le_drapeau(db_session, monkeypatch):
    from app.scrapers import registry

    monkeypatch.setattr(registry, "detect_provider", lambda url: "klikego")

    def _iter(db, url, settings, force=False):
        raise KeyboardInterrupt
        yield  # pragma: no cover — fait de _iter un générateur

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    csv_text = (
        "a,Donne-nous un lien pour accéder aux résultats.\n"
        "x,https://www.klikego.com/e/1\n"
    )
    out = bulk_import_service.run_import_sheet(db_session, csv_text, _settings(), delay=0.0)

    assert out.interrupted is True
