"""Routers de scraping : import épreuve (sync + SSE), détection de provider."""
import json

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
                yield f"data: {json.dumps(event)}\n\n"
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
