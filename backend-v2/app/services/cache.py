"""
Cache TTL dynamique (PRD F1).

Une course « en cours » (au moins un participant sans temps final) est re-scrapée
fréquemment ; une course « terminée » est considérée stable longtemps.
"""
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.time import utcnow
from app.models.course import Course
from app.models.participation import Participation


def is_in_progress(db: Session, course_id: int) -> bool:
    """Vrai si au moins une participation n'a pas de temps final (course en cours)."""
    return (
        db.query(Participation.id)
        .filter(
            Participation.course_id == course_id,
            (Participation.total_time.is_(None)) | (Participation.total_time == ""),
        )
        .first()
        is not None
    )


def ttl_seconds(db: Session, course: Course, settings: Settings) -> int:
    if is_in_progress(db, course.id):
        return settings.cache_ttl_in_progress_seconds
    return settings.cache_ttl_finished_seconds


def is_fresh(db: Session, course: Course, settings: Settings) -> bool:
    """Vrai si la course a été scrapée plus récemment que son TTL."""
    if course.scraped_at is None:
        return False
    age = (utcnow() - course.scraped_at).total_seconds()
    return age < ttl_seconds(db, course, settings)
