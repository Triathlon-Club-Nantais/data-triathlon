"""Calcul gardé en mémoire de process (#1352, #1384)."""
import threading

from app.core import cached_value
from app.core.cached_value import CachedValue


def test_the_value_is_computed_once_within_its_lifetime(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(cached_value.time, "monotonic", lambda: now[0])
    calls = []
    cache = CachedValue(ttl_seconds=60)

    def compute():
        calls.append(1)
        return len(calls)

    assert cache.get(compute) == 1
    now[0] += 59
    assert cache.get(compute) == 1
    now[0] += 2
    assert cache.get(compute) == 2


def test_a_value_computed_across_a_clear_is_not_kept():
    cache = CachedValue(ttl_seconds=60)

    def compute_while_a_commit_lands():
        cache.clear()
        return 7

    assert cache.get(compute_while_a_commit_lands) == 7
    assert cache.get(lambda: 3) == 3


def test_concurrent_misses_compute_once():
    # La liste et sa pastille arrivent ensemble après chaque écriture (#1384).
    cache = CachedValue(ttl_seconds=60)
    started, release = threading.Event(), threading.Event()
    calls = []

    def compute():
        calls.append(1)
        started.set()
        release.wait(5)
        return 7

    first = threading.Thread(target=cache.get, args=(compute,))
    first.start()
    started.wait(5)
    second = threading.Thread(target=cache.get, args=(compute,))
    second.start()
    release.set()
    first.join(5)
    second.join(5)

    assert len(calls) == 1


def test_a_clear_is_not_held_up_by_a_running_compute():
    cache = CachedValue(ttl_seconds=60)
    started, release = threading.Event(), threading.Event()

    def compute():
        started.set()
        release.wait(5)
        return 7

    worker = threading.Thread(target=cache.get, args=(compute,))
    worker.start()
    started.wait(5)
    clearing = threading.Thread(target=cache.clear)
    clearing.start()
    clearing.join(1)
    cleared_while_computing = not clearing.is_alive()
    release.set()
    worker.join(5)

    assert cleared_while_computing
    assert cache.get(lambda: 3) == 3


def test_any_commit_clears_every_value(db_session):
    cache = CachedValue(ttl_seconds=60)
    cache.get(lambda: 7)

    db_session.commit()

    assert cache.get(lambda: 3) == 3
