"""Session du mot de passe partagé du site (#509).

Couche mince : `require_site_access` (`api/deps.py`) garde la vérification,
elle-même **auto-appliquée** ici sur `GET /site-access/session` — c'est le
point que le frontend interroge pour savoir s'il doit rediriger vers
`/acces`. `POST`/`DELETE` restent non gardées : la première pose le cookie,
la seconde n'a aucun effet de bord sensible.
"""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import NotAuthenticatedError, require_site_access
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.repositories import site_access_config_repository
from app.schemas.site_access import SiteAccessLogin
from app.services import site_access

router = APIRouter(tags=["site-access"])


@router.post("/site-access/session", status_code=204)
def open_session(
    body: SiteAccessLogin,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    config = site_access_config_repository.get_config(db)
    if config is None or not site_access.verify_password(
        body.password, password_hash=config.password_hash, password_salt=config.password_salt
    ):
        raise NotAuthenticatedError("Mot de passe incorrect.")

    response.set_cookie(
        key=site_access.SITE_SESSION_COOKIE,
        value=site_access.sign_session(config.session_secret),
        max_age=settings.site_access_session_ttl_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


@router.delete("/site-access/session", status_code=204)
def close_session(response: Response, settings: Settings = Depends(get_settings)):
    response.delete_cookie(
        key=site_access.SITE_SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
    )


@router.get("/site-access/session", dependencies=[Depends(require_site_access)])
def check_session():
    """Le frontend l'appelle via `serverFetchAuthed` : 200 si la session est
    valide, 401 sinon (levé par `require_site_access` avant d'atteindre ce corps)."""
    return {"ok": True}
