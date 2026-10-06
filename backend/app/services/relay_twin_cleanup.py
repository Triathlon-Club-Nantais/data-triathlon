"""Épreuves solo laissées à côté de leur jumelle relais (#1195, #1197).

`is_relay` entre dans l'identité d'une épreuve depuis #963. Un heat d'équipe
autrefois typé solo a reçu, au premier rescrape, une épreuve relais à côté de
l'ancienne, sous la même URL : résultats comptés deux fois (La Baule 2025, 146,
148 et 152 à côté de 145, 147 et 151). Depuis #1204 l'import requalifie une
épreuve en place quand il le peut ; ce nettoyage reprend celles qui restent.

Outillé et ponctuel, sur le patron de `timepulse_cleanup` (#1004) : l'import,
lui, ne supprime jamais rien.
"""
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories import course_repository, participation_repository
from app.services import admin_actions


@dataclass(frozen=True)
class RelayTwin:
    course_id: int
    name: str
    source_url: str
    covered_by: int


def find_superseded(db: Session) -> list[RelayTwin]:
    """Les épreuves solo dont **chaque** dossard nommé est repris par leur jumelle relais.

    Jumelle : même URL de source active, même nom, même date, `is_relay` vrai. Un
    seul dossard nommé repris nulle part suffit à garder l'épreuve, les équipes
    absentes du relais (18 à La Baule avant le rescrape) n'étant pas encore
    importées ailleurs.
    """
    courses = course_repository.iter_all(db)
    groups = defaultdict(list)
    for course in courses:
        groups[(course.source_url, course.name, course.event_date)].append(course)

    groups = {key: group for key, group in groups.items() if len(group) > 1}
    ids = [course.id for group in groups.values() for course in group]
    bibs = participation_repository.named_bibs_by_course(db, ids)
    superseded = []
    for group in groups.values():
        relays = [course for course in group if course.is_relay]
        for course in group:
            if course.is_relay or not bibs[course.id]:
                continue
            twin = next((r for r in relays if bibs[course.id] <= bibs[r.id]), None)
            if twin is not None:
                superseded.append(RelayTwin(course.id, course.name, course.source_url, twin.id))
    return sorted(superseded, key=lambda c: c.course_id)


def purge_superseded(db: Session, *, user_id: int) -> list[RelayTwin]:
    """Supprime les épreuves de `find_superseded`, journalisées comme un geste admin."""
    superseded = find_superseded(db)
    for course in superseded:
        admin_actions.delete_course(db, course_id=course.course_id, user_id=user_id)
    db.commit()
    return superseded
