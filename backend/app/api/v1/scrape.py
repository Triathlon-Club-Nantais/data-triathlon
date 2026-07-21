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
from app.scrapers import detect_provider
from app.services import import_service

router = APIRouter(tags=["scrape"])


def _json_default(o):
    """Filet de sérialisation JSON pour les phases du SSE.

    `iter_import_event` peut émettre des dataclasses (ex. `Reassignment`,
    frozen, non sérialisable nativement) dans le champ `reassignments` de la
    phase `done`. `batch` consomme le même générateur et a besoin des objets
    Python — la conversion se fait donc ici, au point de sérialisation SSE,
    jamais dans le générateur.
    """
    if is_dataclass(o) and not isinstance(o, type):
        return asdict(o)
    return str(o)


@router.post("/scrape/event", response_model=ImportResult)
def scrape_event(
    body: ScrapeRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
):
    """Importe tous les participants d'une épreuve (bloquant)."""
    return import_service.import_event(db, body.url, settings)


@router.post("/scrape/event/stream")
def scrape_event_stream(body: ScrapeRequest, settings: Settings = Depends(settings_dep)):
    """Import épreuve avec progression temps réel (SSE)."""

    def generate():
        # Session dédiée au générateur (cycle de vie isolé du streaming)
        db = SessionLocal()
        try:
            for event in import_service.iter_import_event(db, body.url, settings):
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
    return {"provider": detect_provider(url)}
