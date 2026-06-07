"""
Service de scraping d'un athlète unique (prévisualisation et sauvegarde manuelle).

Traduit les exceptions des scrapers en exceptions domaine.
"""
import logging

from sqlalchemy.orm import Session

from app.core.exceptions import (
    DuplicateError,
    InvalidUrlError,
    MultipleMatchesError,
    ScraperError,
)
from app.models.participation import Participation
from app.repositories import participation_repository
from app.scrapers import MultipleMatchesError as ScraperMultipleMatches
from app.scrapers import scrape as registry_scrape
from app.scrapers.base import ScrapedResult
from app.services import mapping

logger = logging.getLogger(__name__)


def _validate_url(url: str) -> str:
    url = (url or "").strip()
    if not url.startswith("http"):
        raise InvalidUrlError()
    return url


def preview(url: str, bib: str | None = None) -> ScrapedResult:
    """Scrape un athlète sans persister (prévisualisation du formulaire)."""
    url = _validate_url(url)
    try:
        return registry_scrape(url, bib=bib)
    except ScraperMultipleMatches as exc:
        raise MultipleMatchesError(exc.candidates) from exc
    except Exception as exc:
        logger.warning("Échec scraping %s : %s", url, exc)
        raise ScraperError(f"Erreur lors du scraping : {exc}") from exc


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
