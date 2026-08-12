"""Arbitrage des sources d'une épreuve — la bascule de l'active (#285).

Un module à part d'`admin_data.py`, pour deux raisons qui tiennent au geste et
non au rangement : il est le seul de l'administration à **scraper**, donc à
dépendre de `Settings` et à durer des secondes, et il est le premier d'une série
que le lot 3 de #275 complète (aperçu de fusion, absorption, doublons suspects).

Couche mince, comme ses voisins : validation, délégation à
`services/admin_actions.py`, `commit`. La transaction se clôt **ici** — c'est ce
qui rend le geste et sa trace indissociables (FR-015), et ce qui fait qu'un refus
levé par le service n'écrit rien du tout, ni classement ni journal.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.exceptions import DomainError
from app.core.permissions import P
from app.models.user import User
from app.schemas.course import CourseSourceOut, CourseSourceSwitch
from app.services import admin_actions

router = APIRouter(tags=["admin"])


@router.patch(
    "/admin/courses/{course_id}/sources/{source_id}",
    response_model=list[CourseSourceOut],
)
def switch_course_source(
    course_id: int,
    source_id: int,
    body: CourseSourceSwitch,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(require_permission(P.COURSES_SOURCES)),
):
    """Désigne le chronométreur qui fait foi, et **réécrit le classement** (D2).

    Gardée par `courses:sources` et non par `courses:write` : le pouvoir voisin
    est borné aux quatre champs d'identité, où corriger un libellé ne détruit
    rien. Ici les résultats affichés sont remplacés dans leur intégralité — le
    réutiliser aurait élargi un pouvoir déjà distribué sans que personne ne l'ait
    décidé.

    Rend la liste des sources telle qu'elle sera affichée, dans l'ordre de
    `GET /courses/{id}/sources` (#284) : l'écran se réaffiche sans second appel,
    et le front n'a qu'une seule forme à connaître pour cette donnée.

    **Bloquant, et sans progression.** #275 tranche que la bascule et le
    re-scrape à la demande (#118) « doivent partager le même mécanisme, pas en
    inventer deux » : le SSE d'administration appartient donc à #118, et aucun
    critère d'acceptation de #285 ne porte sur la progression.
    """
    if not body.is_active:
        # Une épreuve garde son active : l'index partiel autorise **zéro** active,
        # et une épreuve sans active n'est plus scrapée (#282) ni affichée avec sa
        # source (#279). Le seul moyen de changer d'active est d'en désigner une
        # autre — accepter `false` donnerait un moyen d'éteindre une épreuve sans
        # savoir qu'on le fait.
        raise DomainError(
            "Une épreuve garde toujours une source principale : désignez celle qui "
            "doit faire foi plutôt que de désactiver l'actuelle."
        )
    sources = admin_actions.switch_course_source(
        db,
        course_id=course_id,
        source_id=source_id,
        user_id=user.id,
        settings=settings,
    )
    db.commit()
    return sources
