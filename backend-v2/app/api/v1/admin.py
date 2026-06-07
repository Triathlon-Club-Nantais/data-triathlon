"""Router Admin : signalement des providers non supportés."""
from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories import pending_provider_repository

router = APIRouter(tags=["admin"])


class PendingProviderCreate(BaseModel):
    url: str


@router.post("/admin/pending-providers", status_code=201)
def report_pending_provider(body: PendingProviderCreate, db: Session = Depends(get_db)):
    try:
        hint = urlparse(body.url).netloc
    except Exception:
        hint = ""
    entry = pending_provider_repository.create(db, url=body.url, provider_hint=hint)
    db.commit()
    db.refresh(entry)
    return {"id": entry.id, "url": entry.url, "provider_hint": entry.provider_hint}


@router.get("/admin/pending-providers")
def list_pending_providers(db: Session = Depends(get_db)):
    rows = pending_provider_repository.list_unhandled(db)
    return [
        {
            "id": r.id,
            "url": r.url,
            "provider_hint": r.provider_hint,
            "reported_at": r.reported_at.isoformat() if r.reported_at else None,
        }
        for r in rows
    ]


@router.delete("/admin/pending-providers/{entry_id}", status_code=204)
def mark_handled(entry_id: int, db: Session = Depends(get_db)):
    pending_provider_repository.mark_handled(db, entry_id)
    db.commit()
