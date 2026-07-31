"""Dépendances FastAPI partagées."""
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.models.user import User
from app.repositories import user_repository
from app.services import auth_service

SESSION_COOKIE_NAME = "tcn_session"


def settings_dep() -> Settings:
    """Injecte les réglages applicatifs dans les routers."""
    return get_settings()


def _resolve_session_user(
    request: Request, db: Session, settings: Settings
) -> User | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token or not settings.session_secret_key:
        return None
    user_id = auth_service.verify_session(
        settings.session_secret_key, token, max_age=settings.session_max_age_seconds
    )
    if user_id is None:
        return None
    user = user_repository.get(db, user_id)
    if user is None or not user.is_active:
        return None
    return user


def current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
) -> User:
    """Return the authenticated user or raise 401."""
    user = _resolve_session_user(request, db, settings)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Non authentifié."
        )
    return user


def current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
) -> User | None:
    """Return the authenticated user or None — never raises."""
    return _resolve_session_user(request, db, settings)
