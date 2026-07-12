"""Re-scrape en masse des courses déjà en base (force=True, bypass du cache TTL)."""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.repositories import course_repository
from app.services.batch import BatchItem, run_batch
from app.services.progress import ProgressReporter


@dataclass
class RescrapeOutcome:
    """Bilan d'un rescrape-db."""
    total: int = 0
    imported: int = 0
    skipped: int = 0
    errors: int = 0
    dry_run_urls: list[str] = field(default_factory=list)
    interrupted: bool = False


def run_rescrape_db(
    db: Session,
    settings: Settings,
    *,
    dry_run: bool = False,
    older_than: int | None = None,
    provider: str | None = None,
    limit: int | None = None,
    delay: float = 1.0,
    reporter: ProgressReporter | None = None,
) -> RescrapeOutcome:
    """Re-scrape toutes les courses en DB avec force=True (bypass du cache TTL).

    Ne retient que les courses ayant une source_url (clé de re-scraping).
    En dry-run : liste les URLs sans scraper ni persister.
    """
    courses = course_repository.iter_all(
        db, provider=provider, older_than_days=older_than
    )
    courses = [c for c in courses if c.source_url]
    if limit is not None:
        courses = courses[:limit]

    outcome = RescrapeOutcome(total=len(courses))
    if dry_run:
        # Charge utile réservée au dry-run : hors dry-run, embarquer l'URL de
        # chaque course gonflerait la sortie --json de plusieurs dizaines de Ko.
        outcome.dry_run_urls = [c.source_url for c in courses]
        return outcome

    # Le nom de la course vient de la DB : on peut libeller proprement.
    items = [
        BatchItem(url=c.source_url, label=f"{c.provider} · {c.name}") for c in courses
    ]
    totals = run_batch(db, items, settings, force=True, delay=delay, reporter=reporter)

    outcome.imported = totals.imported
    outcome.skipped = totals.skipped
    outcome.errors = totals.errors
    outcome.interrupted = totals.interrupted
    return outcome
