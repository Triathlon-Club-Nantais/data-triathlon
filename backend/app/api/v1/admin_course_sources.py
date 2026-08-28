"""Arbitrage des sources d'une épreuve — la bascule de l'active (#285, #624).

Un module à part d'`admin_data.py`, pour deux raisons qui tiennent au geste et
non au rangement : il est le seul de l'administration à **scraper**, donc à
dépendre de `Settings` et à durer des secondes, et il est le premier d'une série
que le lot 3 de #275 complète (aperçu de fusion, absorption, doublons suspects).

**Ce fichier n'éprouve que le contrat HTTP/SSE** (garde, en-têtes, format des
frames) — la mécanique de scrape/remplacement/purge est couverte par
`test_services/test_admin_actions.py`, patron exact d'`admin_course_rescrape.py`
(#118), dont ce module reprend le mécanisme depuis #624 : la bascule bloquante
dépassait le délai du proxy sur une épreuve fan-out, d'où un 502 avant même le
premier octet.
"""
import json
from dataclasses import asdict, is_dataclass

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import require_permission
from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.core.exceptions import DomainError
from app.core.permissions import P
from app.models.user import User
from app.schemas.course import CourseSourceSwitch
from app.services import admin_actions

router = APIRouter(tags=["admin"])


def _json_default(value: object) -> object:
    """Même filet que `scrape.py`/`admin_course_rescrape.py` : dataclasses
    (`Reassignment`…) non sérialisables nativement."""
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return str(value)


#: Même padding que `scrape.py`/`admin_course_rescrape.py` — contourne le
#: buffering de proxy/navigateur qui retiendrait les tout premiers octets.
_SSE_INITIAL_PADDING = b":" + b" " * 2048 + b"\n\n"

#: Même battement que `scrape.py::generate()`/`admin_course_rescrape.py` (#705,
#: #731) — traduit la sentinelle `admin_actions.SSE_HEARTBEAT` en ligne de
#: commentaire SSE, ignorée par le parseur front comme le padding initial.
_SSE_HEARTBEAT = b": heartbeat\n\n"


@router.patch("/admin/courses/{course_id}/sources/{source_id}")
def switch_course_source(
    course_id: int,
    source_id: int,
    body: CourseSourceSwitch,
    settings: Settings = Depends(get_settings),
    user: User = Depends(require_permission(P.COURSES_SOURCES)),
):
    """Désigne le chronométreur qui fait foi, et **réécrit le classement** (D2).

    Gardée par `courses:sources` et non par `courses:write` : le pouvoir voisin
    est borné aux quatre champs d'identité, où corriger un libellé ne détruit
    rien. Ici les résultats affichés sont remplacés dans leur intégralité — le
    réutiliser aurait élargi un pouvoir déjà distribué sans que personne ne l'ait
    décidé.

    Le dernier événement du flux (`phase: "done"`) porte la liste des sources
    telle qu'elle sera affichée, dans l'ordre de `GET /courses/{id}/sources`
    (#284) : l'écran se réaffiche sans second appel, et le front n'a qu'une
    seule forme à connaître pour cette donnée.

    **Flux SSE depuis #624**, même mécanisme que le re-scrape à la demande
    (#118) — #275 tranche que les deux « doivent partager le même mécanisme,
    pas en inventer deux ». La bascule bloquante d'origine (#285) dépassait le
    délai du proxy sur une épreuve fan-out (Klikego, 30-40 s), rendant un 502
    avant même le premier octet.

    Session dédiée (`SessionLocal()`, patron de `admin_course_rescrape.py`), et
    pas `Depends(get_db)` : la session doit survivre à la requête HTTP
    elle-même — le thread de fond continue après une déconnexion, là où une
    session injectée par dépendance FastAPI est refermée dès la fin de la
    fonction de route.
    """
    if not body.is_active:
        # Une épreuve garde son active : l'index partiel autorise **zéro** active,
        # et une épreuve sans active n'est plus scrapée (#282) ni affichée avec sa
        # source (#279). Le seul moyen de changer d'active est d'en désigner une
        # autre — accepter `false` donnerait un moyen d'éteindre une épreuve sans
        # savoir qu'on le fait. Refusé avant toute session : c'est une erreur de
        # requête, pas un geste qui aurait besoin de la base.
        raise DomainError(
            "Une épreuve garde toujours une source principale : désignez celle qui "
            "doit faire foi plutôt que de désactiver l'actuelle."
        )

    db = SessionLocal()
    try:
        events = admin_actions.iter_switch_course_source(
            db,
            course_id=course_id,
            source_id=source_id,
            user_id=user.id,
            settings=settings,
        )
    except Exception:
        # La garde (404) a levé avant tout octet du flux — rien à laisser
        # tourner en fond, la session peut être refermée ici.
        db.close()
        raise

    def generate():
        yield _SSE_INITIAL_PADDING
        for event in events:
            if event is admin_actions.SSE_HEARTBEAT:
                yield _SSE_HEARTBEAT
                continue
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
