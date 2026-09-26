from app.core.database import get_db
from app.main import app


def test_health_ok(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] is True


def test_health_is_a_503_when_the_database_is_unreachable(client):
    """The keep-warm probe only reads the HTTP status (#1070)."""

    class _BaseCoupee:
        def execute(self, *args, **kwargs):
            raise OSError("connection refused")

    app.dependency_overrides[get_db] = lambda: _BaseCoupee()

    resp = client.get("/api/v1/health")

    assert resp.status_code == 503
    assert resp.json() == {"status": "degraded", "database": False}
