"""Auth flow helpers — cookie signing, GitHub OAuth exchange, identity fetch.

Never touches the SQLAlchemy Session (Principe II). The router wires this
module to `user_repository` and to httpx.
"""
import base64
import hashlib
import secrets as py_secrets
from typing import Any
from urllib.parse import urlencode

import httpx
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.exceptions import DomainError

_SESSION_SALT = "tcn-session"
_STATE_SALT = "tcn-oauth-state"
_SESSION_VERSION = 1

_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"  # noqa: S105 (public URL)
_GITHUB_API_USER = "https://api.github.com/user"
_GITHUB_API_EMAILS = "https://api.github.com/user/emails"


class NoVerifiedEmailError(DomainError):
    status_code = 422
    message = "Aucun email GitHub vérifié disponible."


# ---------------------------------------------------------------------------
# Cookie signing (session + short-lived OAuth state)
# ---------------------------------------------------------------------------


def _session_serializer(secret_key: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key, salt=_SESSION_SALT)


def _state_serializer(secret_key: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key, salt=_STATE_SALT)


def sign_session(secret_key: str, user_id: int, epoch: int = 0) -> str:
    return _session_serializer(secret_key).dumps(
        {"uid": user_id, "epoch": epoch, "v": _SESSION_VERSION}
    )


def verify_session(
    secret_key: str, token: str, max_age: int
) -> tuple[int, int] | None:
    """Return `(user_id, epoch)` if the cookie is valid, else `None`.

    The caller compares `epoch` against `User.session_epoch` to reject
    cookies issued before the last logout of that user. Cf. review B4.
    """
    try:
        payload = _session_serializer(secret_key).loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(payload, dict) or payload.get("v") != _SESSION_VERSION:
        return None
    uid = payload.get("uid")
    if not isinstance(uid, int):
        return None
    epoch = payload.get("epoch", 0)
    if not isinstance(epoch, int):
        return None
    return uid, epoch


def sign_state(secret_key: str, state: str, verifier: str | None = None) -> str:
    """Sign the CSRF `state` together with the PKCE `verifier`.

    Backwards-compatible: an older cookie carrying just a `str` is still
    parseable via `verify_state`. When `verifier` is None, the signed value
    is a plain string (legacy shape); otherwise it's `{"s": state, "v": verifier}`.
    """
    payload = {"s": state, "v": verifier} if verifier is not None else state
    return _state_serializer(secret_key).dumps(payload)


def verify_state(
    secret_key: str, token: str, max_age: int
) -> tuple[str, str | None] | None:
    """Return `(state, verifier|None)` if the cookie is valid, else `None`."""
    try:
        value = _state_serializer(secret_key).loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if isinstance(value, str):
        return value, None
    if isinstance(value, dict) and isinstance(value.get("s"), str):
        verifier = value.get("v")
        if verifier is not None and not isinstance(verifier, str):
            return None
        return value["s"], verifier
    return None


# ---------------------------------------------------------------------------
# PKCE (S256) — B5 of PR #159 review
# ---------------------------------------------------------------------------


def generate_pkce_verifier() -> str:
    """43-char urlsafe verifier (RFC 7636 §4.1: min 43, max 128, unreserved chars)."""
    return py_secrets.token_urlsafe(32)


def pkce_challenge(verifier: str) -> str:
    """S256 challenge = base64url(SHA-256(verifier)) without padding."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


# ---------------------------------------------------------------------------
# GitHub OAuth flow
# ---------------------------------------------------------------------------


def build_authorize_url(
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str | None = None,
) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "user:email",
        "state": state,
    }
    if code_challenge is not None:
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"
    return f"{_GITHUB_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code_for_token(
    http: httpx.Client | Any,
    *,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code_verifier: str | None = None,
) -> str:
    """Exchange the authorization code for an access token.

    Raises DomainError with a French, user-facing message on failure.
    """
    body = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    if code_verifier is not None:
        body["code_verifier"] = code_verifier
    response = http.post(
        _GITHUB_TOKEN_URL,
        headers={"Accept": "application/json"},
        data=body,
    )
    if not response.is_success:
        raise DomainError("Autorisation GitHub refusée.")

    payload = response.json() or {}
    token = payload.get("access_token")
    if not token:
        raise DomainError("Autorisation GitHub refusée.")
    return str(token)


def fetch_github_identity(
    http: httpx.Client | Any, *, token: str
) -> dict[str, str]:
    """Return `{github_id, github_login, email}` for the token holder.

    Falls back to /user/emails when the primary email is not exposed publicly.
    Raises NoVerifiedEmailError when no verified email can be found.
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
    }
    user_resp = http.get(_GITHUB_API_USER, headers=headers)
    if not user_resp.is_success:
        raise DomainError("Autorisation GitHub refusée.")

    user = user_resp.json() or {}
    github_id = user.get("id")
    github_login = user.get("login")
    if github_id is None or not github_login:
        raise DomainError("Autorisation GitHub refusée.")

    email = user.get("email")
    if not email:
        emails_resp = http.get(_GITHUB_API_EMAILS, headers=headers)
        if not emails_resp.is_success:
            raise NoVerifiedEmailError()
        email = _pick_verified_email(emails_resp.json() or [])

    if not email:
        raise NoVerifiedEmailError()

    return {
        "github_id": str(github_id),
        "github_login": str(github_login),
        "email": str(email),
    }


def _pick_verified_email(emails: list[dict]) -> str | None:
    for entry in emails:
        if entry.get("verified") and entry.get("primary"):
            return entry.get("email")
    for entry in emails:
        if entry.get("verified"):
            return entry.get("email")
    return None
