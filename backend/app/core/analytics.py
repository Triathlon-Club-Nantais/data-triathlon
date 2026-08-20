"""PostHog analytics client — initialisation unique, instance partagée.

Usage dans les routes :
    from app.core.analytics import posthog_client, capture_event

    # Capture simple (utilisateur authentifié)
    capture_event("batch_launched", distinct_id=str(user.id), properties={"mode": mode})

    # Capture anonyme (visiteur non connecté)
    capture_event("feedback_submitted", distinct_id="anonymous", properties={...})

L'instance ``posthog_client`` peut être ``None`` si la clé n'est pas configurée.
Toutes les fonctions ci-dessous vérifient cette condition avant d'agir.
"""
import atexit
import logging

from posthog import Posthog

logger = logging.getLogger(__name__)

#: Instance partagée — ``None`` jusqu'à l'appel de ``init_posthog()``.
posthog_client: Posthog | None = None

#: `distinct_id` des événements émis sans utilisateur authentifié. Volontairement
#: partagé entre tous les visiteurs anonymes : ces événements n'ont pas de
#: granularité par personne à préserver (feedback anonyme, scrape système), et
#: PostHog fusionnerait de toute façon toute paire d'ids anonymes qui s'identifie
#: plus tard sur le même utilisateur. Un seul littéral évite qu'un futur site
#: d'appel en invente un second et fragmente les métriques agrégées.
ANONYMOUS_DISTINCT_ID = "anonymous"


def init_posthog(token: str, host: str, debug: bool = False) -> None:
    """Initialise le client PostHog. Appelé dans le lifespan FastAPI.

    Un token vide signifie « pas de PostHog » : la fonction retourne sans
    rien faire. En mode debug (développement), un avertissement nomme ce
    qui manque plutôt que de rater les captures en silence.
    """
    global posthog_client

    if not token:
        if debug:
            logger.warning(
                "PostHog is disabled: POSTHOG_PROJECT_TOKEN is not set, events will "
                "be silently dropped. This warning stops once the variable is set."
            )
        return

    # Décision explicite : l'autocapture des exceptions est activée — c'est le
    # produit « Error Tracking » de PostHog, la raison d'être de cette variable.
    # Elle expose la trace complète (message, args) de toute exception non
    # gérée par `register_exception_handlers` (seul `DomainError` l'est) au
    # cloud EU. Les `DomainError` connus embarquant des données identifiantes
    # (ex. nom d'athlète dans `admin_data.py`) sont eux capturés proprement et
    # n'atteignent jamais l'autocapture ; le risque résiduel est un bug non
    # prévu qui logue accidentellement une donnée similaire dans son message.
    # `project_api_key` et non `api_key` : le SDK nomme ainsi le **paramètre**
    # du constructeur, alors qu'il expose la valeur sous l'attribut `api_key` —
    # asymétrie qui a coûté un démarrage en production (`TypeError` dans le
    # lifespan, application startup failed). Un test tient désormais ce nom.
    posthog_client = Posthog(
        project_api_key=token,
        host=host,
        enable_exception_autocapture=True,
        debug=debug,
    )
    atexit.register(posthog_client.shutdown)
    logger.info("PostHog analytics initialised (host: %s)", host)


def shutdown_posthog() -> None:
    """Vide la file d'attente au shutdown du serveur."""
    if posthog_client is not None:
        posthog_client.shutdown()


def capture_event(
    event: str,
    *,
    distinct_id: str,
    properties: dict | None = None,
) -> None:
    """Capture un événement si le client est initialisé.

    Ne lève jamais : un échec PostHog ne doit pas casser la réponse HTTP.
    """
    if posthog_client is None:
        return
    try:
        posthog_client.capture(
            distinct_id=distinct_id,
            event=event,
            properties=properties or {},
        )
    except Exception:
        logger.exception("PostHog capture failed for event %r", event)


def set_person_properties(distinct_id: str, properties: dict) -> None:
    """Envoie des propriétés de personne (sans PII dans les événements).

    Utiliser pour associer des métadonnées non-PII à un utilisateur.
    """
    if posthog_client is None:
        return
    try:
        posthog_client.set(distinct_id=distinct_id, properties=properties)
    except Exception:
        logger.exception("PostHog set failed for distinct_id %r", distinct_id)
