"""La revue d'identité des athlètes (#908) : lecture, compte, mise à l'écart d'une paire.

Couche mince : la garde, l'appel au service, la sérialisation. Les motifs et
leurs seuils vivent dans `services/athlete_identity_review.py`.

`/admin/identity-review` et non `/admin/athletes/identity-review` : la seconde
forme serait captée par `/admin/athletes/{athlete_id}` et rendrait 422.
`athletes:write`, le pouvoir de la fusion, dont cette liste est la porte
d'entrée. La garde est posée sur la route, jamais sur le router (#115).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.user import User
from app.schemas.athlete_identity import (
    IdentityPairIgnoreCreate,
    IdentityPairIgnoreOut,
    IdentityReviewCount,
    IdentityReviewList,
)
from app.services import athlete_identity_review

router = APIRouter(tags=["admin"])


@router.get("/admin/identity-review", response_model=IdentityReviewList)
def list_identity_cases(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.ATHLETES_WRITE)),
) -> IdentityReviewList:
    """Les cas d'identité à trancher, sans pagination : cas du club et reliquat de la reprise."""
    return IdentityReviewList(candidates=athlete_identity_review.find_candidates(db))


@router.get("/admin/identity-review/count", response_model=IdentityReviewCount)
def count_identity_cases(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.ATHLETES_WRITE)),
) -> IdentityReviewCount:
    """La taille de la liste, pour la pastille de la nav. Même garde que la liste."""
    return IdentityReviewCount(total=len(athlete_identity_review.find_candidates(db)))


@router.post("/admin/identity-review/ignore", response_model=IdentityPairIgnoreOut, status_code=201)
def ignore_identity_pair(
    body: IdentityPairIgnoreCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(P.ATHLETES_WRITE)),
) -> IdentityPairIgnoreOut:
    """Écarte une paire jugée distincte : elle ne revient plus dans la revue."""
    out = athlete_identity_review.ignore_pair(
        db, athlete_id_a=body.athlete_id_a, athlete_id_b=body.athlete_id_b, user_id=user.id
    )
    db.commit()
    return IdentityPairIgnoreOut(**out)
