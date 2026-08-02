"""Dépendances FastAPI partagées."""
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.exceptions import DomainError
from app.models.user import User
from app.services.auth import session as session_service


def settings_dep() -> Settings:
    """Injecte les réglages applicatifs dans les routers."""
    return get_settings()


class NotAuthenticatedError(DomainError):
    """Aucune session valide n'accompagne cette requête."""

    status_code = 401
    message = "Vous devez être connecté pour accéder à cette ressource."


def current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
) -> User:
    """Utilisateur de la session portée par le cookie, ou 401.

    Passe par `services/auth/session.py` et **jamais** par un repository
    directement : c'est là que vit l'invariant à trois conditions (FR-013), et
    le court-circuiter le dupliquerait — c'est précisément ce que fait la PR
    #159, dont le router appelle `user_repository`.

    **Aucune route existante n'en dépend** : la protection des ressources
    d'administration relève de #115, et le site public reste intégralement
    ouvert (FR-035).
    """
    # Import différé : `api/v1/auth.py` importe cette fonction, et l'un des deux
    # doit céder. C'est aussi ce qui donne accès aux en-têtes sans cache sans en
    # recopier les valeurs — un 401 mis en cache empêcherait un connecté de voir
    # sa session (FR-018), et il sort du handler d'exception, hors de portée de
    # la dépendance de router.
    from app.api.v1.auth import ENTETES_SANS_CACHE, session_cookie_name

    jeton = request.cookies.get(session_cookie_name(settings))
    user = session_service.resolve(db, jeton)
    if user is None:
        raise NotAuthenticatedError(headers=ENTETES_SANS_CACHE)
    return user
