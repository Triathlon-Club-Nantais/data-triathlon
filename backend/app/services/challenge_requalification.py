"""Reprise des épreuves Challenge importées avant #1008 comme des épreuves.

Module à part de `challenge_service` : il supprime l'épreuve par le geste
d'administration (`admin_actions`), qui dépend de l'import, qui dépend lui-même
de `challenge_service`.
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories import challenge_repository, course_repository
from app.scrapers.utils import heat_is_challenge
from app.services import admin_actions, challenge_service
from app.services.challenge_service import ChallengeRow

#: Écart de date toléré entre une épreuve redatée par heat et son Challenge.
_NEAR_DAYS = 2


@dataclass(frozen=True)
class Requalified:
    course_id: int
    name: str
    linked_course_ids: list[int]
    rows: int


def requalify(db: Session, *, user_id: int | None) -> list[Requalified]:
    """Requalifie en Challenge les épreuves déjà importées qui en sont.

    `user_id=None` liste seulement. Sinon, enregistre le Challenge **puis** supprime
    l'épreuve par le geste d'administration, journalisé : ses athlètes restent,
    référencés par les lignes Challenge.
    """
    done: list[Requalified] = []
    for course in course_repository.list_named_like(db, "challenge"):
        if not heat_is_challenge(course.name) or course.event_date is None:
            continue
        rows = [ChallengeRow.from_participation(p) for p in course.participations]
        found = challenge_service.match(
            db, rows, event_date=course.event_date, exclude_course_ids={course.id}
        )
        if found is None:
            continue
        done.append(Requalified(course.id, course.name, found.course_ids, len(found.athlete_ids)))
        if user_id is not None:
            # Le Challenge déjà importé peut porter la date d'événement quand
            # l'épreuve a été redatée par heat (#1196) : on le reprend.
            existing = challenge_repository.find_named_near(
                db, name=course.name, event_date=course.event_date, days=_NEAR_DAYS
            )
            challenge_service.save(
                db, name=course.name,
                event_date=existing.event_date if existing else course.event_date,
                source_url=course.source_url, rows=rows, found=found,
            )
            admin_actions.delete_course(db, course_id=course.id, user_id=user_id)
    return done
