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
