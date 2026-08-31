"""Router admin du workflow de validation des actions de bénévolat pour le
quota de saison (#779) — file d'attente, accepter, refuser. La création
(#709) vit dans `admin_data.py`, le self-service (#778) dans
`volunteer_actions.py` — routers distincts, « le chemin dit qui peut
appeler ».
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.user import User
from app.schemas.volunteer_action import AdminVolunteerActionOut
from app.services import volunteer_action_service

router = APIRouter(tags=["admin-volunteer-actions"])


@router.get("/admin/volunteer-actions/pending", response_model=list[AdminVolunteerActionOut])
def lister_les_declarations_en_attente(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.ATHLETES_VOLUNTEER_VALIDATE)),
):
    return volunteer_action_service.list_pending(db)


@router.post(
    "/admin/volunteer-actions/{action_id}/accept", response_model=AdminVolunteerActionOut
)
def accepter(
    action_id: int,
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
def refuser(
    action_id: int,
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
def lister_les_actions_validees_dun_athlete(
    athlete_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.ATHLETES_VOLUNTEER_VALIDATE)),
):
    """Fiche athlète (#781) — suffixe `/validated` distinct du chemin de
    création admin (`POST .../volunteer-actions`, `admin_data.py`, #709),
    pour ne pas faire porter deux pouvoirs différents au même chemin
    (research.md D1)."""
    return volunteer_action_service.list_validated_for_athlete(db, athlete_id=athlete_id)
