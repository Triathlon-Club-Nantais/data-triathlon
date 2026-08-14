"""Re-scrape à la demande d'une course depuis le back-office (#118).

Même famille SSE que `POST /scrape/event/stream` (`scrape.py`) et même
mécanisme de progression que la bascule de source (#285) — #275 tranche que
les deux « doivent partager le même mécanisme, pas en inventer deux ».

**La garde d'existence/concurrence est synchrone, pas dans le générateur.**
`admin_actions.iter_rescrape_course` est une fonction ordinaire (pas un
générateur) précisément pour ça : appelée ici, elle lève 404/409 *avant* que
`StreamingResponse` existe. La raison tient à Starlette :
`StreamingResponse.stream_response` envoie le statut HTTP **avant** de tirer
le premier élément du générateur — une exception levée depuis l'intérieur
d'un générateur déjà en `StreamingResponse` ne peut plus jamais devenir un
404/409, seulement une coupure de flux à 200.
"""
import json
from dataclasses import asdict, is_dataclass

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import require_permission
from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.core.permissions import P
from app.models.user import User
from app.services import admin_actions

router = APIRouter(tags=["admin"])


def _json_default(value: object) -> object:
    """Même filet que `scrape.py` : dataclasses (`Reassignment`…) non sérialisables nativement."""
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return str(value)


#: Même padding que `scrape.py` — voir sa docstring pour le détail du piège
#: de buffering navigateur qu'il contourne.
_SSE_INITIAL_PADDING = b":" + b" " * 2048 + b"\n\n"


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
        events = admin_actions.iter_rescrape_course(
            db, course_id=course_id, user_id=user.id, settings=settings
        )
    except Exception:
        # La garde (404/409) a levé avant tout octet du flux — rien à laisser
        # tourner en fond, la session peut être refermée ici.
        db.close()
        raise

    def generate():
        yield _SSE_INITIAL_PADDING
        for event in events:
            yield f"data: {json.dumps(event, default=_json_default)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Content-Encoding": "identity",
        },
    )
