"""Les doublons suspects — lecture (#288) et mise à l'écart d'une paire (#754).

Couche mince : la garde, l'appel au service, la sérialisation. Le réglage de la
détection — les trois motifs, les deux seuils et pourquoi ils diffèrent — vit
dans `services/course_duplicates.py`, et nulle part ailleurs. Le filtrage des
paires écartées vit au même endroit, dans `find_candidates`.

`courses:sources` et non `courses:write` : cette liste est la porte d'entrée de
la fusion (#289) et de l'arbitrage entre chronométreurs (#285), dont l'issue
réécrit ou supprime des résultats. Corriger le nom d'une épreuve n'est pas le
même geste.

La garde est posée **sur la route**, jamais sur le router (#115, FR-018) : le
même préfixe `/admin/` porte le signalement anonyme du site public.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.user import User
from app.schemas.course_duplicates import (
    DuplicateCandidateCount,
    DuplicateCandidateList,
    DuplicateIgnoreCreate,
    DuplicateIgnoreOut,
)
from app.services import course_duplicates

router = APIRouter(tags=["admin"])


@router.get("/admin/courses/duplicates", response_model=DuplicateCandidateList)
def list_duplicates(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.COURSES_SOURCES)),
) -> DuplicateCandidateList:
    """Les paires d'épreuves qui pourraient n'en faire qu'une, avec leur motif.

    Ni pagination ni filtre : la liste sort 0 paire sur les 95 épreuves de la
    base de développement, et une liste de suspicions qui aurait besoin d'être
    paginée serait le signe que le seuil est à revoir, pas que l'écran manque
    d'outillage.
    """
    return DuplicateCandidateList(candidates=course_duplicates.find_candidates(db))


@router.get("/admin/courses/duplicates/count", response_model=DuplicateCandidateCount)
def count_duplicates(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.COURSES_SOURCES)),
) -> DuplicateCandidateCount:
    """La taille de la liste ci-dessus — pour la pastille de la nav (#726).

    Même garde que la liste : quiconque ne peut pas voir les paires ne doit pas
    non plus en connaître le nombre.
    """
    return DuplicateCandidateCount(total=len(course_duplicates.find_candidates(db)))


@router.post(
    "/admin/courses/duplicates/ignore", response_model=DuplicateIgnoreOut, status_code=201
)
def ignore_duplicate(
    body: DuplicateIgnoreCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(P.COURSES_SOURCES)),
) -> dict:
    """Écarte une paire suspecte : elle ne revient plus dans la liste ci-dessus (#754).

    Même garde que la liste, `courses:sources`, et non `courses:delete` comme la
    fusion : contrairement à elle, ce geste ne supprime aucune donnée, il ne fait
    qu'enregistrer un arbitrage humain — la même famille de décision que la
    bascule de source (#285), pas une suppression d'épreuve (#287).
    """
    resultat = course_duplicates.ignore_pair(
        db, course_id_a=body.course_id_a, course_id_b=body.course_id_b, user_id=user.id
    )
    db.commit()
    return resultat
