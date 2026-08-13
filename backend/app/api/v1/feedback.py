"""Router public : soumission d'un signalement (#267).

**Le chemin dit qui peut appeler.** Le signalement vient du bouton flottant du
site, chez un visiteur anonyme : c'est une ressource publique, et elle vit donc
sous `/feedback`, pas sous `/admin/feedback` où le seul verbe public aurait
côtoyé trois verbes gardés. La consultation et l'instruction, elles, restent
dans `admin_feedback.py` avec leurs pouvoirs.

Ce que ce découpage supprime : la seule route qu'une garde de préfixe posée sur
`/admin` couperait sans que personne ne le veuille (FR-018, FR-022). Il reste
un cas de ce genre dans l'API — `POST /admin/pending-providers` — mais celui-là
est **publié** sous `/api/v1`, donc figé par le Principe IV de la constitution ;
`/feedback` ne l'est pas encore, et c'est maintenant ou jamais.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import optional_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.feedback import FeedbackCreate, FeedbackCreated
from app.services import feedback_service

router = APIRouter(tags=["feedback"])

#: Signalement rejeté en silence (honeypot) : même réponse qu'un succès réel,
#: sans qu'aucune ligne n'existe — `id=0` n'est jamais une clé réelle
#: (research.md §D2).
_REPONSE_HONEYPOT = FeedbackCreated(id=0, status="nouveau")


@router.post("/feedback", status_code=201, response_model=FeedbackCreated)
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
