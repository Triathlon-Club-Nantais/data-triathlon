"""Épreuves timepulse d'avant #674 que leurs parcours qualifiés remplacent (#1004).

Depuis #674 (27/08), timepulse qualifie le nom d'épreuve par le parcours
(`DUATHLON COUERON - Duathlon S Relais`). Une épreuve importée avant garde son nom
nu ; son premier rescrape crée les épreuves qualifiées à côté d'elle, et les mêmes
résultats sont comptés deux fois. La règle R ne peut pas les rapprocher : une URL
timepulse couvre tous les parcours d'un événement.

Nettoyage outillé et ponctuel, lancé après le premier rescrape timepulse de chaque
environnement : l'import, lui, ne supprime jamais rien.
"""
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories import course_repository, participation_repository
from app.services import admin_actions

PROVIDER = "timepulse"


@dataclass(frozen=True)
class SupersededCourse:
    course_id: int
    name: str
    source_url: str
    covered_by: list[int]


def find_superseded(db: Session) -> list[SupersededCourse]:
    """Les épreuves non qualifiées dont **chaque** dossard nommé est repris ailleurs.

    Remplaçantes : même URL de source active, même date, et un nom qui prolonge le
    sien par ` - <parcours>`. Un seul dossard nommé repris nulle part suffit à
    garder l'épreuve.
    """
    courses = course_repository.iter_all(db, provider=PROVIDER)
    groups = defaultdict(list)
    for course in courses:
        groups[(course.source_url, course.event_date)].append(course)

    bibs = participation_repository.named_bibs_by_course(db, [c.id for c in courses])
    superseded = []
    for group in groups.values():
        for course in group:
            qualified = [
                other for other in group
                if other.id != course.id and other.name.startswith(f"{course.name} - ")
            ]
            if not qualified or not bibs[course.id]:
                continue
            covered = set().union(*(bibs[other.id] for other in qualified))
            if bibs[course.id] <= covered:
                superseded.append(SupersededCourse(
                    course_id=course.id,
                    name=course.name,
                    source_url=course.source_url,
                    covered_by=[other.id for other in qualified],
                ))
    return sorted(superseded, key=lambda c: c.course_id)


def purge_superseded(db: Session, *, user_id: int) -> list[SupersededCourse]:
    """Supprime les épreuves de `find_superseded`, journalisées comme un geste admin."""
    superseded = find_superseded(db)
    for course in superseded:
        admin_actions.delete_course(db, course_id=course.course_id, user_id=user_id)
    db.commit()
    return superseded
