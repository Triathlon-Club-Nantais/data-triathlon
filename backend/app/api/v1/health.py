"""Endpoints d'infra : santé de l'API/base, et version du backend."""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.version import app_version

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


@router.get("/version")
def version() -> dict:
    """Version du backend en cours d'exécution (#134).

    Utilisé par le front pour afficher un footer et détecter les mismatches
    front/back (rollback partiel, redéploiement dissocié). Volontairement
    non authentifié : la donnée n'est pas sensible et un utilisateur qui
    remonte un bug doit pouvoir la voir sans être connecté.
    """
    return {"version": app_version()}
