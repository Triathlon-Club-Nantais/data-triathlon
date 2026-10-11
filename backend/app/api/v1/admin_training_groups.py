"""Router des groupes d'entraînement (#1291). Chaque route porte sa garde,
`jeunes:read` pour lire, `jeunes:write` pour écrire, patron `admin_training_sessions.py`."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.user import User
from app.schemas.training_group import (
    TrainingGroupDetailRead,
    TrainingGroupMemberAdd,
    TrainingGroupRead,
    TrainingGroupWrite,
)
from app.services import training_group_service

router = APIRouter(tags=["admin"])

BASE = "/admin/training-groups"


@router.get(BASE, response_model=list[TrainingGroupRead])
def list_training_groups(
    db: Session = Depends(get_db), _: User = Depends(require_permission(P.JEUNES_READ))
):
    return training_group_service.list_group_views(db)


@router.get(BASE + "/{training_group_id}", response_model=TrainingGroupDetailRead)
def get_training_group(
    training_group_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.JEUNES_READ)),
):
    group = training_group_service.get_group_or_404(db, training_group_id)
    return training_group_service.group_detail_view(db, group)


@router.post(BASE, response_model=TrainingGroupDetailRead, status_code=201)
def create_training_group(
    body: TrainingGroupWrite,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.JEUNES_WRITE)),
):
    group = training_group_service.create_group(db, actor, name=body.name)
    view = training_group_service.group_detail_view(db, group)
    db.commit()
    return view


@router.patch(BASE + "/{training_group_id}", response_model=TrainingGroupDetailRead)
def rename_training_group(
    training_group_id: int,
    body: TrainingGroupWrite,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.JEUNES_WRITE)),
):
    group = training_group_service.get_group_or_404(db, training_group_id)
    training_group_service.rename_group(db, actor, group, name=body.name)
    view = training_group_service.group_detail_view(db, group)
    db.commit()
    return view


@router.delete(BASE + "/{training_group_id}", status_code=204)
def delete_training_group(
    training_group_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.JEUNES_WRITE)),
):
    group = training_group_service.get_group_or_404(db, training_group_id)
    training_group_service.delete_group(db, actor, group)
    db.commit()


@router.post(BASE + "/{training_group_id}/members", response_model=TrainingGroupDetailRead)
def add_training_group_member(
    training_group_id: int,
    body: TrainingGroupMemberAdd,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.JEUNES_WRITE)),
):
    group = training_group_service.get_group_or_404(db, training_group_id)
    training_group_service.add_member(db, actor, group, profile_id=body.profile_id)
    view = training_group_service.group_detail_view(db, group)
    db.commit()
    return view


@router.delete(BASE + "/{training_group_id}/members/{profile_id}", response_model=TrainingGroupDetailRead)
def remove_training_group_member(
    training_group_id: int,
    profile_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.JEUNES_WRITE)),
):
    group = training_group_service.get_group_or_404(db, training_group_id)
    training_group_service.remove_member(db, actor, group, profile_id=profile_id)
    view = training_group_service.group_detail_view(db, group)
    db.commit()
    return view
