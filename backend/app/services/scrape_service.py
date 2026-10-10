"""
Service de persistance d'un résultat saisi à la main.

`save_one` ne sert qu'à la saisie manuelle (`POST /participations`) : l'import
d'épreuve complète persiste par `import_service`, sans passer par lui.
"""
import logging
from datetime import date

from sqlalchemy.orm import Session

from app.core.club import is_tcn
from app.core.exceptions import DomainError, DuplicateError
from app.core.youth import is_youth
from app.models.participation import Participation
from app.repositories import participation_repository
from app.scrapers.base import ScrapedResult
from app.services import mapping, opposition_service

logger = logging.getLogger(__name__)


class YouthResultError(DomainError):
    status_code = 422
    message = (
        "Les résultats des catégories jeunes (jusqu'à Minime) ne sont pas enregistrés, "
        "sauf pour un membre du club."
    )


def ensure_not_youth(
    event_name: str | None, event_date: date | None, category: str | None, club: str | None
) -> None:
    """Refuse une ligne saisie ou corrigée à la main que l'import écarterait (#1280).

    Règle de l'import (#881) et son exception TCN (#1221) : une ligne seule est
    son propre heat, gardé s'il porte un TCN.
    """
    event_year = event_date.year if event_date else None
    if is_youth(event_name, category, event_year=event_year) and not is_tcn(club):
        raise YouthResultError()


def save_one(db: Session, scraped: ScrapedResult, event_url: str = "") -> Participation:
    """Persiste un résultat scrapé/édité (athlète + course + participation)."""
    opposition_service.ensure_not_opposed(db, scraped.athlete_name, scraped.athlete_firstname)
    ensure_not_youth(scraped.event_name, scraped.event_date, scraped.category, scraped.club)
    course = mapping.get_or_create_course(db, scraped, event_url).course
    if scraped.bib_number and participation_repository.exists_for_bib(
        db, course.id, scraped.bib_number
    ):
        raise DuplicateError(
            f"Ce résultat existe déjà (dossard {scraped.bib_number} — "
            f"{scraped.event_name} / {scraped.event_type})."
        )
    athlete = mapping.get_or_create_athlete(db, scraped, event_date=course.event_date)
    participation = participation_repository.create(
        db, **mapping.participation_fields(scraped, athlete_id=athlete.id, course_id=course.id)
    )
    db.commit()
    db.refresh(participation)
    return participation
