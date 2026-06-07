"""Endpoint de santé — vérifie l'API et la connexion à la base."""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    """Renvoie l'état de l'API et de la base de données."""
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - dépend de l'infra
        logger.warning("Health check DB échoué : %s", exc)
        db_ok = False

    return {"status": "ok" if db_ok else "degraded", "database": db_ok}
