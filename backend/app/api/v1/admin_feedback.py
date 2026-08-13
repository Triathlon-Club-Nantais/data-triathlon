"""Router Admin : retours utilisateurs (#267).

**Quatre routes, deux gardes, même contraste que `admin.py`** : le signalement
est public — il vient du bouton flottant du site, chez un visiteur anonyme —
alors que le consulter et l'instruire exigent chacun leur pouvoir. Aucune garde
de préfixe : posée sur `/admin`, elle supprimerait le signalement public sans
que rien ne la nomme (FR-018, même raisonnement que #115).
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import optional_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.feedback import FeedbackCreate, FeedbackCreated
from app.services import feedback_service

router = APIRouter(tags=["admin"])

#: Signalement rejeté en silence (honeypot) : même réponse qu'un succès réel,
#: sans qu'aucune ligne n'existe — `id=0` n'est jamais une clé réelle
#: (research.md §D2).
_REPONSE_HONEYPOT = FeedbackCreated(id=0, status="nouveau")


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
