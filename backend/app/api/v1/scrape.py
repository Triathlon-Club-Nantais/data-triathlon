"""Routers de scraping : import épreuve (sync + SSE), détection de provider."""
import json
import logging
from dataclasses import asdict, is_dataclass

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import HttpUrl
from sqlalchemy.orm import Session

from app.api.deps import optional_user, scrape_rate_limit
from app.core.analytics import ANONYMOUS_DISTINCT_ID, capture_event
from app.core.config import Settings, get_settings
from app.core.database import SessionLocal, get_db
from app.models.user import User
from app.schemas.scrape import ImportResult, ScrapeRequest
from app.scrapers import detect_provider, is_supported, provider_names
from app.services import import_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scrape"])


def _json_default(value: object) -> object:
    """Filet de sérialisation JSON pour les phases du SSE.

    `iter_import_event` peut émettre des dataclasses (ex. `Reassignment`,
    frozen, non sérialisable nativement) dans le champ `reassignments` de la
    phase `done`. `batch` consomme le même générateur et a besoin des objets
    Python — la conversion se fait donc ici, au point de sérialisation SSE,
    jamais dans le générateur.
    """
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return str(value)


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
    result = import_service.import_event(db, str(body.url), settings)
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


# Padding initial de 2 KB : dépasse le seuil de buffering des navigateurs
# (Chrome / Firefox retiennent ~1-2 KB avant de laisser `Response.body.getReader()`
# rendre le premier chunk). Sans lui, un import Klikego fan-out (35 s de scraping)
# reste figé sur « Récupération des participants… » côté UI alors que le backend
# émet 8 events. Ligne SSE commençant par `:` = commentaire, ignoré par le parseur
# de `useImportStream`. Pas un no-op côté proto : le socket reçoit ces octets
# immédiatement, ce qui casse le tampon. `X-Accel-Buffering: no` ne suffit pas
# (c'est un hint pour nginx, pas pour le navigateur).
_SSE_INITIAL_PADDING = b":" + b" " * 2048 + b"\n\n"


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

    def generate():
        # Session dédiée au générateur (cycle de vie isolé du streaming)
        db = SessionLocal()
        try:
            yield _SSE_INITIAL_PADDING
            for event in import_service.iter_import_event(db, str(body.url), settings):
                yield f"data: {json.dumps(event, default=_json_default)}\n\n"
        finally:
            db.close()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            # `Content-Encoding: identity` bloque la compression par tout
            # intermédiaire HTTP — le proxy Turbopack de Next.js dev l'a
            # rendue visible (avec `Accept-Encoding: gzip` d'un navigateur, il
            # bufferisait le stream dans son compresseur jusqu'à ~500 octets,
            # la barre par heat #156 apparaissait 4-5 s en retard), mais la
            # même compression peut réapparaître en prod (edge Vercel, CDN,
            # reverse-proxy) — d'où la garde côté application, pas côté env.
            # Coût mesuré : ~5 KB de plus par import (SSE non compressé),
            # négligeable devant le gain de latence perçue. `no-transform` du
            # Cache-Control est le second garde de RFC 7234.
            "Content-Encoding": "identity",
        },
    )


@router.get("/scrape/detect")
def detect(url: HttpUrl):
    """Provider détecté + support réel, tous deux dérivés du registre.

    `supported` est renvoyé pour que le front n'ait pas à tenir sa propre liste
    de providers : la sienne avait divergé et affichait « Non supporté » sur
    Competitor, RaceResult et Chronoplace.

    `HttpUrl` (#634) : même patron que `ScrapeRequest.url` (#49) et
    `PendingProviderCreate.url` (#398) — troisième et dernière route tracée
    par #251. Le front filtre déjà par `startsWith("http")` avant d'appeler
    cette route (`ProviderDetector.tsx`), donc sans coût pour l'appelant
    légitime.
    """
    raw = str(url)
    return {"provider": detect_provider(raw), "supported": is_supported(raw)}


@router.get("/scrape/providers")
def providers():
    """Fournisseurs ciblables, dans l'ordre de détection.

    Même registre que la validation de `--provider` côté batch : le sélecteur du
    front ne peut donc pas proposer un nom que le lancement refuserait, ni
    manquer un provider ajouté depuis.
    """
    return {"providers": provider_names()}
