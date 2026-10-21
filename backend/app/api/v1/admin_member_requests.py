"""File des demandes d'adhésion (#1785).

Routeur fin : délégation au service, qui journalise ; le routeur commite.
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.user import User
from app.schemas.ids import DbId
from app.schemas.member_request import MemberRequestReviewRead
from app.services import member_requests

router = APIRouter(tags=["admin"])


@router.get("/admin/member-requests", response_model=list[MemberRequestReviewRead])
def list_member_requests(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.MEMBER_REQUESTS_REVIEW)),
):
    return member_requests.list_pending(db)


@router.post("/admin/member-requests/{request_id}/approve", status_code=204)
def approve_member_request(
    request_id: DbId,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.MEMBER_REQUESTS_REVIEW)),
):
    member_requests.approve(db, request_id, actor_id=actor.id)
    db.commit()
    return Response(status_code=204)


@router.post("/admin/member-requests/{request_id}/reject", status_code=204)
def reject_member_request(
    request_id: DbId,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.MEMBER_REQUESTS_REVIEW)),
):
    member_requests.reject(db, request_id, actor_id=actor.id)
    db.commit()
    return Response(status_code=204)
