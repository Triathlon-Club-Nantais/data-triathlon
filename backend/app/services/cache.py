"""
Cache TTL dynamique (PRD F1).

Une course « en cours » (au moins un participant sans temps final) est re-scrapée
fréquemment ; une course « terminée » est considérée stable longtemps.

**La fraîcheur est celle de l'épreuve, pas d'une URL** (#281). Depuis que N
sources peuvent désigner la même épreuve, la question se pose : une URL passive
porte-t-elle un cache ? Non. Le TTL protège du re-scraping inutile de ce qu'on
**affiche**, et une passive n'alimente aucun affichage — elle n'est même jamais
scrapée (#282). Son `last_scraped_at` n'entre donc pas dans le calcul : la
fraîcheur se lit sur `Course.scraped_at`, alimenté par le seul scraping qui ait
lieu, celui de l'active.

Conséquence côté recherche, et c'est le sens du filtre `is_active` des trois
recherches par URL de `course_repository` : coller la seconde publication d'une
épreuve fraîche ne trouve rien en cache, donc ne renvoie pas le classement de
l'**autre** chronométreur sous l'URL qu'on vient de coller.
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
