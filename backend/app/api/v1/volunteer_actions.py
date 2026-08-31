"""Router public authentifié : formulaire self-service de déclaration de
bénévolat pour un athlète, créditant le quota de saison (#778).

Toutes les routes exigent une session (`current_user`, 401 sinon), aucune
n'exige de pouvoir RBAC particulier — patron `volunteer_declarations.py`
(#751). L'endpoint admin existant (`admin_data.py`,
`POST /admin/athletes/{athlete_id}/volunteer-actions`) n'est pas touché.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.volunteer_action import VolunteerActionSelfCreate, VolunteerActionSelfOut
from app.services import volunteer_action_service

router = APIRouter(tags=["volunteer-actions"])


@router.post("/volunteer-actions", status_code=201, response_model=VolunteerActionSelfOut)
def creer_pour_un_athlete(
    body: VolunteerActionSelfCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    action = volunteer_action_service.create_pending(
        db,
        declared_by_user_id=user.id,
        athlete_id=body.athlete_id,
        title=body.title,
        description=body.description,
    )
    db.commit()
    db.refresh(action)
    return action
