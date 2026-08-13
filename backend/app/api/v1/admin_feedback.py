"""Router Admin : instruction des retours utilisateurs (#267).

**Trois routes, deux pouvoirs, aucune publique.** La soumission, elle, est
publique et vit sous `/feedback` (`api/v1/feedback.py`) : le chemin dit qui
peut appeler, et ce module ne porte plus que ce qu'un pouvoir garde.
"""
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.permissions import P
from app.models.user import User
from app.models.user_feedback import UserFeedback
from app.repositories import feedback_repository
from app.schemas.feedback import FeedbackRead, FeedbackUpdate

router = APIRouter(tags=["admin"])


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


@router.get("/admin/feedback", response_model=list[FeedbackRead])
def list_feedback(
    sort: Literal["created_at", "type", "status"] = "created_at",
    order: Literal["asc", "desc"] = "desc",
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.FEEDBACK_READ)),
):
    entries = feedback_repository.list_sorted(db, sort=sort, order=order)
    return [_vue(entry) for entry in entries]


@router.get("/admin/feedback/{feedback_id}", response_model=FeedbackRead)
def get_feedback(
    feedback_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.FEEDBACK_READ)),
):
    entry = feedback_repository.get(db, feedback_id)
    if entry is None:
        raise NotFoundError("Signalement introuvable")
    return _vue(entry)


@router.patch("/admin/feedback/{feedback_id}", response_model=FeedbackRead)
def update_feedback(
    feedback_id: int,
    body: FeedbackUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.FEEDBACK_MANAGE)),
):
    entry = feedback_repository.get(db, feedback_id)
    if entry is None:
        raise NotFoundError("Signalement introuvable")
    if "status" in body.model_fields_set:
        feedback_repository.update_status(db, feedback_id, body.status)
    if "github_url" in body.model_fields_set:
        feedback_repository.set_github_url(db, feedback_id, str(body.github_url))
    db.commit()
    db.refresh(entry)
    return _vue(entry)
