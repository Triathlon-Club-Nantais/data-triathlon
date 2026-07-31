"""GitHub OAuth authentication endpoints (issue #114).

See `specs/006-auth-backend-github/contracts/auth-api.md` for the full public
contract. Sessions are carried by the `tcn_session` cookie; the short-lived
`tcn_oauth_state` cookie carries the CSRF state during the OAuth round-trip.
"""
import logging
import secrets

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

OAUTH_STATE_COOKIE_NAME = "tcn_oauth_state"
OAUTH_STATE_MAX_AGE = 10 * 60  # 10 minutes


def get_http_client() -> httpx.Client:
    """Injectable factory — tests override this dependency with a fake client."""
    return httpx.Client(timeout=10.0)


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
    signed_state = auth_service.sign_state(settings.session_secret_key, state)

    authorize_url = auth_service.build_authorize_url(
        client_id=settings.github_oauth_client_id,
        redirect_uri=_redirect_uri(request, settings),
        state=state,
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

    expected_state = auth_service.verify_state(
        settings.session_secret_key, state_cookie, max_age=OAUTH_STATE_MAX_AGE
    )
    if expected_state != state:
        response = _bad_request("État CSRF invalide.")
        _clear_state_cookie(response, settings)
        return response

    if not code:
        response = _bad_request("Autorisation GitHub refusée.")
        _clear_state_cookie(response, settings)
        return response

    try:
        with http as client:
            token = auth_service.exchange_code_for_token(
                client,
                code=code,
                client_id=settings.github_oauth_client_id,
                client_secret=settings.github_oauth_client_secret,
                redirect_uri=_redirect_uri(request, settings),
            )
            identity = auth_service.fetch_github_identity(client, token=token)
    except DomainError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error during GitHub OAuth callback")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Autorisation GitHub refusée.",
        ) from exc

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
        settings.session_secret_key, user_id=user.id
    )
    response = RedirectResponse(
        settings.frontend_post_login_url, status_code=status.HTTP_302_FOUND
    )
    _clear_state_cookie(response, settings)
    _set_session_cookie(response, session_token, settings)
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(settings: Settings = Depends(settings_dep)) -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_session_cookie(response, settings)
    return response


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(current_user)) -> User:
    return user


def _bad_request(detail: str) -> Response:
    """Return a 302 or 400 depending on framework layer.

    We keep a JSON 400 here — the frontend surfaces it as-is.
    """
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST, content={"detail": detail}
    )
