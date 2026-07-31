"""GitHub OAuth authentication endpoints (issue #114).

See `specs/006-auth-backend-github/contracts/auth-api.md` for the full public
contract. Sessions are carried by the `tcn_session` cookie; the short-lived
`tcn_oauth_state` cookie carries the CSRF state during the OAuth round-trip.
"""
import logging
import secrets

import httpx
from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import SESSION_COOKIE_NAME, current_user, settings_dep
from app.core.config import Settings
from app.core.database import get_db
from app.core.exceptions import AuthConfigurationError, DomainError
from app.models.user import User
from app.repositories import user_repository
from app.schemas.user import UserRead
from app.services import auth_service
from app.services.auth_service import NoVerifiedEmailError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

OAUTH_STATE_COOKIE_NAME = "tcn_oauth_state"
OAUTH_STATE_MAX_AGE = 10 * 60  # 10 minutes


def get_http_client():
    """Injectable factory — tests override this dependency with a fake client.

    Yields an `httpx.Client` inside a context manager so FastAPI closes it on
    every exit path (nominal or exceptional). A plain `return httpx.Client(...)`
    leaks the client on every callback that fails before the `with http as
    client:` block used to exist — that was the DoS surface described in
    review B3 of PR #159.
    """
    with httpx.Client(timeout=5.0) as client:
        yield client


def _require_auth_configured(settings: Settings) -> None:
    if not (
        settings.github_oauth_client_id
        and settings.github_oauth_client_secret
        and settings.session_secret_key
    ):
        raise AuthConfigurationError()


def _redirect_uri(request: Request, settings: Settings) -> str:
    if settings.github_oauth_redirect_url:
        return settings.github_oauth_redirect_url
    return str(request.url_for("github_callback"))


def _login_is_allowed(github_login: str, settings: Settings) -> bool:
    """Allowlist check (B2). Empty list = every account accepted (dev default)."""
    allowlist = settings.github_allowed_logins
    if not allowlist:
        return True
    return github_login.lower() in {login.lower() for login in allowlist}


def _set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response, settings: Settings) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value="",
        max_age=0,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def _set_state_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=OAUTH_STATE_COOKIE_NAME,
        value=token,
        max_age=OAUTH_STATE_MAX_AGE,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/api/v1/auth/github/",
    )


def _clear_state_cookie(response: Response, settings: Settings) -> None:
    response.set_cookie(
        key=OAUTH_STATE_COOKIE_NAME,
        value="",
        max_age=0,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/api/v1/auth/github/",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/github/authorize", name="github_authorize")
def github_authorize(
    request: Request, settings: Settings = Depends(settings_dep)
) -> RedirectResponse:
    _require_auth_configured(settings)

    state = secrets.token_urlsafe(32)
    verifier = auth_service.generate_pkce_verifier()
    signed_state = auth_service.sign_state(
        settings.session_secret_key, state, verifier=verifier
    )

    authorize_url = auth_service.build_authorize_url(
        client_id=settings.github_oauth_client_id,
        redirect_uri=_redirect_uri(request, settings),
        state=state,
        code_challenge=auth_service.pkce_challenge(verifier),
    )
    response = RedirectResponse(authorize_url, status_code=status.HTTP_302_FOUND)
    _set_state_cookie(response, signed_state, settings)
    return response


@router.get("/github/callback", name="github_callback")
def github_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    state_cookie: str | None = Cookie(default=None, alias=OAUTH_STATE_COOKIE_NAME),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    http: httpx.Client = Depends(get_http_client),
) -> RedirectResponse:
    _require_auth_configured(settings)

    if error:
        response = _bad_request("Autorisation GitHub refusée.")
        _clear_state_cookie(response, settings)
        return response

    if not state or not state_cookie:
        response = _bad_request("État CSRF invalide.")
        _clear_state_cookie(response, settings)
        return response

    verified = auth_service.verify_state(
        settings.session_secret_key, state_cookie, max_age=OAUTH_STATE_MAX_AGE
    )
    if verified is None or verified[0] != state:
        response = _bad_request("État CSRF invalide.")
        _clear_state_cookie(response, settings)
        return response
    _, code_verifier = verified

    if not code:
        response = _bad_request("Autorisation GitHub refusée.")
        _clear_state_cookie(response, settings)
        return response

    try:
        token = auth_service.exchange_code_for_token(
            http,
            code=code,
            client_id=settings.github_oauth_client_id,
            client_secret=settings.github_oauth_client_secret,
            redirect_uri=_redirect_uri(request, settings),
            code_verifier=code_verifier,
        )
        identity = auth_service.fetch_github_identity(http, token=token)
    except NoVerifiedEmailError as exc:
        # 422 with state cookie cleared (research.md: "supprimé quelle que soit l'issue")
        response = _json_response(status.HTTP_422_UNPROCESSABLE_ENTITY, exc.message)
        _clear_state_cookie(response, settings)
        return response
    except DomainError:
        raise
    except httpx.HTTPError:
        logger.exception("HTTP error during GitHub OAuth callback")
        response = _json_response(
            status.HTTP_400_BAD_REQUEST, "Autorisation GitHub refusée."
        )
        _clear_state_cookie(response, settings)
        return response

    if not _login_is_allowed(identity["github_login"], settings):
        logger.warning(
            "auth.github.rejected login=%s (not in GITHUB_ALLOWED_LOGINS)",
            identity["github_login"],
        )
        response = _json_response(
            status.HTTP_403_FORBIDDEN, "Compte GitHub non autorisé pour ce site."
        )
        _clear_state_cookie(response, settings)
        return response

    user, created = user_repository.upsert_from_github(
        db,
        github_id=identity["github_id"],
        github_login=identity["github_login"],
        email=identity["email"],
    )
    db.commit()
    logger.info(
        "auth.github.login user_id=%s created=%s login=%s",
        user.id,
        created,
        user.github_login,
    )

    session_token = auth_service.sign_session(
        settings.session_secret_key, user_id=user.id, epoch=user.session_epoch
    )
    response = RedirectResponse(
        settings.frontend_post_login_url, status_code=status.HTTP_302_FOUND
    )
    _clear_state_cookie(response, settings)
    _set_session_cookie(response, session_token, settings)
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
) -> Response:
    """Invalidate the session and every other cookie of the same user (B4)."""
    if settings.session_secret_key:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if token:
            payload = auth_service.verify_session(
                settings.session_secret_key,
                token,
                max_age=settings.session_max_age_seconds,
            )
            if payload is not None:
                user_id, _ = payload
                user = user_repository.get(db, user_id)
                if user is not None:
                    user.session_epoch += 1
                    db.commit()

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_session_cookie(response, settings)
    return response


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(current_user)) -> User:
    return user


def _bad_request(detail: str) -> Response:
    """Return a JSON 400 with a French detail string.

    UX caveat: this response is served to a browser mid-navigation (the user
    landed on /callback from GitHub). It shows a raw JSON page. The frontend
    (#116) is expected to intercept these callback errors and redirect to a
    friendly page — until then, the browser is where the buck stops. Kept as
    a 400 to preserve the contract in `contracts/auth-api.md`.
    """
    return _json_response(status.HTTP_400_BAD_REQUEST, detail)


def _json_response(status_code: int, detail: str) -> Response:
    """Helper: build a JSON error response so we can set cookies before returning."""
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=status_code, content={"detail": detail})
