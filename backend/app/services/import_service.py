"""
Service d'import en masse d'une épreuve (tous les participants).

Inclut le cache TTL (court-circuite le re-scraping si la course est fraîche),
la déduplication par (course, dossard), un rollback explicite en cas d'erreur,
le calcul de l'indice de fiabilité de chaque course touchée (`services/quality.py`),
et un générateur de progression pour le streaming SSE.
"""
import logging
from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import InvalidUrlError, ProviderNotSupportedError, ScraperError
from app.models.course import Course
from app.repositories import course_repository, participation_repository
from app.scrapers import scrape_event_all as registry_scrape_event_all
from app.scrapers.base import ScrapedResult
from app.services import cache, mapping, quality

logger = logging.getLogger(__name__)


def _validate_url(url: str) -> str:
    url = (url or "").strip()
    if not url.startswith("http"):
        raise InvalidUrlError()
    return url


def _scrape_all(url: str) -> list[ScrapedResult]:
    try:
        return registry_scrape_event_all(url)
    except ValueError as exc:  # provider non supporté pour l'import en masse
        raise ProviderNotSupportedError(str(exc)) from exc
    except Exception as exc:
        logger.warning("Échec import %s : %s", url, exc)
        raise ScraperError(f"Erreur lors de l'import : {exc}") from exc


class _Persister:
    """Persiste les résultats scrapés avec déduplication et caches en mémoire.

    Deux clés de déduplication, par course :
      - le dossard, quand il existe (`uq_participation_bib`) ;
      - sinon l'athlète, en **multiset**. Certains chronométreurs n'attribuent
        pas de dossard ; la même personne peut alors figurer plusieurs fois dans
        les résultats source, et ces occurrences doivent survivre au réimport
        sans être dupliquées. On décompte donc les participations sans dossard
        déjà en base au lieu de tester leur simple présence.
    """

    def __init__(self, db: Session, event_url: str):
        self.db = db
        self.event_url = event_url
        self._bibs: dict[int, set[str]] = {}
        self._added_bibs: dict[int, set[str]] = {}
        self._duplicate_bibs: dict[int, int] = {}
        self._athlete_credits: dict[int, dict[int, int]] = {}
        self._courses: dict[int, Course] = {}
        self.imported = 0
        self.skipped = 0

    def add(self, scraped: ScrapedResult) -> None:
        course = mapping.get_or_create_course(self.db, scraped, self.event_url)
        self._courses[course.id] = course
        bib = scraped.bib_number or None

        if bib is not None:
            bibs = self._bibs.setdefault(
                course.id, participation_repository.existing_bibs_for_course(self.db, course.id)
            )
            added = self._added_bibs.setdefault(course.id, set())
            if bib in bibs:
                self.skipped += 1
                # Dossard déjà persisté avant cet import → doublon bénin (re-scrape).
                # Déjà ajouté pendant cet import → la source se contredit, la ligne est
                # perdue : c'est une anomalie de fiabilité (cf. services/quality.py).
                if bib in added:
                    self._duplicate_bibs[course.id] = self._duplicate_bibs.get(course.id, 0) + 1
                return

        # Sans dossard, l'identité repose sur l'athlète : il faut le résoudre d'abord.
        athlete = mapping.get_or_create_athlete(self.db, scraped)
        if bib is None:
            credits = self._athlete_credits.setdefault(
                course.id,
                participation_repository.athlete_counts_without_bib(self.db, course.id),
            )
            if credits.get(athlete.id, 0) > 0:
                credits[athlete.id] -= 1
                self.skipped += 1
                return

        participation_repository.create(
            self.db,
            **mapping.participation_fields(
                scraped, athlete_id=athlete.id, course_id=course.id
            ),
        )
        if bib is not None:
            bibs.add(bib)
            added.add(bib)
        self.imported += 1

    def finalize(self) -> None:
        for course_id, course in self._courses.items():
            course_repository.touch_scraped_at(self.db, course)
            report = quality.analyze(
                participation_repository.list_for_course(self.db, course_id),
                duplicate_bibs=self._duplicate_bibs.get(course_id, 0),
            )
            course_repository.set_quality(
                self.db,
                course,
                is_reliable=report.is_reliable,
                quality_issues=report.anomalies,
            )


def _cached_result(db: Session, url: str, settings: Settings) -> dict | None:
    """Si une course fraîche existe pour cette URL, renvoie le résultat sans re-scraper."""
    existing = course_repository.get_latest_by_source_url(db, url)
    if existing and cache.is_fresh(db, existing, settings):
        count = len(participation_repository.existing_bibs_for_course(db, existing.id))
        logger.info("Cache TTL frais pour %s — re-scraping court-circuité", url)
        return {"imported": 0, "skipped": count, "cached": True}
    return None


def import_event(db: Session, url: str, settings: Settings) -> dict:
    """Import complet (bloquant). Renvoie {imported, skipped, [cached]}."""
    url = _validate_url(url)

    cached = _cached_result(db, url, settings)
    if cached is not None:
        return cached

    results = _scrape_all(url)
    if not results:
        return {"imported": 0, "skipped": 0}

    persister = _Persister(db, url)
    try:
        for scraped in results:
            persister.add(scraped)
        persister.finalize()
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Rollback de l'import %s", url)
        raise ScraperError("Erreur lors de l'enregistrement des résultats.") from None

    return {"imported": persister.imported, "skipped": persister.skipped}


def iter_import_event(db: Session, url: str, settings: Settings) -> Iterator[dict]:
    """
    Générateur de progression pour le SSE. Émet des dicts de phase :
      {phase: scraping} → {phase: saving, progress, total, imported, skipped}
      → {phase: done, …}   (ou {phase: error, message})
    """
    try:
        url = _validate_url(url)
    except InvalidUrlError as exc:
        yield {"phase": "error", "message": exc.message}
        return

    cached = _cached_result(db, url, settings)
    if cached is not None:
        yield {"phase": "done", "total": cached["skipped"], **cached}
        return

    yield {"phase": "scraping", "message": "Récupération des participants…"}
    try:
        results = _scrape_all(url)
    except (ProviderNotSupportedError, ScraperError) as exc:
        yield {"phase": "error", "message": exc.message}
        return

    total = len(results)
    if total == 0:
        yield {"phase": "done", "imported": 0, "skipped": 0, "total": 0}
        return

    persister = _Persister(db, url)
    yield {"phase": "saving", "total": total, "imported": 0, "skipped": 0, "progress": 0}
    try:
        for i, scraped in enumerate(results):
            persister.add(scraped)
            if (i + 1) % 20 == 0 or i == total - 1:
                yield {
                    "phase": "saving",
                    "total": total,
                    "imported": persister.imported,
                    "skipped": persister.skipped,
                    "progress": i + 1,
                }
        persister.finalize()
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Rollback de l'import streaming %s", url)
        yield {"phase": "error", "message": "Erreur lors de l'enregistrement des résultats."}
        return

    yield {
        "phase": "done",
        "imported": persister.imported,
        "skipped": persister.skipped,
        "total": total,
    }
