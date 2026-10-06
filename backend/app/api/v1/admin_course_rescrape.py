"""Re-scrape à la demande d'une course depuis le back-office (#118).

Même famille SSE que `POST /scrape/event/stream` (`scrape.py`) et même
mécanisme de progression que la bascule de source (#285) — #275 tranche que
les deux « doivent partager le même mécanisme, pas en inventer deux ».

**La garde d'existence/concurrence est synchrone, pas dans le générateur.**
`course_rescrape_service.iter_rescrape_course` est une fonction ordinaire (pas un
générateur) précisément pour ça : appelée ici, elle lève 404/409 *avant* que
`StreamingResponse` existe. La raison tient à Starlette :
`StreamingResponse.stream_response` envoie le statut HTTP **avant** de tirer
le premier élément du générateur — une exception levée depuis l'intérieur
d'un générateur déjà en `StreamingResponse` ne peut plus jamais devenir un
404/409, seulement une coupure de flux à 200.
"""
from fastapi import APIRouter, Depends

from app.api import sse
from app.api.deps import require_permission
from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.core.permissions import P
from app.models.user import User
from app.services import course_rescrape_service

router = APIRouter(tags=["admin"])


@router.post("/admin/courses/{course_id}/rescrape")
def rescrape_course(
    course_id: int,
    settings: Settings = Depends(get_settings),
    user: User = Depends(require_permission(P.COURSES_SOURCES)),
):
    """Re-scrape la source active de la course, en upsert (FR-001 à FR-011).

    Session dédiée (`SessionLocal()`, patron de `scrape_event_stream`), et pas
    `Depends(get_db)` : la session doit survivre à la requête HTTP elle-même
    (FR-011, le thread de fond continue après une déconnexion), là où une
    session injectée par dépendance FastAPI est refermée dès la fin de la
    fonction de route.
    """
    db = SessionLocal()
    try:
        events = course_rescrape_service.iter_rescrape_course(
            db, course_id=course_id, user_id=user.id, settings=settings
        )
    except Exception:
        # La garde (404/409) a levé avant tout octet du flux — rien à laisser
        # tourner en fond, la session peut être refermée ici.
        db.close()
        raise

    return sse.event_stream(events)
