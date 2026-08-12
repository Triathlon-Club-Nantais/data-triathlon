"""Fusion de deux épreuves publiées deux fois — l'aperçu d'impact (#286).

Un module à part et non une ressource de plus dans `admin_data.py` : la fusion
est un geste de l'epic #275 (arbitrage des sources), pas un des quatre gestes
correctifs de #117. La fusion elle-même (#287) viendra ici, à côté de son aperçu.

Couche mince : validation, délégation à `services/course_merge.py`, traduction en
HTTP. Aucun `commit` — cette ressource ne modifie rien.

La garde est posée **sur la route**, jamais sur le préfixe (#115, FR-018) :
`admin.py` monte sous le même `/admin/` le signalement anonyme du site public.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.user import User
from app.schemas.admin import CourseMergeImpact
from app.services import course_merge

router = APIRouter(tags=["admin"])


@router.get("/admin/courses/{course_id}/merge-impact", response_model=CourseMergeImpact)
def course_merge_impact(
    course_id: int,
    absorbed_id: int = Query(description="L'épreuve à absorber, celle qui disparaîtra."),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.COURSES_SOURCES)),
):
    """Chiffre ce qu'une fusion coûterait **avant** de la commettre.

    Gardée par `courses:sources` et non par un pouvoir de lecture, sur le patron
    de `deletion-impact` : qui peut arbitrer les sources peut mesurer, et
    l'inverse n'aurait pas d'usage. `courses:write` ne conviendrait pas non plus
    — sa description est bornée aux quatre champs d'identité d'une épreuve.

    `absorbed_id` est **obligatoire** : sans lui la question n'a pas de réponse,
    et un défaut la ferait porter sur une épreuve choisie par l'API.
    """
    return course_merge.merge_impact(db, course_id=course_id, absorbed_id=absorbed_id)
