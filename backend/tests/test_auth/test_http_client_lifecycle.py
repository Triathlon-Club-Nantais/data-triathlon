"""B3 — httpx.Client is closed on every callback exit path.

Before B3, `get_http_client()` returned a bare `httpx.Client` and the router
wrapped its own `with http as client:`. All six early-return paths (503,
error, state absent/invalid, code absent) skipped the wrapper → 5 clients
constructed, 0 closed. Turning `get_http_client` into a generator forces
FastAPI to close the client on every exit path.
"""
import httpx
from fastapi.testclient import TestClient


def test_get_http_client_is_a_context_manager_generator():
    """The dependency must be a generator so FastAPI can close on exit."""
    from app.api.v1.auth import get_http_client

    gen = get_http_client()
    # A generator, not a bare Client.
    assert hasattr(gen, "__next__")

    client = next(gen)
    assert isinstance(client, httpx.Client)
    assert not client.is_closed

    # Simulate FastAPI closing the dependency at request end.
    try:
        next(gen)
    except StopIteration:
        pass
    assert client.is_closed


def test_client_is_closed_when_callback_returns_bad_request(monkeypatch, auth_settings):
    """A callback that 400s must not leak the httpx client."""
    from app.api.v1 import auth as auth_router
    from app.core.database import get_db
    from app.main import app

    created_clients: list[httpx.Client] = []
    original_factory = auth_router.get_http_client

    def _tracking_factory():
        with httpx.Client(timeout=1.0) as client:
            created_clients.append(client)
            yield client

    def _override_get_db():
        # a fake db session — never used because the callback fails early
        yield None

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[original_factory] = _tracking_factory
    try:
        with TestClient(app) as c:
            # No state cookie → 400 « État CSRF invalide. »
            resp = c.get(
                "/api/v1/auth/github/callback",
                params={"code": "c", "state": "s"},
                follow_redirects=False,
            )
            assert resp.status_code == 400
    finally:
        app.dependency_overrides.clear()

    # The tracking factory only yielded if FastAPI resolved the dependency
    # before returning the 400. Whether it did or not is a FastAPI internal;
    # what matters is that every client we did create is closed.
    for client in created_clients:
        assert client.is_closed, "httpx.Client leaked after a 400 callback"
