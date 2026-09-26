"""Endpoints d'infra : santé de l'API/base, et version du backend."""
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.version import app_version

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    """Renvoie l'état de l'API et de la base de données.

    Base injoignable → 503, pas 200 : le keep-warm et toute supervision ne
    lisent que le statut HTTP, et sans base aucune page de lecture ne répond
    (#1070).
    """
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("Health check DB échoué : %s", exc)
        return JSONResponse(status_code=503, content={"status": "degraded", "database": False})

    return {"status": "ok", "database": True}


@router.get("/version")
def version() -> dict:
    """Version du backend en cours d'exécution (#134).

    Utilisé par le front pour afficher un footer et détecter les mismatches
    front/back (rollback partiel, redéploiement dissocié). Volontairement
    non authentifié : la donnée n'est pas sensible et un utilisateur qui
    remonte un bug doit pouvoir la voir sans être connecté.
    """
    return {"version": app_version()}
