"""Fusion de deux épreuves publiées deux fois — l'aperçu (#286) et l'acte (#287).

Un module à part et non deux ressources de plus dans `admin_data.py` : la fusion
est un geste de l'epic #275 (arbitrage des sources), pas un des quatre gestes
correctifs de #117.

Couche mince : validation, délégation à `services/course_merge.py`, traduction en
HTTP. L'aperçu ne modifie rien ; la fusion est la seule des deux à `commit`.

La garde est posée **sur la route**, jamais sur le préfixe (#115, FR-018) :
`admin.py` monte sous le même `/admin/` le signalement anonyme du site public.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.user import User
from app.schemas.admin import CourseMergeImpact, CourseMergeRequest, CourseMergeResult
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


@router.post("/admin/courses/{course_id}/merge", response_model=CourseMergeResult)
def merge_courses(
    course_id: int,
    body: CourseMergeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(P.COURSES_SOURCES)),
    _delete: User = Depends(require_permission(P.COURSES_DELETE)),
):
    """Absorbe une épreuve dans une autre. Ne re-scrape rien (#287).

    **Deux pouvoirs exigés, et deux `Depends` pour le dire.** `require_permission`
    nomme *un* pouvoir ; les composer est le seul mécanisme disponible, et il n'en
    faut pas de troisième — chaque appel rend une fabrique distincte, donc le cache
    de dépendances de FastAPI ne les confond pas, et `current_user` reste évalué une
    fois. Le geste est à la fois un arbitrage de sources (`courses:sources`) et une
    **suppression d'épreuve** (`courses:delete`) : les résultats de l'absorbée sans
    jumeau de dossard disparaissent, là où la bascule (#285) réimporte. Exiger le
    seul pouvoir d'arbitrage donnerait une suppression à qui n'en a pas reçu le
    droit ; le seul pouvoir de suppression laisserait modifier les sources d'une
    épreuve sans l'avoir reçu. Aucun pouvoir n'est ajouté au catalogue : « fusionner »
    n'est pas une capacité de plus, c'est la conjonction de deux capacités existantes.

    L'absorbée est nommée dans le corps et la cible dans le chemin : la ressource
    s'écrit du point de vue de ce qui **survit**.

    Le `commit` est ici, jamais dans le service : c'est ce qui rend le geste et son
    entrée de journal indissociables — un refus lève avant et n'écrit rien.
    """
    resultat = course_merge.merge_courses(
        db, course_id=course_id, absorbed_id=body.absorbed_id, user_id=user.id
    )
    db.commit()
    return resultat
