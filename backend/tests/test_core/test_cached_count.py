"""Compteur gardé en mémoire de process (#1352)."""
from app.core import cached_count
from app.core.cached_count import CachedCount


def test_the_value_is_computed_once_within_its_lifetime(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(cached_count.time, "monotonic", lambda: now[0])
    calls = []
    counter = CachedCount(ttl_seconds=60)

    def compute():
        calls.append(1)
        return len(calls)

    assert counter.get(compute) == 1
    now[0] += 59
    assert counter.get(compute) == 1
    now[0] += 2
    assert counter.get(compute) == 2


def test_set_and_clear(monkeypatch):
    counter = CachedCount(ttl_seconds=60)
    counter.set(7)
    assert counter.get(lambda: 0) == 7
    counter.clear()
    assert counter.get(lambda: 3) == 3
