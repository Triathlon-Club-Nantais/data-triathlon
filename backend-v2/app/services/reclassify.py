"""
Re-classement de l'existant en base : normalise les `event_type` vers la forme
canonique, raffine les valeurs nues à partir du nom d'épreuve (même famille
seulement) et complète `distance_km`. Sans réseau, idempotent.

Réutilisé par la migration Alembic. Isolé ici pour être testable hors Alembic.
"""
from sqlalchemy.orm import Session

from app.models.course import Course
from app.repositories import course_repository
from app.scrapers.classify import (
    BARE_TYPES,
    classify_event_type,
    extract_distance_km,
    normalize_event_type,
)


def _sport_base(event_type: str) -> str:
    for base in ("bike-run", "course-a-pied"):
        if event_type.startswith(base):
            return base
    return event_type.split("-", 1)[0]


def _resolve_event_type(course: Course) -> str:
    """Type canonique cible : normalise, puis raffine depuis le nom si le type
    reste nu (même famille uniquement, conservateur)."""
    new_type = normalize_event_type(course.event_type)
    if new_type in BARE_TYPES:
        candidate = classify_event_type(course.name)
        if candidate not in BARE_TYPES and _sport_base(candidate) == _sport_base(new_type):
            new_type = candidate
    return new_type


def reclassify_existing(db: Session) -> int:
    """Applique le re-classement à toutes les courses. Renvoie le nombre modifié."""
    changed = 0
    for course in db.query(Course).all():
        new_type = _resolve_event_type(course)

        # Backfill distance_km.
        if course.distance_km is None:
            km = extract_distance_km(course.name)
            if km is not None:
                course.distance_km = km
                changed += 1

        if new_type == course.event_type:
            continue

        # Collision d'identité (nom, date, new_type) avec une course existante ?
        target = course_repository.get_by_identity(
            db, course.name, course.event_date, new_type
        )
        if target is not None and target.id != course.id:
            # Fusion : repointer les participations vers la course canonique via
            # la relation (back_populates), pour les retirer de
            # `course.participations` AVANT le delete et éviter le cascade
            # delete-orphan qui les supprimerait. (Limite connue : collision de
            # dossard entre les deux courses non gérée — improbable, événements
            # distincts.)
            for part in list(course.participations):
                part.course = target
            db.delete(course)
        else:
            course.event_type = new_type
        changed += 1

    db.flush()
    return changed
