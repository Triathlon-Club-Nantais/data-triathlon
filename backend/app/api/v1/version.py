"""Endpoint public de version — le front en tire son mini-footer (#134)."""
from fastapi import APIRouter

from app.version import app_version

router = APIRouter(tags=["version"])


@router.get("/version")
def version() -> dict:
    """Version du backend en cours d'exécution.

    Utilisé par le front pour afficher un footer et détecter les mismatches
    front/back (rollback partiel, redéploiement dissocié). Volontairement
    non authentifié : la donnée n'est pas sensible et un utilisateur qui
    remonte un bug doit pouvoir la voir sans être connecté.
    """
    return {"version": app_version()}
