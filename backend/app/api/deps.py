"""Dépendances FastAPI partagées."""
import logging
from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.exceptions import DomainError
from app.core.permissions import Permission
from app.models.user import User
from app.repositories import benevole_config_repository
from app.services import benevole_access
from app.services.auth import authorization
from app.services.auth import session as session_service

logger = logging.getLogger(__name__)


class NotAuthenticatedError(DomainError):
    """Aucune session valide n'accompagne cette requête."""

    status_code = 401
    message = "Vous devez être connecté pour accéder à cette ressource."


class InsufficientPermissionError(DomainError):
    """Session valide, pouvoir absent.

    Le message **ne nomme ni le pouvoir exigé, ni ceux portés** (FR-019) : un
    refus n'a pas à dresser la carte des droits pour qui insiste. Le diagnostic
    passe par le journal, côté serveur.
    """

    status_code = 403
    message = "Vous n'avez pas les droits nécessaires pour cette action."


def current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
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
    from app.api.v1.auth import NO_STORE_HEADERS, session_cookie_name

    token = request.cookies.get(session_cookie_name(settings))
    user = session_service.resolve(db, token)
    if user is None:
        raise NotAuthenticatedError(headers=NO_STORE_HEADERS)
    return user


def optional_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User | None:
    """Utilisateur de la session portée par le cookie, ou `None` sans lever.

    **Seule différence avec `current_user`** : une session absente ou invalide
    rend `None` au lieu d'un 401. Nécessaire pour une route publique qui veut
    associer l'auteur connecté **si** une session existe, sans exiger d'en
    avoir une (#267, FR-001 et FR-005 de `specs/20260812-191428-bouton-
    signalement/spec.md`) — un cas que `current_user` seul ne couvre pas.
    """
    # Import différé : même raison que `current_user` ci-dessus.
    from app.api.v1.auth import session_cookie_name

    token = request.cookies.get(session_cookie_name(settings))
    return session_service.resolve(db, token)


def require_benevole_access(request: Request, db: Session = Depends(get_db)) -> None:
    """Garde de la page bénévoles (#271) — mot de passe partagé, pas de RBAC.

    **Distincte de `require_permission`** : ne compose pas `current_user`, ne
    porte aucune identité individuelle (research.md §D1 de #271 — le choix
    RGPD/CNIL qui a motivé le mot de passe partagé plutôt qu'un compte par
    bénévole). Fail-closed : configuration absente (jamais définie) ou
    cookie absent/invalide rendent tous le même 401 — la clé de vérification
    est `session_secret`, pas le mot de passe lui-même (research.md §D2 de
    `specs/20260815-173645-admin-mdp-benevoles/`).
    """
    config = benevole_config_repository.get_config(db)
    cookie = request.cookies.get(benevole_access.BENEVOLE_SESSION_COOKIE)
    if config is None or not benevole_access.verify_session(cookie, config.session_secret):
        raise NotAuthenticatedError()


def require_permission(code: Permission | str) -> Callable[..., User]:
    """Fabrique la garde d'une ressource. **Nomme un pouvoir, jamais un rôle** (FR-017).

    Elle **compose `current_user`**, et c'est ce qui rend l'ordre 401-avant-403
    structurel plutôt que défensif : une requête sans session n'atteint jamais le
    contrôle de pouvoir, il n'y a donc aucun chemin où l'ordre pourrait
    s'inverser par inadvertance.

    Se pose **route par route** (FR-018). Jamais en `dependencies=` de router ni
    d'application : `POST /admin/pending-providers` est le signalement anonyme du
    site public, et une garde de préfixe le supprimerait sans que rien ne le
    nomme.

    Passer `P.X` plutôt qu'une chaîne n'est pas du confort :
    `require_permission("pending_providres")` refuserait tout le monde, en
    silence. `tests/test_permissions_catalogue.py` tient les deux bouts par AST.
    """

    def garde(
        request: Request,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if authorization.has_permission(db, user, code):
            return user
        # FR-034 — sans cette trace, un refus n'est diagnosticable par personne :
        # le message rendu, lui, tait délibérément le pouvoir exigé. En anglais
        # (couche technique invisible), et sans jeton ni secret (FR-035).
        logger.warning(
            "Access denied: user %s lacks %s for %s %s",
            user.id,
            code,
            request.method,
            request.url.path,
        )
        raise InsufficientPermissionError()

    return garde
