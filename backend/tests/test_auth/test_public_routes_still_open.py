"""SC-001 — every public endpoint keeps responding without a session (issue #114)."""
import pytest


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/v1/health"),
        ("GET", "/api/v1/courses"),
        ("GET", "/api/v1/athletes"),
        ("GET", "/api/v1/stats"),
        ("GET", "/api/v1/stats/seasons"),
    ],
)
def test_public_endpoints_answer_without_session(client, method, path):
    """Anonymous callers keep getting a 2xx from the public endpoints."""
    resp = client.request(method, path)
    assert resp.status_code < 400, (
        f"{method} {path} should stay open without a session (got {resp.status_code})"
    )
    # No auth cookie should be issued by a public endpoint.
    set_cookie = resp.headers.get("set-cookie", "")
    assert "tcn_session" not in set_cookie


def test_auth_me_is_the_only_endpoint_that_401s_without_a_session(client):
    """/auth/me is the sole endpoint that requires a session (FR-015)."""
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
