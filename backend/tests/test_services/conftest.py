import threading
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db_session_concurrent(tmp_path):
    """Session SQLAlchemy sur un fichier SQLite réel — pas `db_session`.

    `db_session` (conftest racine) utilise `StaticPool` : toutes ses `Session`
    partagent la **même** connexion DBAPI unique, jamais sûr à utiliser depuis
    plusieurs threads en même temps. Un vrai fichier donne, comme en
    production (pool réel sur Postgres), une connexion distincte par
    `Session` — nécessaire pour exercer un `run_batch` réellement
    multi-thread sans dépendre d'un artefact du fixture de test.
    """
    import app.models  # noqa: F401 — enregistre toutes les tables sur Base.metadata
    from app.core.database import Base

    engine = create_engine(
        f"sqlite:///{tmp_path / 'test-concurrent.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class ConcurrencyGauge:
    """Jauge du nombre d'exécutions simultanées d'un bloc, et de son pic.

    Preuve de concurrence sans dépendre d'un `sleep()` minuté : `track()`
    incrémente/décrémente un compteur verrouillé autour du code à observer, et
    retient le maximum jamais atteint.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current = 0
        self.peak = 0

    @contextmanager
    def track(self):
        with self._lock:
            self._current += 1
            self.peak = max(self.peak, self._current)
        try:
            yield
        finally:
            with self._lock:
                self._current -= 1


@pytest.fixture
def concurrency_gauge() -> ConcurrencyGauge:
    return ConcurrencyGauge()


class FakeReporter:
    """Sonde de progression : enregistre les appels reçus, dans l'ordre."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def batch_start(self, total: int) -> None:
        self.calls.append(("batch_start", total))

    def item_start(self, index: int, label: str, host: str) -> None:
        self.calls.append(("item_start", index, label, host))

    def item_progress(self, done: int, total: int, host: str) -> None:
        self.calls.append(("item_progress", done, total, host))

    def item_done(self, imported: int, skipped: int, error: str | None, host: str) -> None:
        self.calls.append(("item_done", imported, skipped, error, host))

    def batch_end(self) -> None:
        self.calls.append(("batch_end",))


@pytest.fixture
def fake_reporter() -> FakeReporter:
    return FakeReporter()


@pytest.fixture
def patch_scraper(monkeypatch):
    """Substitue au registre de scrapers une liste de résultats déjà prête.

    Recopiée à l'identique dans quatre modules jusqu'à #590, dont un seul disait
    pourquoi `**kwargs` est là — c'est `cache_probe` (fan-out Klikego #156), que
    l'appelant passe et que la doublure ne consulte pas.
    """
    from app.services import import_service

    def _set(results):
        monkeypatch.setattr(
            import_service, "registry_scrape_event_all", lambda url, **kwargs: results
        )

    return _set
