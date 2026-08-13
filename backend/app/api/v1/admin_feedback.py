"""Router Admin : retours utilisateurs (#267).

**Quatre routes, deux gardes, même contraste que `admin.py`** : le signalement
est public — il vient du bouton flottant du site, chez un visiteur anonyme —
alors que le consulter et l'instruire exigent chacun leur pouvoir. Aucune garde
de préfixe : posée sur `/admin`, elle supprimerait le signalement public sans
que rien ne la nomme (FR-018, même raisonnement que #115).
"""
from typing import Literal

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import optional_user, require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.user import User
from app.models.user_feedback import UserFeedback
from app.repositories import feedback_repository
from app.schemas.feedback import FeedbackCreate, FeedbackCreated, FeedbackRead
from app.services import feedback_service

router = APIRouter(tags=["admin"])

#: Signalement rejeté en silence (honeypot) : même réponse qu'un succès réel,
#: sans qu'aucune ligne n'existe — `id=0` n'est jamais une clé réelle
#: (research.md §D2).
_REPONSE_HONEYPOT = FeedbackCreated(id=0, status="nouveau")


def _vue(entry: UserFeedback) -> FeedbackRead:
    return FeedbackRead(
        id=entry.id,
        type=entry.type,
        title=entry.title,
        body=entry.body,
        page_url=entry.page_url,
        user_agent=entry.user_agent,
        status=entry.status,
        github_url=entry.github_url,
        created_at=entry.created_at,
        email=entry.user.email if entry.user_id else None,
    )


@router.post("/admin/feedback", status_code=201, response_model=FeedbackCreated)
def submit_feedback(
    body: FeedbackCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(optional_user),
):
    entry = feedback_service.submit(
        db,
        type=body.type,
        title=body.title,
        body=body.body,
        page_url=body.page_url,
        user_agent=body.user_agent,
        ip_address=request.client.host if request.client else None,
        user_id=user.id if user else None,
        honeypot=body.honeypot,
    )
    if entry is None:
        return _REPONSE_HONEYPOT
    db.commit()
    db.refresh(entry)
    return FeedbackCreated(id=entry.id, status=entry.status)


@router.get("/admin/feedback", response_model=list[FeedbackRead])
def list_feedback(
    sort: Literal["created_at", "type", "status"] = "created_at",
    order: Literal["asc", "desc"] = "desc",
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.FEEDBACK_READ)),
):
    entries = feedback_repository.list_sorted(db, sort=sort, order=order)
    return [_vue(entry) for entry in entries]
