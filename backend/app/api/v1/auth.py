"""Router d'authentification — cinq endpoints, aucun contrat existant modifié.

Couche mince : il traduit en HTTP ce que `services/auth/flow.py` décide, et ne
porte que ce qui est réellement du ressort du protocole — les cookies, les codes
de statut et les redirections.

**Le callback répond toujours par une redirection** (FR-027) : jamais une page
de données techniques dans un navigateur en pleine navigation, ce qui était le
défaut reconnu de la PR #159.
"""
import logging
from collections.abc import Iterable

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import authorize_rate_limit, current_user, require_site_access
from app.core import permissions
from app.core.analytics import capture_event, set_person_properties
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.exceptions import AuthUnavailableError, NotFoundError
from app.core.season import SEASON_MAX, SEASON_MIN, current_season, parse_seasons
from app.core.time import utcnow
from app.models.result_claim import ResultClaim
from app.models.user import User
from app.repositories import user_repository
from app.schemas.athlete_claim import (
    AthleteClaimCreate,
    AthleteClaimRead,
    ClaimedAthleteRead,
    ResultClaimCreate,
    ResultClaimRead,
)
from app.schemas.auth import (
    AccountIdentityRead,
    AuthMethodRead,
    SessionGroupRead,
    SessionRoleRead,
    SessionUserRead,
)
from app.schemas.ids import DbId
from app.schemas.season_goal import SeasonGoalRead, SeasonGoalWrite
from app.schemas.teammate import Teammate
from app.schemas.volunteer_action import MyVolunteerActionOut
from app.services import (
    athlete_claims,
    membership,
    result_claims,
    season_goals,
    teammate_service,
    volunteer_access,
    volunteer_action_service,
)
from app.services.auth import accounts, authorization, flow
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

#: Signal de présence, lisible en JS (#427) : sans lui, `useSession` n'a aucun
#: moyen de savoir qu'un visiteur est anonyme avant d'appeler `/auth/me`, qui
#: répond alors 401 — bruit systématique dans la console du navigateur. Ne
#: porte aucun secret, donc pas de `HttpOnly` ; et n'a pas besoin du préfixe
#: `__Host-` réservé aux deux cookies ci-dessus, son nom reste fixe d'un
#: environnement à l'autre.
LOGGED_IN_COOKIE = "tcn_logged_in"


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


def _landing_path(codes: Iterable[str]) -> str:
    """Le premier espace ouvert : back-office, sinon encadrement, sinon accueil."""
    if permissions.administers(codes):
        return "/admin"
    if permissions.supervises(codes):
        return "/encadrement"
    return "/"


def _redirect_to(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=302, headers=NO_STORE_HEADERS)


def _set_auth_cookie(
    response: Response,
    *,
    name: str,
    value: str,
    max_age: int,
    settings: Settings,
    httponly: bool = True,
) -> None:
    """Pose un cookie du socle. **Jamais** d'attribut `Domain` : `__Host-` l'interdit,
    et c'est la non-écrasabilité depuis un sous-domaine qui ferme la fixation."""
    response.set_cookie(
        key=name,
        value=value,
        max_age=max_age,
        httponly=httponly,
        secure=settings.auth_cookie_secure,
        samesite="lax",  # `strict` casserait le retour de navigation depuis le fournisseur
        path="/",
    )


def _clear_auth_cookie(
    response: Response, *, name: str, settings: Settings, httponly: bool = True
) -> None:
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
        httponly=httponly,
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
        AuthMethodRead(slug=method.slug, label=method.label)
        for method in registry.enabled_methods()
    ]


@router.get("/auth/{provider}/authorize", dependencies=[Depends(authorize_rate_limit)])
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
        session_token, user = flow.complete_login(
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
        # Capturer avant la redirection, avec l'utilisateur déjà en main.
        # `User` ne porte aucun rôle global (FR-041) : `is_superuser` est la
        # décision réelle du projet, pas un champ inventé sur `User`.
        set_person_properties(str(user.id), {"is_staff": authorization.is_superuser(db, user)})
        capture_event(
            "user_logged_in", distinct_id=str(user.id), properties={"provider": provider}
        )
        # La destination reste **fixée par le code** (FR-026) : aucun paramètre
        # d'entrée n'y entre, la redirection ouverte reste fermée. Un compte sans
        # rôle (adhérent, #1322) arrive sur l'accueil.
        effective = authorization.effective_permissions(db, user)
        response = _redirect_to(f"{settings.auth_redirect_base_url}{_landing_path(effective)}")
        session_max_age = settings.auth_session_ttl_days * 24 * 60 * 60
        _set_auth_cookie(
            response,
            name=session_cookie_name(settings),
            value=session_token,
            max_age=session_max_age,
            settings=settings,
        )
        _set_auth_cookie(
            response,
            name=LOGGED_IN_COOKIE,
            value="1",
            max_age=session_max_age,
            settings=settings,
            httponly=False,
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

    `POST` et non `GET` : le cookie étant `SameSite=Lax`, un `POST` **cross-site**
    ne le porte pas. Un `POST` same-site (l'apex, un autre sous-domaine) le porte,
    lui : c'est `core/origin_guard` qui le refuse (#946).
    """
    token = request.cookies.get(session_cookie_name(settings))
    # Résoudre l'utilisateur avant de fermer la session pour pouvoir le capturer.
    logging_out_user = session_service.resolve(db, token)
    session_service.close(db, token)
    db.commit()

    if logging_out_user is not None:
        capture_event("user_logged_out", distinct_id=str(logging_out_user.id))

    return _signed_out_response(settings)


def _signed_out_response(settings: Settings) -> Response:
    response = Response(status_code=204, headers=NO_STORE_HEADERS)
    _clear_auth_cookie(response, name=session_cookie_name(settings), settings=settings)
    _clear_auth_cookie(
        response, name=LOGGED_IN_COOKIE, settings=settings, httponly=False
    )
    # #1272 : admis par son pouvoir, l'admin ne voit plus « Se déconnecter » de
    # `/benevoles`. Un cookie bénévoles resté sur ce navigateur ne doit pas
    # survivre à sa déconnexion. Mêmes attributs qu'à la pose.
    _clear_auth_cookie(response, name=volunteer_access.VOLUNTEER_SESSION_COOKIE, settings=settings)
    return response


@router.delete("/auth/me", status_code=204)
def delete_me(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Supprime le compte de la session, puis déconnecte ce navigateur (#1326).

    Protégée comme `logout` : `SameSite=Lax` écarte le cross-site, `core/origin_guard`
    le same-site. Les refus (référence obligatoire, dernier administrateur) sortent
    en 409 par le handler de `DomainError`, sans rien supprimer.
    """
    user_id = user.id
    accounts.delete_account(db, user, origin="request")
    db.commit()
    capture_event("user_account_deleted", distinct_id=str(user_id))
    return _signed_out_response(settings)


@router.post(
    "/auth/me/athlete-claim",
    response_model=AthleteClaimRead,
    status_code=201,
    # Le routeur `auth` est exempté de la garde du site, mais la réponse nomme la
    # fiche : sans elle, un compte quelconque énumérerait les athlètes (revue de #1624).
    dependencies=[Depends(require_site_access)],
)
def request_athlete_claim(
    body: AthleteClaimCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Demande le rattachement de sa fiche (#1325), toujours soumis à la file du club."""
    claim = athlete_claims.request_claim(db, user, body.athlete_id)
    db.commit()
    return AthleteClaimRead.model_validate(claim)


@router.delete("/auth/me/athlete-claim", status_code=204)
def cancel_athlete_claim(user: User = Depends(current_user), db: Session = Depends(get_db)):
    athlete_claims.cancel_claim(db, user)
    db.commit()
    return Response(status_code=204, headers=NO_STORE_HEADERS)


def _result_claim_read(claim: ResultClaim) -> ResultClaimRead:
    course = claim.participation.course
    return ResultClaimRead(
        id=claim.id, participation_id=claim.participation_id, status=claim.status, created_at=claim.created_at,
        course_id=course.id, course_name=course.name,
        event_date=course.event_date.isoformat() if course.event_date else None,
    )


@router.get("/auth/me/result-claims", response_model=list[ResultClaimRead])
def list_my_result_claims(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Mes réclamations de résultat (#1637), en attente ou refusées."""
    return [_result_claim_read(claim) for claim in result_claims.list_mine(db, user)]


@router.post(
    "/auth/me/result-claims",
    response_model=ResultClaimRead,
    status_code=201,
    # Même raison que la demande de fiche : le routeur `auth` échappe à la garde du site.
    dependencies=[Depends(require_site_access)],
)
def request_result_claim(body: ResultClaimCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """« Ce résultat est à moi » (#1637), toujours soumis à la file du club."""
    claim = result_claims.request_claim(db, user, body.participation_id)
    db.commit()
    return _result_claim_read(claim)


@router.delete("/auth/me/result-claims/{claim_id}", status_code=204)
def cancel_result_claim(claim_id: DbId, user: User = Depends(current_user), db: Session = Depends(get_db)):
    result_claims.cancel_claim(db, user, claim_id)
    db.commit()
    return Response(status_code=204, headers=NO_STORE_HEADERS)


@router.delete("/auth/me/athlete", status_code=204)
def detach_athlete(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Se détache de sa fiche ; la fiche et ses résultats restent (#1325)."""
    athlete_claims.detach(db, user)
    db.commit()
    return Response(status_code=204, headers=NO_STORE_HEADERS)


def _goal_read(progress: season_goals.GoalProgress) -> SeasonGoalRead:
    goal = progress.goal
    return SeasonGoalRead(
        id=goal.id, season=goal.season, kind=goal.kind, event_type=goal.event_type, target=goal.target,
        best_time=progress.best_time, count=progress.count, reached=progress.reached,
    )


def _progress_of(db: Session, user: User, goal) -> SeasonGoalRead:
    (progress,) = [p for p in season_goals.list_with_progress(db, user, goal.season) if p.goal.id == goal.id]
    return _goal_read(progress)


@router.get("/auth/me/goals", response_model=list[SeasonGoalRead])
def list_goals(
    season: int | None = Query(None, ge=SEASON_MIN, le=SEASON_MAX),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Objectifs de saison du compte et leur progression (#1373), privés."""
    return [_goal_read(p) for p in season_goals.list_with_progress(db, user, season or current_season())]


@router.post("/auth/me/goals", response_model=SeasonGoalRead, status_code=201)
def create_goal(body: SeasonGoalWrite, user: User = Depends(current_user), db: Session = Depends(get_db)):
    goal = season_goals.create(
        db, user, season=current_season(), kind=body.kind, event_type=body.event_type, target=body.target
    )
    db.commit()
    return _progress_of(db, user, goal)


@router.put("/auth/me/goals/{goal_id}", response_model=SeasonGoalRead)
def update_goal(
    goal_id: DbId, body: SeasonGoalWrite, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    goal = season_goals.update(db, user, goal_id, kind=body.kind, event_type=body.event_type, target=body.target)
    db.commit()
    return _progress_of(db, user, goal)


@router.delete("/auth/me/goals/{goal_id}", status_code=204)
def delete_goal(goal_id: DbId, user: User = Depends(current_user), db: Session = Depends(get_db)):
    season_goals.delete(db, user, goal_id)
    db.commit()
    return Response(status_code=204, headers=NO_STORE_HEADERS)


@router.get("/auth/me/volunteer-actions", response_model=list[MyVolunteerActionOut])
def list_my_volunteer_actions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Mes actions de bénévolat validées (#1696) ; liste vide sans fiche rattachée."""
    if user.athlete_id is None:
        return []
    return volunteer_action_service.list_validated_for_athlete(db, athlete_id=user.athlete_id)


@router.get("/auth/me/teammates", response_model=list[Teammate])
def list_my_teammates(
    federal_only: bool = Query(False),
    seasons: str | None = Query(None, description="Saisons (années de début, CSV) ; absentes, toutes saisons."),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Mes trois coéquipiers de course les plus fréquents (#1701) ; liste vide sans fiche rattachée."""
    if user.athlete_id is None:
        return []
    return teammate_service.list_for_athlete(
        db, athlete_id=user.athlete_id, federal_only=federal_only, seasons=parse_seasons(seasons)
    )


@router.get("/auth/me/identities", response_model=list[AccountIdentityRead])
def list_my_identities(user: User = Depends(current_user)):
    """Les moyens de connexion du compte de la session (#1663), du plus ancien au plus récent."""
    return [
        AccountIdentityRead(
            provider=identity.provider,
            label=provider.label if (provider := registry.get(identity.provider)) else identity.provider,
            email=identity.email,
            created_at=identity.created_at,
        )
        for identity in sorted(user.identities, key=lambda identity: identity.created_at)
    ]


@router.get("/auth/me", response_model=SessionUserRead)
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Identité de la session, ses pouvoirs et ses rôles.

    **401** pour un anonyme, jamais « 200 vide » — point de contrat figé, en
    changer inverserait une sémantique.

    **Aucun pouvoir n'est exigé** : la lecture ne porte que sur soi. C'est la
    contrepartie de FR-003, qui réserve l'inventaire **général** des pouvoirs à
    `roles:read`. Un connecté sans rôle obtient deux listes vides, et c'est un
    état légitime — celui de tout le monde sur une installation neuve.

    `user` est rechargé avec `roles`/`groups` déjà joints (#625) : sans ce
    chargement anticipé, `user.roles`, `user.groups` et leurs `.role`/`.group`
    sont autant de requêtes séparées, en plus de celle que
    `effective_permissions` fait déjà pour les mêmes attributions — jusqu'à
    huit ou dix aller-retours DB pour un GET censé être trivial.
    """
    loaded_user = user_repository.get_with_roles_and_groups(db, user.id) or user
    effective = authorization.effective_permissions(db, loaded_user, attributions=loaded_user.roles)
    athlete, claim = athlete_claims.session_view(db, loaded_user)
    return SessionUserRead(
        athlete=ClaimedAthleteRead.model_validate(athlete) if athlete else None,
        athlete_claim=AthleteClaimRead.model_validate(claim) if claim else None,
        id=loaded_user.id,
        email=loaded_user.email,
        display_name=loaded_user.display_name,
        created_at=loaded_user.created_at,
        permissions=sorted(effective),
        can_administer=permissions.administers(effective),
        can_supervise=permissions.supervises(effective),
        is_member=membership.is_member(db, loaded_user, utcnow().date()),
        roles=[
            SessionRoleRead(
                id=attribution.role.id,
                slug=attribution.role.slug,
                name=attribution.role.name,
                organisation_id=attribution.organisation_id,
            )
            for attribution in loaded_user.roles
        ],
        groups=[
            SessionGroupRead(
                id=membership.group.id,
                slug=membership.group.slug,
                name=membership.group.name,
                organisation_id=membership.group.organisation_id,
            )
            for membership in loaded_user.groups
        ],
    )
