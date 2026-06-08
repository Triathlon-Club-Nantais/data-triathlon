"""
Service de persistance d'un résultat (saisie manuelle ou import d'épreuve).

`save_one` est la brique unitaire : réutilisée par la saisie manuelle
(`POST /participations`) et en boucle par l'import d'épreuve complète.
"""
import logging

from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateError
from app.models.participation import Participation
from app.repositories import participation_repository
from app.scrapers.base import ScrapedResult
from app.services import mapping

logger = logging.getLogger(__name__)


def save_one(db: Session, scraped: ScrapedResult, event_url: str = "") -> Participation:
    """Persiste un résultat scrapé/édité (athlète + course + participation)."""
    course = mapping.get_or_create_course(db, scraped, event_url)
    if scraped.bib_number and participation_repository.exists_for_bib(
        db, course.id, scraped.bib_number
    ):
        raise DuplicateError(
            f"Ce résultat existe déjà (dossard {scraped.bib_number} — "
            f"{scraped.event_name} / {scraped.event_type})."
        )
    athlete = mapping.get_or_create_athlete(db, scraped)
    participation = participation_repository.create(
        db, **mapping.participation_fields(scraped, athlete_id=athlete.id, course_id=course.id)
    )
    db.commit()
    db.refresh(participation)
    return participation
