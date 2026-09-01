"""Router public : formulaire self-service de déclaration de bénévolat pour
un athlète, créditant le quota de saison (#778).

Aucune session individuelle exigée (#809) — seul le mot de passe partagé du
site (`require_site_access`, posé en amont sur tout le routeur) ferme cette
route, sur le patron de `feedback.py` (#267) : `optional_user` résout une
session SSO si présente (l'auteur reste alors tracé) et rend `None` sinon,
sans jamais lever 401. Aucun pouvoir RBAC n'est exigé. L'endpoint admin
existant (`admin_data.py`,
`POST /admin/athletes/{athlete_id}/volunteer-actions`) n'est pas touché.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import optional_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.volunteer_action import VolunteerActionSelfCreate, VolunteerActionSelfOut
from app.services import volunteer_action_service

router = APIRouter(tags=["volunteer-actions"])


@router.post("/volunteer-actions", status_code=201, response_model=VolunteerActionSelfOut)
def creer_pour_un_athlete(
    body: VolunteerActionSelfCreate,
    db: Session = Depends(get_db),
    user: User | None = Depends(optional_user),
):
    action = volunteer_action_service.create_pending(
        db,
        declared_by_user_id=user.id if user else None,
        athlete_id=body.athlete_id,
        title=body.title,
        description=body.description,
    )
    db.commit()
    db.refresh(action)
    return action
