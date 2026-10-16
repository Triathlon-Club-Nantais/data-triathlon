"""Router admin du workflow de validation des actions de bénévolat pour le
quota de saison (#779) — file d'attente, accepter, refuser. La création
n'a plus qu'un chemin, le self-service de `volunteer_actions.py` (#778),
depuis le retrait du geste admin (#780) — routers distincts, « le chemin dit
qui peut appeler ».
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import DbId, require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.user import User
from app.schemas.volunteer_action import AdminVolunteerActionOut
from app.services import volunteer_action_service

router = APIRouter(tags=["admin-volunteer-actions"])


@router.get("/admin/volunteer-actions/pending", response_model=list[AdminVolunteerActionOut])
def list_pending_declarations(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.ATHLETES_VOLUNTEER_VALIDATE)),
):
    return volunteer_action_service.list_pending(db)


@router.post(
    "/admin/volunteer-actions/{action_id}/accept", response_model=AdminVolunteerActionOut
)
def accept_action(
    action_id: DbId,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(P.ATHLETES_VOLUNTEER_VALIDATE)),
):
    action = volunteer_action_service.accept(db, admin_user_id=admin.id, action_id=action_id)
    db.commit()
    db.refresh(action)
    return action


@router.post(
    "/admin/volunteer-actions/{action_id}/reject", response_model=AdminVolunteerActionOut
)
def reject_action(
    action_id: DbId,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(P.ATHLETES_VOLUNTEER_VALIDATE)),
):
    action = volunteer_action_service.reject(db, admin_user_id=admin.id, action_id=action_id)
    db.commit()
    db.refresh(action)
    return action


@router.get(
    "/admin/athletes/{athlete_id}/volunteer-actions/validated",
    response_model=list[AdminVolunteerActionOut],
)
def list_validated_actions_for_athlete(
    athlete_id: DbId,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.ATHLETES_VOLUNTEER_VALIDATE)),
):
    """Fiche athlète (#781) — suffixe `/validated`, posé à l'époque pour ne pas
    faire porter deux pouvoirs différents au même chemin que l'ancienne
    création admin, retirée depuis par #780 (research.md D1)."""
    return volunteer_action_service.list_validated_for_athlete(db, athlete_id=athlete_id)


@router.delete("/admin/volunteer-actions/{action_id}", status_code=204)
def delete_action(
    action_id: DbId,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(P.ATHLETES_VOLUNTEER_VALIDATE)),
):
    """Supprime une déclaration, quel que soit son statut (#818) — même
    pouvoir que `accept_action`/`reject_action`, pas de garde dédiée (research.md D1)."""
    volunteer_action_service.delete(db, admin_user_id=admin.id, action_id=action_id)
    db.commit()
