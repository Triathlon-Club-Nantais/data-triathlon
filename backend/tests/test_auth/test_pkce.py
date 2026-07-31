"""B5 — PKCE (S256) sur le flux OAuth GitHub.

GitHub a ajouté PKCE aux OAuth Apps le 14 juillet 2025 (S256 uniquement).
Il couvre la fuite du `code` avant échange (log de proxy, Referer,
historique) : sans le verifier, un `code` intercepté seul reste inutile.
"""
import base64
import hashlib
from urllib.parse import parse_qs, urlparse


def test_pkce_challenge_is_base64url_of_sha256_of_verifier():
    from app.services import auth_service

    verifier = auth_service.generate_pkce_verifier()
    assert 43 <= len(verifier) <= 128  # RFC 7636 §4.1

    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    assert auth_service.pkce_challenge(verifier) == expected


def test_authorize_url_carries_pkce_parameters(client_with_auth):
    resp = client_with_auth.get(
        "/api/v1/auth/github/authorize", follow_redirects=False
    )
    qs = parse_qs(urlparse(resp.headers["location"]).query)
    assert qs["code_challenge_method"] == ["S256"]
    challenge = qs["code_challenge"][0]
    # base64url without padding: only unreserved chars, no `=`
    assert challenge
    assert "=" not in challenge


def test_callback_sends_code_verifier_to_github(
    client_with_auth, fake_http, github_user_payload
):
    """The verifier stored in the state cookie must reach GitHub's token endpoint."""
    resp = client_with_auth.get(
        "/api/v1/auth/github/authorize", follow_redirects=False
    )
    state = parse_qs(urlparse(resp.headers["location"]).query)["state"][0]

    fake_http.queue_token({"access_token": "gho_test"})
    fake_http.queue_user(github_user_payload)

    client_with_auth.get(
        "/api/v1/auth/github/callback",
        params={"code": "c", "state": state},
        follow_redirects=False,
    )

    token_calls = [c for c in fake_http.calls if c[0] == "POST"]
    assert token_calls, "no POST to token endpoint recorded"
    body = token_calls[0][2].get("data", {})
    assert "code_verifier" in body
    assert body["code_verifier"]


def test_verify_state_reads_back_the_verifier():
    from app.services import auth_service

    signed = auth_service.sign_state("k", "the-state", verifier="the-verifier")
    result = auth_service.verify_state("k", signed, max_age=60)
    assert result == ("the-state", "the-verifier")


def test_verify_state_still_parses_legacy_string_payload():
    """Backwards compat: an old cookie storing only the string state still parses."""
    from app.services import auth_service

    signed = auth_service.sign_state("k", "the-state")  # no verifier
    result = auth_service.verify_state("k", signed, max_age=60)
    assert result == ("the-state", None)
