"""Dépendances FastAPI partagées."""
import logging
import time
from collections import deque
from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.exceptions import DomainError, TooManyRequestsError
from app.core.permissions import Permission
from app.models.user import User
from app.repositories import benevole_config_repository, site_access_config_repository
from app.services import benevole_access, shared_password, site_access
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
    if config is None or not shared_password.verify_cookie(cookie, config.session_secret):
        raise NotAuthenticatedError()


def require_site_access(
    request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> None:
    """Garde transverse du site entier (#509) — mot de passe partagé, pas de
    RBAC. Distincte de `require_benevole_access` : secret et cookie propres.
    Fail-closed : configuration absente, cookie absent/invalide/expiré
    rendent tous le même 401.
    """
    config = site_access_config_repository.get_config(db, with_updated_by=False)
    cookie = request.cookies.get(site_access.SITE_SESSION_COOKIE)
    ttl_seconds = settings.site_access_session_ttl_days * 24 * 60 * 60
    if config is None or not shared_password.verify_cookie(
        cookie, config.session_secret, max_age_seconds=ttl_seconds
    ):
        raise NotAuthenticatedError()


# ── Plafond de débit par IP (#395, constats A04-2 et A07-1 de l'audit OWASP) ──
#
# Le garde SSRF de `core/http.py` ferme la **destination** d'une sortie HTTP,
# pas son **volume** ; le cache TTL de `services/cache.py` court-circuite le
# re-scraping d'une **même** épreuve, jamais le nombre d'épreuves distinctes
# demandées. Rien ne bornait donc ce qu'un appel public déclenche : jusqu'à ~26
# requêtes sortantes vers un même hôte tiers, puis plusieurs centaines de lignes
# écrites — et sur l'offre gratuite Render (un process, limiteur de threads AnyIO
# à 40, routes toutes `def`), quelques appels concurrents saturent le site.
#
# La clé est `request.client.host`, donc la première entrée de `X-Forwarded-For`
# depuis #393 (`ProxyHeadersMiddleware`, `app/main.py`) : sans ce préalable, tout
# plafond par IP se contournerait avec un en-tête forgé.
#
# Compteur **en mémoire du process**, à la différence du plafond de `/feedback`
# qui compte des lignes en base : il n'y a ici aucune table où compter, et en
# créer une ferait écrire la requête que le plafond doit justement empêcher.
#
# ponytail: compteur mono-process et fenêtre glissante en mémoire — exact tant
# que l'API tourne en un seul process (le cas sur Render). Le jour où elle scale
# horizontalement, chaque instance appliquera le plafond pour elle seule :
# passer alors à un compteur partagé (Redis). De même, le contrôle puis
# l'enregistrement ne sont pas atomiques : sous concurrence, quelques appels
# peuvent passer au-delà du plafond — sans conséquence pour un garde de volume.
_hits: dict[tuple[str, str], deque[float]] = {}

#: Au-delà, on purge les seaux dont la fenêtre est entièrement écoulée — un
#: attaquant qui fait tourner ses adresses ne fait pas croître la mémoire sans
#: fin. La purge n'efface aucun quota en cours.
_MAX_SEAUX = 10_000

#: A07-1, faible : l'ouverture de parcours ne fait qu'une signature JWS, sans
#: écriture ni réseau. Le levier est mince, le plafond est donc large — et il
#: reste une constante, pas un réglage : personne n'a de raison de l'ajuster.
AUTHORIZE_RATE_LIMIT_MAX_PER_WINDOW = 30
AUTHORIZE_RATE_LIMIT_WINDOW_SECONDS = 3600

#: A04-3, moyen : un signalement de fournisseur suit un import qui a échoué, et
#: une saisie manuelle suit ce signalement — le plafond de scraping (10/h) borne
#: donc déjà le parcours légitime. Large pour la même raison qu'ailleurs : on
#: vise l'écriture en boucle, pas le membre qui saisit sa saison.
PUBLIC_WRITE_RATE_LIMIT_MAX_PER_WINDOW = 30
PUBLIC_WRITE_RATE_LIMIT_WINDOW_SECONDS = 3600

#: #509, et **son propre seau** depuis la revue de #513 : `POST /site-access/
#: session` partageait `public_write`, ce qui couplait la porte d'entrée du site
#: à la saisie manuelle de résultats — un membre qui saisissait sa saison ne
#: pouvait plus ouvrir de session, et un club derrière une seule IP NAT/CGNAT
#: épuisait les 30 tentatives collectivement.
#:
#: Plus large que les écritures publiques, et pour la raison inverse : c'est le
#: **premier** geste de chaque visiteur, plusieurs adhérents partagent une IP,
#: et une saisie au clavier se trompe. 60/heure laisse la place à un club
#: derrière un NAT tout en gardant le plafond qui compte : `hashlib.scrypt`
#: (~16 Mo, 50-100 ms CPU) tourne à chaque tentative, avant même de savoir si
#: le mot de passe est bon — c'est le levier de déni de service que ce seau
#: ferme, la force brute n'étant pas le sujet sur un secret généré à 144 bits.
SITE_ACCESS_RATE_LIMIT_MAX_PER_WINDOW = 60
SITE_ACCESS_RATE_LIMIT_WINDOW_SECONDS = 3600


def reset_rate_limits() -> None:
    """Vide les compteurs. Réservé aux tests (fixture autouse de `conftest`)."""
    _hits.clear()


def _enforce_rate_limit(
    request: Request, bucket: str, *, max_per_window: int, window_seconds: int
) -> None:
    ip = request.client.host if request.client else None
    if ip is None:
        return

    now = time.monotonic()
    if len(_hits) > _MAX_SEAUX:
        for key, seen in list(_hits.items()):
            if not seen or now - seen[-1] >= window_seconds:
                del _hits[key]

    seen = _hits.setdefault((bucket, ip), deque())
    while seen and now - seen[0] >= window_seconds:
        seen.popleft()

    if len(seen) >= max_per_window:
        logger.warning(
            "Rate limit reached on bucket %s for %s (%s %s)",
            bucket,
            ip,
            request.method,
            request.url.path,
        )
        retry_after = int(window_seconds - (now - seen[0])) + 1
        raise TooManyRequestsError(
            "Trop de demandes envoyées récemment, réessayez plus tard.",
            headers={"Retry-After": str(retry_after)},
        )

    seen.append(now)


def scrape_rate_limit(request: Request, settings: Settings = Depends(get_settings)) -> None:
    """Plafond des deux routes d'import d'épreuve — **un seul seau pour les deux**.

    `POST /scrape/event` et `POST /scrape/event/stream` déclenchent le même
    travail : deux compteurs distincts doubleraient le plafond réel pour qui
    alterne entre les deux.
    """
    _enforce_rate_limit(
        request,
        "scrape",
        max_per_window=settings.scrape_rate_limit_max_per_window,
        window_seconds=settings.scrape_rate_limit_window_seconds,
    )


def authorize_rate_limit(request: Request) -> None:
    """Plafond de `GET /auth/{provider}/authorize` (A07-1)."""
    _enforce_rate_limit(
        request,
        "authorize",
        max_per_window=AUTHORIZE_RATE_LIMIT_MAX_PER_WINDOW,
        window_seconds=AUTHORIZE_RATE_LIMIT_WINDOW_SECONDS,
    )


def public_write_rate_limit(request: Request) -> None:
    """Plafond des deux écritures publiques non bornées (A04-3, #398).

    `POST /admin/pending-providers` et `POST /participations` écrivent en base
    sans session. Ce qui les protégeait — le `provider_hint` déduit pour l'une,
    la mise en quarantaine (`is_pending_validation`) pour l'autre — borne ce
    qu'un anonyme **publie**, jamais ce qu'il **écrit** : la base grossit quand
    même, et la fiche d'un athlète réel reste polluable. C'est ce volume-là
    qu'on borne, et lui seul : les deux routes restent ouvertes par choix
    (#267, #270), et `tests/test_auth/test_public_routes_still_open.py` les
    nomme comme telles.

    **Un seul seau pour les deux** : elles se suivent dans le même geste — un
    import qui échoue déclenche le signalement du fournisseur, puis la saisie
    manuelle qu'il propose. Deux compteurs distincts n'ajouteraient qu'un
    plafond à contourner par alternance.

    Constante plutôt que réglage : à la différence du plafond de scraping,
    aucune de ces deux routes n'appelle le réseau ni ne sature un process —
    leur coût est une ligne en base. Personne n'a de raison de l'ajuster à
    chaud.
    """
    _enforce_rate_limit(
        request,
        "public_write",
        max_per_window=PUBLIC_WRITE_RATE_LIMIT_MAX_PER_WINDOW,
        window_seconds=PUBLIC_WRITE_RATE_LIMIT_WINDOW_SECONDS,
    )


def site_access_rate_limit(request: Request) -> None:
    """Plafond de `POST /site-access/session` (#509) — **seau dédié**.

    Séparé de `public_write` en revue de #513 : voir
    `SITE_ACCESS_RATE_LIMIT_MAX_PER_WINDOW` pour ce que le partage cassait.
    Lit la constante par le module et non par sa valeur importée, pour que le
    `monkeypatch` des tests porte (patron de `public_write_rate_limit`).
    """
    _enforce_rate_limit(
        request,
        "site_access",
        max_per_window=SITE_ACCESS_RATE_LIMIT_MAX_PER_WINDOW,
        window_seconds=SITE_ACCESS_RATE_LIMIT_WINDOW_SECONDS,
    )


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
