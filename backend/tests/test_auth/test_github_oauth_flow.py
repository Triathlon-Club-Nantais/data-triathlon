"""Tests for the GitHub OAuth flow endpoints (issue #114)."""
from urllib.parse import parse_qs, urlparse

from app.models import User

# ---------------------------------------------------------------------------
# Nominal flow — authorize → callback → me → logout
# ---------------------------------------------------------------------------


def test_authorize_redirects_to_github_and_sets_state_cookie(client_with_auth):
    resp = client_with_auth.get(
        "/api/v1/auth/github/authorize", follow_redirects=False
    )

    assert resp.status_code == 302
    location = resp.headers["location"]
    parsed = urlparse(location)
    assert parsed.hostname == "github.com"
    assert parsed.path == "/login/oauth/authorize"

    qs = parse_qs(parsed.query)
    assert qs["client_id"] == ["test-client-id"]
    assert qs["scope"] == ["user:email"]
    assert qs["state"][0]
    assert qs["redirect_uri"] == [
        "http://testserver/api/v1/auth/github/callback"
    ]

    assert "tcn_oauth_state" in resp.cookies


def test_callback_creates_user_and_opens_session(
    client_with_auth, db_session, fake_http, github_user_payload
):
    # 1. authorize → capture the state cookie
    auth_resp = client_with_auth.get(
        "/api/v1/auth/github/authorize", follow_redirects=False
    )
    state = parse_qs(urlparse(auth_resp.headers["location"]).query)["state"][0]

    fake_http.queue_token({"access_token": "gho_test", "token_type": "bearer"})
    fake_http.queue_user(github_user_payload)

    # 2. callback
    cb_resp = client_with_auth.get(
        "/api/v1/auth/github/callback",
        params={"code": "irrelevant-code", "state": state},
        follow_redirects=False,
    )

    assert cb_resp.status_code == 302
    assert cb_resp.headers["location"] == "http://frontend.local/admin"
    assert "tcn_session" in cb_resp.cookies
    # state cookie is cleared after use
    assert cb_resp.cookies.get("tcn_oauth_state", "") in ("", None)

    # 3. a user was persisted
    users = db_session.query(User).all()
    assert len(users) == 1
    assert users[0].github_id == str(github_user_payload["id"])
    assert users[0].github_login == github_user_payload["login"]
    assert users[0].email == github_user_payload["email"]


def test_second_callback_upserts_user_and_opens_new_session(
    client_with_auth, db_session, fake_http, github_user_payload
):
    # first login
    _login(client_with_auth, fake_http, github_user_payload)
    # second login
    _login(client_with_auth, fake_http, github_user_payload)

    assert db_session.query(User).count() == 1


def test_me_returns_user_for_valid_session(
    client_with_auth, fake_http, github_user_payload
):
    _login(client_with_auth, fake_http, github_user_payload)

    resp = client_with_auth.get("/api/v1/auth/me")

    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == github_user_payload["email"]
    assert body["github_login"] == github_user_payload["login"]
    assert "github_id" not in body


def test_me_returns_401_without_session(client_with_auth):
    resp = client_with_auth.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_logout_clears_session_cookie(
    client_with_auth, fake_http, github_user_payload
):
    _login(client_with_auth, fake_http, github_user_payload)

    resp = client_with_auth.post("/api/v1/auth/logout")

    assert resp.status_code == 204
    assert 'tcn_session=""' in resp.headers.get(
        "set-cookie", ""
    ) or "tcn_session=;" in resp.headers.get("set-cookie", "")


def test_logout_is_noop_without_session(client_with_auth):
    """FR-014 — logout is idempotent even for an anonymous caller."""
    resp = client_with_auth.post("/api/v1/auth/logout")
    assert resp.status_code == 204
    # Set-Cookie header is emitted anyway (Max-Age=0 clears anything the client had)
    assert "tcn_session" in resp.headers.get("set-cookie", "")


# ---------------------------------------------------------------------------
# Email absent from /user — fallback to /user/emails
# ---------------------------------------------------------------------------


def test_callback_falls_back_to_user_emails_when_email_is_null(
    client_with_auth,
    db_session,
    fake_http,
    github_user_payload,
    github_user_emails_payload,
):
    state = _fetch_state(client_with_auth)

    payload_without_email = {**github_user_payload, "email": None}
    fake_http.queue_token({"access_token": "gho_test"})
    fake_http.queue_user(payload_without_email)
    fake_http.queue_emails(github_user_emails_payload)

    resp = client_with_auth.get(
        "/api/v1/auth/github/callback",
        params={"code": "c", "state": state},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    user = db_session.query(User).first()
    # first verified+primary email in the fixture
    assert user.email == "octocat-hidden@example.com"


# ---------------------------------------------------------------------------
# Rejection cases (US3 / T024)
# ---------------------------------------------------------------------------


def test_callback_rejects_missing_state(client_with_auth):
    resp = client_with_auth.get(
        "/api/v1/auth/github/callback",
        params={"code": "c"},
        follow_redirects=False,
    )
    assert resp.status_code in (400, 422)


def test_callback_rejects_state_without_cookie(client_with_auth):
    resp = client_with_auth.get(
        "/api/v1/auth/github/callback",
        params={"code": "c", "state": "made-up"},
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert "CSRF" in resp.json()["detail"].upper() or "état" in resp.json()["detail"].lower()


def test_callback_rejects_state_mismatch(client_with_auth):
    # obtain a valid state cookie
    client_with_auth.get("/api/v1/auth/github/authorize", follow_redirects=False)
    # but pass a different state value in the query
    resp = client_with_auth.get(
        "/api/v1/auth/github/callback",
        params={"code": "c", "state": "not-the-real-state"},
        follow_redirects=False,
    )
    assert resp.status_code == 400


def test_callback_rejects_when_github_denies_authorization(client_with_auth):
    state = _fetch_state(client_with_auth)
    resp = client_with_auth.get(
        "/api/v1/auth/github/callback",
        params={"code": "", "state": state, "error": "access_denied"},
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert "github" in resp.json()["detail"].lower()


def test_callback_rejects_when_token_exchange_fails(
    client_with_auth, fake_http
):
    state = _fetch_state(client_with_auth)
    fake_http.queue_token({"error": "bad_verification_code"}, status=200)

    resp = client_with_auth.get(
        "/api/v1/auth/github/callback",
        params={"code": "bad", "state": state},
        follow_redirects=False,
    )
    assert resp.status_code == 400


def test_callback_rejects_when_no_verified_email_available(
    client_with_auth, fake_http, github_user_payload
):
    state = _fetch_state(client_with_auth)
    fake_http.queue_token({"access_token": "gho_test"})
    fake_http.queue_user({**github_user_payload, "email": None})
    # only unverified emails
    fake_http.queue_emails(
        [{"email": "x@y", "primary": True, "verified": False}]
    )

    resp = client_with_auth.get(
        "/api/v1/auth/github/callback",
        params={"code": "c", "state": state},
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert "email" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fetch_state(client) -> str:
    resp = client.get("/api/v1/auth/github/authorize", follow_redirects=False)
    return parse_qs(urlparse(resp.headers["location"]).query)["state"][0]


def _login(client, fake_http, github_user_payload):
    state = _fetch_state(client)
    fake_http.queue_token({"access_token": "gho_test"})
    fake_http.queue_user(github_user_payload)
    return client.get(
        "/api/v1/auth/github/callback",
        params={"code": "c", "state": state},
        follow_redirects=False,
    )
