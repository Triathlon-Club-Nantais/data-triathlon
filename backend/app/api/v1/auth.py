"""Router d'authentification — cinq endpoints, aucun contrat existant modifié.

Couche mince : il traduit en HTTP ce que `services/auth/flow.py` décide, et ne
porte que ce qui est réellement du ressort du protocole — les cookies, les codes
de statut et les redirections.

**Le callback répond toujours par une redirection** (FR-027) : jamais une page
de données techniques dans un navigateur en pleine navigation, ce qui était le
défaut reconnu de la PR #159.
"""
import logging

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.exceptions import AuthUnavailableError, NotFoundError
from app.models.user import User
from app.schemas.auth import (
    AuthMethodRead,
    SessionGroupRead,
    SessionRoleRead,
    SessionUserRead,
)
from app.services.auth import authorization, flow
from app.services.auth import session as session_service
from app.services.auth.errors import ERROR_CODES, LoginError
from app.services.auth.idp import registry

logger = logging.getLogger(__name__)

#: FR-018 — une réponse portant une identité ne doit jamais être servie à un
#: autre visiteur. Une seule table de valeurs, deux points d'application : la
#: dépendance de router ci-dessous pour les réponses sérialisées, et
#: `_redirect_to()` pour les redirections — mesuré, FastAPI **ne fusionne pas**
#: les en-têtes d'une dépendance dans une `Response` retournée directement.
NO_STORE_HEADERS = {"Cache-Control": "no-store", "Vary": "Cookie"}

SESSION_COOKIE = "tcn_session"
STATE_COOKIE = "tcn_auth_state"
#: Le préfixe `__Host-` **exige** `Secure` : le conserver sur un site en clair
#: ferait rejeter le cookie par le navigateur, et la connexion échouerait sans
#: message. Le nom est donc **dérivé** du réglage, jamais bricolé au cas par cas.
HOST_PREFIX = "__Host-"


def _no_store(response: Response) -> None:
    for name, value in NO_STORE_HEADERS.items():
        response.headers[name] = value


router = APIRouter(tags=["auth"], dependencies=[Depends(_no_store)])


def session_cookie_name(settings: Settings) -> str:
    return _cookie_name(SESSION_COOKIE, settings)


def state_cookie_name(settings: Settings) -> str:
    return _cookie_name(STATE_COOKIE, settings)


def _cookie_name(base: str, settings: Settings) -> str:
    return f"{HOST_PREFIX}{base}" if settings.auth_cookie_secure else base


def _not_found() -> NotFoundError:
    """404 portant les mêmes en-têtes que le reste du préfixe.

    Une erreur sort par le handler global de `DomainError`, hors de portée de la
    dépendance de router : sans cela, deux réponses sur sept échapperaient à
    l'invariant `no-store` / `Vary: Cookie`.
    """
    return NotFoundError(
        "Ce moyen de connexion n'existe pas.", headers=NO_STORE_HEADERS
    )


def _redirect_to(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=302, headers=NO_STORE_HEADERS)


def _set_auth_cookie(
    response: Response, *, name: str, value: str, max_age: int, settings: Settings
) -> None:
    """Pose un cookie du socle. **Jamais** d'attribut `Domain` : `__Host-` l'interdit,
    et c'est la non-écrasabilité depuis un sous-domaine qui ferme la fixation."""
    response.set_cookie(
        key=name,
        value=value,
        max_age=max_age,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",  # `strict` casserait le retour de navigation depuis le fournisseur
        path="/",
    )


def _clear_auth_cookie(response: Response, *, name: str, settings: Settings) -> None:
    """Efface un cookie du socle, avec **les mêmes attributs** que la pose.

    `Response.delete_cookie` de Starlette pose `secure=False` par défaut. Or la
    RFC 6265bis §4.1.3 impose au navigateur d'ignorer **entièrement** tout
    `Set-Cookie` dont le nom commence par `__Host-` si le drapeau secure-only
    est absent : en production, l'effacement était donc purement décoratif — le
    jeton d'état survivait ses 600 s (l'usage unique de FR-023 tombait) et une
    déconnexion laissait le cookie de session dans le navigateur.

    Le défaut était invisible parce que les tests d'effacement tournent sous
    `AUTH_COOKIE_SECURE=false`, où le nom ne porte pas le préfixe.
    """
    response.delete_cookie(
        key=name,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
    )


@router.get("/auth/methods", response_model=list[AuthMethodRead])
def list_methods():
    """Moyens de connexion **effectivement disponibles** (FR-031).

    Une liste vide est une réponse **valide** qui signifie « aucune connexion
    possible » — l'interface l'affiche comme telle, elle ne la traite pas en
    erreur.
    """
    settings = get_settings()
    if not settings.auth_is_configured:
        return []
    return [
        AuthMethodRead(slug=methode.slug, label=methode.label)
        for methode in registry.enabled_methods()
    ]


@router.get("/auth/{provider}/authorize")
def authorize(provider: str, settings: Settings = Depends(get_settings)):
    """Ouvre le parcours. Ne prend **aucun** paramètre, destination de retour
    comprise (FR-026) : la redirection ouverte est fermée par construction."""
    try:
        url, state_token = flow.start_login(provider)
    except LoginError as rejection:
        if rejection.code == "unknown_provider":
            raise _not_found() from rejection
        raise AuthUnavailableError(headers=NO_STORE_HEADERS) from rejection

    response = _redirect_to(url)
    _set_auth_cookie(
        response,
        name=state_cookie_name(settings),
        value=state_token,
        max_age=settings.auth_state_ttl_seconds,
        settings=settings,
    )
    return response


@router.get("/auth/{provider}/callback")
def callback(
    provider: str,
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Retour du fournisseur. **Toujours** une redirection.

    L'ordre est contractuel (FR-025) : la validation locale précède le premier
    octet réseau. Le limiteur de threads mesuré à 40 fait d'un retour de
    parcours coûteux un levier de déni de service **sur le site public**.
    """
    if registry.get(provider) is None:
        raise _not_found()

    state_token = request.cookies.get(state_cookie_name(settings))
    try:
        session_token, _ = flow.complete_login(
            db,
            provider_slug=provider,
            state_token=state_token,
            state_param=state,
            code=code,
            error=error,
        )
        db.commit()
    except LoginError as rejection:
        db.rollback()
        response = _failure_redirect(rejection.code, settings)
    except Exception:
        db.rollback()
        logger.exception("Unexpected failure during the %s callback", provider)
        response = _failure_redirect("provider_error", settings)
    else:
        # Le back-office, seul écran que la connexion ouvre aujourd'hui. La
        # destination reste **fixée par la configuration** (FR-026) : aucun
        # paramètre d'entrée n'y entre, la redirection ouverte reste fermée.
        response = _redirect_to(f"{settings.auth_redirect_base_url}/admin")
        _set_auth_cookie(
            response,
            name=session_cookie_name(settings),
            value=session_token,
            max_age=settings.auth_session_ttl_days * 24 * 60 * 60,
            settings=settings,
        )

    # Effacé sur **tous** les chemins de sortie, succès compris (FR-023) : c'est
    # ce qui donne l'usage unique sans table ni verrou.
    _clear_auth_cookie(response, name=state_cookie_name(settings), settings=settings)
    return response


def _failure_redirect(code: str, settings: Settings) -> RedirectResponse:
    """Ramène sur la page de connexion avec un code de l'**ensemble fermé**.

    Un code hors contrat (`unknown_provider`, `not_configured`) ne franchit
    jamais la frontière : il se replie sur `provider_unavailable`, faute de quoi
    une valeur interne se retrouverait dans une URL publique.
    """
    if code not in ERROR_CODES:
        code = "provider_unavailable"
    return _redirect_to(f"{settings.auth_redirect_base_url}/login?error={code}")


@router.post("/auth/logout", status_code=204)
def logout(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Ferme **cette** session. Idempotent : 204 même sans cookie (FR-014).

    `POST` et non `GET` : le cookie étant `SameSite=Lax`, un `POST` d'origine
    tierce ne le porte pas.
    """
    session_service.close(db, request.cookies.get(session_cookie_name(settings)))
    db.commit()

    response = Response(status_code=204, headers=NO_STORE_HEADERS)
    _clear_auth_cookie(response, name=session_cookie_name(settings), settings=settings)
    return response


@router.get("/auth/me", response_model=SessionUserRead)
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Identité de la session, ses pouvoirs et ses rôles.

    **401** pour un anonyme, jamais « 200 vide » — point de contrat figé, en
    changer inverserait une sémantique.

    **Aucun pouvoir n'est exigé** : la lecture ne porte que sur soi. C'est la
    contrepartie de FR-003, qui réserve l'inventaire **général** des pouvoirs à
    `roles:read`. Un connecté sans rôle obtient deux listes vides, et c'est un
    état légitime — celui de tout le monde sur une installation neuve.
    """
    return SessionUserRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        created_at=user.created_at,
        permissions=sorted(authorization.effective_permissions(db, user)),
        roles=[
            SessionRoleRead(
                id=attribution.role.id,
                slug=attribution.role.slug,
                name=attribution.role.name,
                organisation_id=attribution.organisation_id,
            )
            for attribution in user.roles
        ],
        groups=[
            SessionGroupRead(
                id=appartenance.group.id,
                slug=appartenance.group.slug,
                name=appartenance.group.name,
                organisation_id=appartenance.group.organisation_id,
            )
            for appartenance in user.groups
        ],
    )
