"""Droit d'opposition d'un athlète (#334) : trois ressources, chacune gardée par `oppositions:manage`."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.user import User
from app.schemas.opposition import (
    OppositionCreate,
    OppositionIdentity,
    OppositionPreviewRead,
    OppositionRead,
)
from app.services import opposition_service

router = APIRouter(tags=["admin"])


@router.get("/admin/oppositions", response_model=list[OppositionRead])
def list_oppositions(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.OPPOSITIONS_MANAGE)),
):
    return opposition_service.list_oppositions(db)


@router.post("/admin/oppositions/preview", response_model=OppositionPreviewRead)
def preview_opposition(
    body: OppositionIdentity,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.OPPOSITIONS_MANAGE)),
):
    return opposition_service.preview(db, athlete_id=body.athlete_id, nom=body.nom, prenom=body.prenom)


@router.post("/admin/oppositions", response_model=OppositionRead, status_code=201)
def apply_opposition(
    body: OppositionCreate,
    response: Response,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.OPPOSITIONS_MANAGE)),
):
    opposition, created = opposition_service.apply(
        db, actor, athlete_id=body.athlete_id, nom=body.nom, prenom=body.prenom, requested_on=body.requested_on
    )
    if not created:
        response.status_code = 200
    return opposition_service.opposition_view(opposition)
