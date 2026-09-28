"""Routers de scraping : import épreuve (sync + SSE), détection de provider."""
import logging

from fastapi import APIRouter, Depends, Request
from pydantic import HttpUrl
from sqlalchemy.orm import Session

from app.api import sse
from app.api.deps import optional_user, scrape_rate_limit
from app.core.analytics import ANONYMOUS_DISTINCT_ID, capture_event
from app.core.config import Settings, get_settings
from app.core.database import SessionLocal, get_db
from app.models.user import User
from app.schemas.scrape import ImportResult, ScrapeRequest
from app.scrapers import detect_provider, provider_names, registry
from app.services import import_service, sse_relay

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scrape"])


@router.post(
    "/scrape/event", response_model=ImportResult, dependencies=[Depends(scrape_rate_limit)]
)
def scrape_event(
    body: ScrapeRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User | None = Depends(optional_user),
):
    """Importe tous les participants d'une épreuve (bloquant)."""
    result = import_service.import_event(
        db, str(body.url), settings, single_heat=body.single_heat,
    )
    capture_event(
        "event_scraped",
        distinct_id=str(user.id) if user else ANONYMOUS_DISTINCT_ID,
        properties={
            "provider": detect_provider(str(body.url)),
            "imported": result["imported"],
            "updated": result["updated"],
            "skipped": result["skipped"],
        },
    )
    return result


@router.post("/scrape/event/stream", dependencies=[Depends(scrape_rate_limit)])
def scrape_event_stream(
    body: ScrapeRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    user: User | None = Depends(optional_user),
):
    """Import épreuve avec progression temps réel (SSE)."""
    # `optional_user` n'est pas décoratif : cette route ne le prenait pas, et un
    # import lancé depuis ici ne laissait donc **aucune trace de son appelant**
    # (#395, constat A04-2). Le pendant bloquant, lui, l'associe déjà à son
    # `capture_event`. Une ligne de journal suffit ici — le volume est borné par
    # le plafond de débit posé au-dessus.
    logger.info(
        "SSE import requested: user=%s ip=%s url=%s",
        user.id if user else "anonymous",
        request.client.host if request.client else "unknown",
        body.url,
    )

    # Le travail tourne dans son propre thread (`sse_relay`), avec sa propre
    # Session (`SessionLocal()`, cycle de vie isolé du streaming) — jamais celle
    # du générateur de la réponse. Même `ponytail:` que `_scrape_all_streaming`
    # (#566, point 1) : sur déconnexion SSE, ce générateur peut se faire clore par
    # un thread autre que celui qui possède la Session du travail ; lui faire
    # fermer une Session qu'il ne possède pas romprait ce travail pour toute
    # requête concurrente du même worker. Le thread ferme donc sa propre Session
    # dans son propre `finally`, quoi qu'il arrive côté client.
    def produce(emit) -> None:
        db = SessionLocal()
        try:
            for event in import_service.iter_import_event(
                db, str(body.url), settings, single_heat=body.single_heat,
            ):
                emit(event)
        except Exception:
            # `iter_import_event` encapsule déjà ses échecs attendus en
            # `{phase: error}` — ce filet ne couvre que l'imprévu (ex. le
            # `SELECT` non protégé de `_cached_result`). Sans lui, le thread
            # meurt en silence : le flux se referme sur un 200 bien formé mais
            # tronqué — `useImportStream` reste bloqué sur `running: true` pour
            # toujours, pire que l'ancien défaut (l'exception coupait alors
            # la connexion, remontant comme une panne réseau côté client).
            db.rollback()
            logger.exception("Échec inattendu du flux d'import SSE pour %s", body.url)
            emit({"phase": "error", "message": "Erreur lors de l'import."})
        finally:
            db.close()

    return sse.event_stream(sse_relay.relay(produce))


@router.get("/scrape/detect")
def detect(url: HttpUrl):
    """Provider détecté + support réel + portée du fan-out, dérivés du registre.

    `supported` est renvoyé pour que le front n'ait pas à tenir sa propre liste
    de providers : la sienne avait divergé et affichait « Non supporté » sur
    Competitor, RaceResult et Chronoplace.

    `fanout`/`default_single_heat` (#698) servent le choix « import unique /
    fanout complet » du front (`TcnScrapeForm`) sans qu'il tienne sa propre
    liste de providers fan-out : `fanout` vaut `isinstance(provider,
    FanoutProvider)` ; `default_single_heat` est délégué à
    `provider.targets_single_heat(url)` pour tout provider fan-out, et vaut
    `True` pour les autres (une URL mono-épreuve n'a rien à fan-outer).

    Aucune classe de provider n'est nommée ici pour ce calcul : c'est le
    polymorphisme de `targets_single_heat` qui tranche. La version précédente
    dressait la liste `(Klikego, BreizhChrono)` et retombait sur `True` pour
    tous les autres — donc pré-cochait « import unique » sur Wiclax,
    Chronoplace, OkTime, Sporthive et ChronoWeb, où ce mode rend exactement le
    même volume de participants que le fan-out en perdant la `source_url` par
    sous-unité, son cache TTL et la vraie `FanoutTrace` (revue finale #698).

    `HttpUrl` (#634) : même patron que `ScrapeRequest.url` (#49) et
    `PendingProviderCreate.url` (#398) — troisième et dernière route tracée
    par #251. Le front filtre déjà par `startsWith("http")` avant d'appeler
    cette route (`ProviderDetector.tsx`), donc sans coût pour l'appelant
    légitime.
    """
    raw = str(url)
    # Un seul balayage du registre : `provider` en main, le slug et le support
    # s'en déduisent (`detect_provider` et `is_supported` ne font rien d'autre
    # que rappeler `get_provider`, soit 3 balayages pour une requête).
    provider = registry.get_provider(raw)
    fanout = isinstance(provider, registry.FanoutProvider)
    default_single_heat = provider.targets_single_heat(raw) if fanout else True

    # BreizhChrono et RaceResult : quand l'URL fixe déjà un heat, son
    # `scrape_event_all` fait le scrape mono-heat **quel que soit**
    # `single_heat` (`if heat or single_heat:`, deux fois — chemin classique et
    # chemin live). Il n'y a donc pas de second choix à offrir : proposer la
    # bascule ferait accepter « tout l'événement » puis l'ignorerait en
    # silence. On masque le contrôle sur cette URL précise plutôt que de
    # toucher au dispatch, pré-existant et atteignable depuis la CLI (revue
    # finale #698). Klikego n'est pas concerné : son fan-out ignore réellement
    # le `?heat=` de l'URL et énumère tous les heats, sa bascule ne ment pas.
    # RaceResult, lui, restreint aussi son fan-out au `?contest=` (#989).
    if fanout and default_single_heat and isinstance(
        provider, (registry.BreizhChronoProvider, registry.RaceResultProvider)
    ):
        fanout = False

    return {
        "provider": provider.name if provider else "",
        "supported": provider is not None,
        "fanout": fanout,
        "default_single_heat": default_single_heat,
    }


@router.get("/scrape/providers")
def providers():
    """Fournisseurs ciblables, dans l'ordre de détection.

    Même registre que la validation de `--provider` côté batch : le sélecteur du
    front ne peut donc pas proposer un nom que le lancement refuserait, ni
    manquer un provider ajouté depuis.
    """
    return {"providers": provider_names()}
