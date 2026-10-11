"""Router des séances récurrentes (#1291). Chaque route porte sa garde ;
l'aperçu est une écriture au sens des pouvoirs : il ne sert qu'à créer."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.user import User
from app.schemas.training_recurrence import (
    TrainingRecurrenceCreate,
    TrainingRecurrenceCreated,
    TrainingRecurrenceDeleted,
    TrainingRecurrencePreview,
    TrainingRecurrenceRead,
    TrainingRecurrenceUpdate,
)
from app.services import training_recurrence_service

router = APIRouter(tags=["admin"])

BASE = "/admin/training-recurrences"


@router.get(BASE, response_model=list[TrainingRecurrenceRead])
def list_training_recurrences(
    db: Session = Depends(get_db), _: User = Depends(require_permission(P.JEUNES_READ))
):
    return training_recurrence_service.list_recurrence_views(db)


@router.post(BASE + "/preview", response_model=TrainingRecurrencePreview)
def preview_training_recurrence(
    body: TrainingRecurrenceCreate, _: User = Depends(require_permission(P.JEUNES_WRITE))
):
    dates = training_recurrence_service.occurrence_dates(body.weekday, body.starts_on, body.ends_on)
    return {"occurrence_count": len(dates), "dates": dates}


@router.post(BASE, response_model=TrainingRecurrenceCreated, status_code=201)
def create_training_recurrence(
    body: TrainingRecurrenceCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.JEUNES_WRITE)),
):
    recurrence, created = training_recurrence_service.create_recurrence(db, actor, **body.model_dump())
    view = training_recurrence_service.recurrence_view(db, recurrence) | {"created_session_count": created}
    db.commit()
    return view


@router.patch(BASE + "/{recurrence_id}", response_model=TrainingRecurrenceRead)
def update_training_recurrence(
    recurrence_id: int,
    body: TrainingRecurrenceUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.JEUNES_WRITE)),
):
    recurrence = training_recurrence_service.get_recurrence_or_404(db, recurrence_id)
    fields = body.model_dump(exclude_unset=True)
    # Ces trois champs sont non nuls en base : un `null` explicite vaut « absent ».
    for name in ("weekday", "starts_on", "ends_on"):
        if fields.get(name, ...) is None:
            del fields[name]
    training_recurrence_service.update_recurrence(db, actor, recurrence, **fields)
    view = training_recurrence_service.recurrence_view(db, recurrence)
    db.commit()
    return view


@router.delete(BASE + "/{recurrence_id}", response_model=TrainingRecurrenceDeleted)
def delete_training_recurrence(
    recurrence_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.JEUNES_WRITE)),
):
    recurrence = training_recurrence_service.get_recurrence_or_404(db, recurrence_id)
    outcome = training_recurrence_service.delete_recurrence(db, actor, recurrence)
    db.commit()
    return outcome
