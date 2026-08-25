import pytest


class FakeReporter:
    """Sonde de progression : enregistre les appels reçus, dans l'ordre."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def batch_start(self, total: int) -> None:
        self.calls.append(("batch_start", total))

    def item_start(self, index: int, label: str) -> None:
        self.calls.append(("item_start", index, label))

    def item_progress(self, done: int, total: int) -> None:
        self.calls.append(("item_progress", done, total))

    def item_done(self, imported: int, skipped: int, error: str | None) -> None:
        self.calls.append(("item_done", imported, skipped, error))

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
