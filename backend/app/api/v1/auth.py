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

from app.api.deps import current_user, settings_dep
from app.core.config import Settings
from app.core.database import get_db
from app.core.exceptions import AuthUnavailableError, NotFoundError
from app.models.user import User
from app.schemas.auth import AuthMethodRead, SessionUserRead
from app.services.auth import flow
from app.services.auth import session as session_service
from app.services.auth.errors import ERROR_CODES, LoginError
from app.services.auth.idp import registry

logger = logging.getLogger(__name__)

#: FR-018 — une réponse portant une identité ne doit jamais être servie à un
#: autre visiteur. Une seule table de valeurs, deux points d'application : la
#: dépendance de router ci-dessous pour les réponses sérialisées, et
#: `_redirection()` pour les redirections — mesuré, FastAPI **ne fusionne pas**
#: les en-têtes d'une dépendance dans une `Response` retournée directement.
ENTETES_SANS_CACHE = {"Cache-Control": "no-store", "Vary": "Cookie"}

SESSION_COOKIE = "tcn_session"
STATE_COOKIE = "tcn_auth_state"
#: Le préfixe `__Host-` **exige** `Secure` : le conserver sur un site en clair
#: ferait rejeter le cookie par le navigateur, et la connexion échouerait sans
#: message. Le nom est donc **dérivé** du réglage, jamais bricolé au cas par cas.
PREFIXE_HOTE = "__Host-"


def _sans_cache(response: Response) -> None:
    for nom, valeur in ENTETES_SANS_CACHE.items():
        response.headers[nom] = valeur


router = APIRouter(tags=["auth"], dependencies=[Depends(_sans_cache)])


def session_cookie_name(settings: Settings) -> str:
    return _nom_de_cookie(SESSION_COOKIE, settings)


def state_cookie_name(settings: Settings) -> str:
    return _nom_de_cookie(STATE_COOKIE, settings)


def _nom_de_cookie(base: str, settings: Settings) -> str:
    return f"{PREFIXE_HOTE}{base}" if settings.auth_cookie_secure else base


def _introuvable() -> NotFoundError:
    """404 portant les mêmes en-têtes que le reste du préfixe.

    Une erreur sort par le handler global de `DomainError`, hors de portée de la
    dépendance de router : sans cela, deux réponses sur sept échapperaient à
    l'invariant `no-store` / `Vary: Cookie`.
    """
    return NotFoundError(
        "Ce moyen de connexion n'existe pas.", headers=ENTETES_SANS_CACHE
    )


def _redirection(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=302, headers=ENTETES_SANS_CACHE)


def _pose_cookie(
    response: Response, *, nom: str, valeur: str, duree: int, settings: Settings
) -> None:
    """Pose un cookie du socle. **Jamais** d'attribut `Domain` : `__Host-` l'interdit,
    et c'est la non-écrasabilité depuis un sous-domaine qui ferme la fixation."""
    response.set_cookie(
        key=nom,
        value=valeur,
        max_age=duree,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",  # `strict` casserait le retour de navigation depuis le fournisseur
        path="/",
    )


def _efface_cookie(response: Response, *, nom: str, settings: Settings) -> None:
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
        key=nom,
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
    settings = settings_dep()
    if not settings.auth_is_configured:
        return []
    return [
        AuthMethodRead(slug=methode.slug, label=methode.label)
        for methode in registry.enabled_methods()
    ]


@router.get("/auth/{provider}/authorize")
def authorize(provider: str, settings: Settings = Depends(settings_dep)):
    """Ouvre le parcours. Ne prend **aucun** paramètre, destination de retour
    comprise (FR-026) : la redirection ouverte est fermée par construction."""
    try:
        url, jeton_etat = flow.start_login(provider)
    except LoginError as refus:
        if refus.code == "unknown_provider":
            raise _introuvable() from refus
        raise AuthUnavailableError(headers=ENTETES_SANS_CACHE) from refus

    reponse = _redirection(url)
    _pose_cookie(
        reponse,
        nom=state_cookie_name(settings),
        valeur=jeton_etat,
        duree=settings.auth_state_ttl_seconds,
        settings=settings,
    )
    return reponse


@router.get("/auth/{provider}/callback")
def callback(
    provider: str,
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
):
    """Retour du fournisseur. **Toujours** une redirection.

    L'ordre est contractuel (FR-025) : la validation locale précède le premier
    octet réseau. Le limiteur de threads mesuré à 40 fait d'un retour de
    parcours coûteux un levier de déni de service **sur le site public**.
    """
    if registry.get(provider) is None:
        raise _introuvable()

    jeton_etat = request.cookies.get(state_cookie_name(settings))
    try:
        jeton_session, _ = flow.complete_login(
            db,
            provider_slug=provider,
            state_token=jeton_etat,
            state_param=state,
            code=code,
            error=error,
        )
        db.commit()
    except LoginError as refus:
        db.rollback()
        reponse = _echec(refus.code, settings)
    except Exception:
        db.rollback()
        logger.exception("Unexpected failure during the %s callback", provider)
        reponse = _echec("provider_error", settings)
    else:
        reponse = _redirection(settings.auth_redirect_base_url)
        _pose_cookie(
            reponse,
            nom=session_cookie_name(settings),
            valeur=jeton_session,
            duree=settings.auth_session_ttl_days * 24 * 60 * 60,
            settings=settings,
        )

    # Effacé sur **tous** les chemins de sortie, succès compris (FR-023) : c'est
    # ce qui donne l'usage unique sans table ni verrou.
    _efface_cookie(reponse, nom=state_cookie_name(settings), settings=settings)
    return reponse


def _echec(code: str, settings: Settings) -> RedirectResponse:
    """Ramène sur la page de connexion avec un code de l'**ensemble fermé**.

    Un code hors contrat (`unknown_provider`, `not_configured`) ne franchit
    jamais la frontière : il se replie sur `provider_unavailable`, faute de quoi
    une valeur interne se retrouverait dans une URL publique.
    """
    if code not in ERROR_CODES:
        code = "provider_unavailable"
    return _redirection(f"{settings.auth_redirect_base_url}/login?error={code}")


@router.post("/auth/logout", status_code=204)
def logout(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
):
    """Ferme **cette** session. Idempotent : 204 même sans cookie (FR-014).

    `POST` et non `GET` : le cookie étant `SameSite=Lax`, un `POST` d'origine
    tierce ne le porte pas.
    """
    session_service.close(db, request.cookies.get(session_cookie_name(settings)))
    db.commit()

    reponse = Response(status_code=204, headers=ENTETES_SANS_CACHE)
    _efface_cookie(reponse, nom=session_cookie_name(settings), settings=settings)
    return reponse


@router.get("/auth/me", response_model=SessionUserRead)
def me(user: User = Depends(current_user)):
    """Identité de la session. **401** pour un anonyme, jamais « 200 vide » —
    point de contrat figé, en changer inverserait une sémantique."""
    return user
