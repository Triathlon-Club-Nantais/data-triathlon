"""Routers de scraping : import épreuve (sync + SSE), détection de provider."""
import json
from dataclasses import asdict, is_dataclass

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import settings_dep
from app.core.config import Settings
from app.core.database import SessionLocal, get_db
from app.schemas.scrape import ImportResult, ScrapeRequest
from app.scrapers import detect_provider, is_supported
from app.services import import_service

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


@router.post("/scrape/event", response_model=ImportResult)
def scrape_event(
    body: ScrapeRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
):
    """Importe tous les participants d'une épreuve (bloquant)."""
    return import_service.import_event(db, str(body.url), settings)


# Padding initial de 2 KB : dépasse le seuil de buffering des navigateurs
# (Chrome / Firefox retiennent ~1-2 KB avant de laisser `Response.body.getReader()`
# rendre le premier chunk). Sans lui, un import Klikego fan-out (35 s de scraping)
# reste figé sur « Récupération des participants… » côté UI alors que le backend
# émet 8 events. Ligne SSE commençant par `:` = commentaire, ignoré par le parseur
# de `useImportStream`. Pas un no-op côté proto : le socket reçoit ces octets
# immédiatement, ce qui casse le tampon. `X-Accel-Buffering: no` ne suffit pas
# (c'est un hint pour nginx, pas pour le navigateur).
_SSE_INITIAL_PADDING = b":" + b" " * 2048 + b"\n\n"


@router.post("/scrape/event/stream")
def scrape_event_stream(body: ScrapeRequest, settings: Settings = Depends(settings_dep)):
    """Import épreuve avec progression temps réel (SSE)."""

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
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/scrape/detect")
def detect(url: str):
    """Provider détecté + support réel, tous deux dérivés du registre.

    `supported` est renvoyé pour que le front n'ait pas à tenir sa propre liste
    de providers : la sienne avait divergé et affichait « Non supporté » sur
    Competitor, RaceResult et Chronoplace.
    """
    return {"provider": detect_provider(url), "supported": is_supported(url)}
