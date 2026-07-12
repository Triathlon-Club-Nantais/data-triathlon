from app.core.config import Settings
from app.services import batch, import_service
from app.services.batch import BatchItem


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def _phases_ok(db, url, settings, force=False):
    """Simule iter_import_event pour une épreuve de 30 participants."""
    yield {"phase": "scraping", "message": "Récupération des participants…"}
    yield {"phase": "saving", "total": 30, "imported": 0, "skipped": 0, "progress": 0}
    yield {"phase": "saving", "total": 30, "imported": 20, "skipped": 0, "progress": 20}
    yield {"phase": "saving", "total": 30, "imported": 28, "skipped": 2, "progress": 30}
    yield {"phase": "done", "imported": 28, "skipped": 2, "total": 30}


def test_run_batch_relaie_la_progression_intra_epreuve(db_session, monkeypatch, fake_reporter):
    monkeypatch.setattr(import_service, "iter_import_event", _phases_ok)

    totals = batch.run_batch(
        db_session, [BatchItem(url="https://k/1", label="klikego · A")], _settings(),
        force=False, delay=0.0, reporter=fake_reporter,
    )

    assert totals.imported == 28
    assert totals.skipped == 2
    assert totals.errors == 0
    assert fake_reporter.calls == [
        ("batch_start", 1),
        ("item_start", 0, "klikego · A"),
        ("item_progress", 0, 30),
        ("item_progress", 20, 30),
        ("item_progress", 30, 30),
        ("item_done", 28, 2, None),
        ("batch_end",),
    ]


def test_run_batch_phase_error_compte_une_erreur_sans_interrompre(
    db_session, monkeypatch, fake_reporter
):
    def _phases(db, url, settings, force=False):
        if "boom" in url:
            yield {"phase": "error", "message": "timeout scrape"}
            return
        yield from _phases_ok(db, url, settings, force)

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    totals = batch.run_batch(
        db_session,
        [BatchItem(url="https://k/boom", label="A"), BatchItem(url="https://k/ok", label="B")],
        _settings(), force=False, delay=0.0, reporter=fake_reporter,
    )

    assert totals.errors == 1
    assert totals.imported == 28  # la 2e épreuve a bien été traitée
    assert ("item_done", 0, 0, "timeout scrape") in fake_reporter.calls


def test_run_batch_une_exception_reelle_compte_aussi_une_erreur(db_session, monkeypatch):
    def _phases(db, url, settings, force=False):
        raise RuntimeError("bug inattendu")
        yield  # pragma: no cover — fait de _phases un générateur

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    totals = batch.run_batch(
        db_session, [BatchItem(url="https://k/1", label="A")], _settings(),
        force=False, delay=0.0,
    )

    assert totals.errors == 1
    assert totals.imported == 0


def test_run_batch_ctrl_c_conserve_le_travail_deja_fait(db_session, monkeypatch, fake_reporter):
    def _phases(db, url, settings, force=False):
        if "stop" in url:
            raise KeyboardInterrupt
        yield from _phases_ok(db, url, settings, force)

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    totals = batch.run_batch(
        db_session,
        [BatchItem(url="https://k/ok", label="A"), BatchItem(url="https://k/stop", label="B"),
         BatchItem(url="https://k/jamais", label="C")],
        _settings(), force=False, delay=0.0, reporter=fake_reporter,
    )

    assert totals.interrupted is True
    assert totals.imported == 28   # la 1re épreuve est conservée
    assert totals.errors == 0      # une interruption n'est pas une erreur
    assert ("item_start", 2, "C") not in fake_reporter.calls  # la 3e n'a pas démarré
    assert fake_reporter.calls[-1] == ("batch_end",)          # les barres sont bien fermées


def test_run_batch_transmet_force_au_generateur(db_session, monkeypatch):
    vus: list[bool] = []

    def _phases(db, url, settings, force=False):
        vus.append(force)
        yield {"phase": "done", "imported": 1, "skipped": 0, "total": 1}

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    batch.run_batch(
        db_session, [BatchItem(url="https://k/1", label="A")], _settings(),
        force=True, delay=0.0,
    )

    assert vus == [True]


def test_run_batch_sans_reporter_ne_leve_pas(db_session, monkeypatch):
    monkeypatch.setattr(import_service, "iter_import_event", _phases_ok)

    totals = batch.run_batch(
        db_session, [BatchItem(url="https://k/1", label="A")], _settings(),
        force=False, delay=0.0,
    )

    assert totals.imported == 28  # NullReporter par défaut
