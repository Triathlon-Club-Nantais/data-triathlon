"""La revue d'identité des athlètes (#908) : lecture, compte, mise à l'écart d'une paire ou d'un cas à une fiche, confirmation d'un club.

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
    ConfirmedIdentityClubList,
    DismissedIdentityCaseList,
    IdentityCaseDismissCreate,
    IdentityCaseDismissOut,
    IdentityClubConfirmCreate,
    IdentityClubConfirmOut,
    IdentityPairIgnoreCreate,
    IdentityPairIgnoreOut,
    IdentityReviewCount,
    IdentityReviewList,
    IgnoredIdentityPairList,
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
    return IdentityReviewCount(total=athlete_identity_review.count(db))


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


@router.post("/admin/identity-review/confirm-club", response_model=IdentityClubConfirmOut, status_code=201)
def confirm_identity_club(
    body: IdentityClubConfirmCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(P.ATHLETES_WRITE)),
) -> IdentityClubConfirmOut:
    """Confirme un club pour une fiche (#1209) : il ne la signale plus, et l'import
    y rattache les résultats publiés sous ce club."""
    out = athlete_identity_review.confirm_club(
        db, athlete_id=body.athlete_id, club_key=body.club_key, user_id=user.id
    )
    db.commit()
    return IdentityClubConfirmOut(**out)


@router.get("/admin/identity-review/ignored", response_model=IgnoredIdentityPairList)
def list_ignored_identity_pairs(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.ATHLETES_WRITE)),
) -> IgnoredIdentityPairList:
    """Les paires écartées, pour revoir un arbitrage (#1243)."""
    return IgnoredIdentityPairList(pairs=athlete_identity_review.list_ignored(db))


@router.delete("/admin/identity-review/ignored/{pair_id}", status_code=204)
def unignore_identity_pair(
    pair_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(P.ATHLETES_WRITE)),
) -> None:
    """Annule une mise à l'écart : la paire revient dans la revue."""
    athlete_identity_review.unignore_pair(db, pair_id=pair_id, user_id=user.id)
    db.commit()


@router.get("/admin/identity-review/confirmed-clubs", response_model=ConfirmedIdentityClubList)
def list_confirmed_identity_clubs(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.ATHLETES_WRITE)),
) -> ConfirmedIdentityClubList:
    """Les clubs confirmés pour une fiche, pour revoir un arbitrage (#1243)."""
    return ConfirmedIdentityClubList(clubs=athlete_identity_review.list_confirmed_clubs(db))


@router.delete("/admin/identity-review/confirmed-clubs/{known_id}", status_code=204)
def unconfirm_identity_club(
    known_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(P.ATHLETES_WRITE)),
) -> None:
    """Annule une confirmation de club : la fiche est de nouveau signalée pour lui."""
    athlete_identity_review.unconfirm_club(db, known_id=known_id, user_id=user.id)
    db.commit()


@router.post("/admin/identity-review/dismiss", response_model=IdentityCaseDismissOut, status_code=201)
def dismiss_identity_case(
    body: IdentityCaseDismissCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(P.ATHLETES_WRITE)),
) -> IdentityCaseDismissOut:
    """Écarte un cas à une seule fiche (#1252) : il ne revient que si ses données changent."""
    out = athlete_identity_review.dismiss_case(db, athlete_id=body.athlete_id, reason=body.reason, user_id=user.id)
    db.commit()
    return IdentityCaseDismissOut(**out)


@router.get("/admin/identity-review/dismissed", response_model=DismissedIdentityCaseList)
def list_dismissed_identity_cases(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.ATHLETES_WRITE)),
) -> DismissedIdentityCaseList:
    """Les cas à une seule fiche écartés, pour revoir un arbitrage."""
    return DismissedIdentityCaseList(cases=athlete_identity_review.list_dismissed(db))


@router.delete("/admin/identity-review/dismissed/{case_id}", status_code=204)
def undismiss_identity_case(
    case_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(P.ATHLETES_WRITE)),
) -> None:
    """Annule une mise à l'écart : le cas revient dans la revue s'il tient toujours."""
    athlete_identity_review.undismiss_case(db, case_id=case_id, user_id=user.id)
    db.commit()
