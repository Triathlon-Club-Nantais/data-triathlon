"""File des demandes de rattachement à une fiche athlète (#1325).

Routeur fin : délégation au service, qui journalise ; le routeur commite. Chaque
route porte sa garde.
"""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.core.time import utcnow
from app.models.user import User
from app.schemas.athlete_claim import (
    AthleteClaimReviewRead,
    AthleteLinkRead,
    ClaimantRead,
    LicenseeRead,
    ReviewedAthleteRead,
)
from app.schemas.ids import DbId
from app.services import athlete_claims

router = APIRouter(tags=["admin"])


@router.get("/admin/athlete-claims", response_model=list[AthleteClaimReviewRead])
def list_athlete_claims(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.ATHLETE_CLAIMS_REVIEW)),
):
    return [
        AthleteClaimReviewRead(
            id=review.claim.id,
            created_at=review.claim.created_at,
            user=ClaimantRead.model_validate(review.user),
            athlete=ReviewedAthleteRead.model_validate(review.athlete),
            licensee=LicenseeRead.model_validate(review.licensee) if review.licensee else None,
            email_on_member_list=review.email_on_member_list,
            linked_accounts=review.linked_accounts,
        )
        for review in athlete_claims.list_pending_with_hints(db, utcnow().date())
    ]


@router.get("/admin/athlete-links", response_model=list[AthleteLinkRead])
def list_athlete_links(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.ATHLETE_CLAIMS_REVIEW)),
):
    """Comptes rattachés, et si leur fiche est licenciée au club cette saison (#1633)."""
    return [AthleteLinkRead.model_validate(link) for link in athlete_claims.list_links(db, utcnow().date())]


@router.delete("/admin/athlete-links/{user_id}", status_code=204)
def detach_athlete_link(
    user_id: DbId,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.ATHLETE_CLAIMS_REVIEW)),
):
    athlete_claims.admin_detach(db, user_id, actor_id=actor.id)
    db.commit()
    return Response(status_code=204)


@router.post("/admin/athlete-claims/{claim_id}/approve", status_code=204)
def approve_athlete_claim(
    claim_id: DbId,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.ATHLETE_CLAIMS_REVIEW)),
):
    athlete_claims.approve(db, claim_id, actor_id=actor.id)
    db.commit()
    return Response(status_code=204)


@router.post("/admin/athlete-claims/{claim_id}/reject", status_code=204)
def reject_athlete_claim(
    claim_id: DbId,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.ATHLETE_CLAIMS_REVIEW)),
):
    athlete_claims.reject(db, claim_id, actor_id=actor.id)
    db.commit()
    return Response(status_code=204)
