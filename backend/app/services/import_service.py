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
from app.models.participation import Participation
from app.repositories import course_repository, participation_repository
from app.scrapers import scrape_event_all as registry_scrape_event_all
from app.scrapers.base import STATUS_DNF, STATUS_FINISHER, ScrapedResult
from app.services import cache, mapping, quality

logger = logging.getLogger(__name__)


def _validate_url(url: str) -> str:
    url = (url or "").strip()
    if not url.startswith("http"):
        raise InvalidUrlError()
    return url


def _scrape_all(url: str) -> list[ScrapedResult]:
    try:
        results = registry_scrape_event_all(url)
    except ValueError as exc:  # provider non supporté pour l'import en masse
        raise ProviderNotSupportedError(str(exc)) from exc
    except Exception as exc:
        logger.warning("Échec import %s : %s", url, exc)
        raise ScraperError(f"Erreur lors de l'import : {exc}") from exc
    _require_event_name(url, results)
    return results


def _require_event_name(url: str, results: list[ScrapedResult]) -> None:
    """Refuse un scrape dont l'épreuve n'a pas de nom : la course serait illisible.

    Une `Course` sans nom n'est ni lisible dans l'UI ni retrouvable à la
    recherche, et son identité `(nom, date, type)` entre en collision avec
    toute autre course anonyme du même jour. On échoue avant d'écrire : le
    batch la compte en erreur et l'opérateur la voit dans son bilan.
    """
    if any(not (r.event_name or "").strip() for r in results):
        raise ScraperError(
            f"Nom d'épreuve introuvable pour {url} — import refusé "
            "(une course sans nom serait inexploitable)."
        )


#: Clés d'appariement / d'identité : jamais réécrites par la fusion prudente.
#: `athlete_id` en fait partie — la réconciliation d'identité est le périmètre
#: séparé de #66/#67, pas celui de ce rafraîchissement de valeurs.
_CLES_APPARIEMENT = frozenset({"athlete_id", "course_id", "bib_number"})


def _is_empty(value: object) -> bool:
    """Vide au sens de la fusion prudente : `None`, chaîne vide, dict vide.

    `False` et `0` n'en sont **pas** : un `is_relay=False` est une affirmation du
    scraper, pas une absence, et doit pouvoir corriger un `True` erroné. Un test
    de vérité pythonien (`if value:`) confondrait les deux — d'où l'égalité
    explicite, qui distingue `False`/`0` de `""`/`{}` (`False == {}` est faux).
    """
    return value is None or value == "" or value == {}


def _merge_fields(existing, fields: dict) -> dict:
    """Champs à écrire : source non vide ET différente de la base.

    `status` est exclu ici (traité par `_resolve_status`, car jamais vide) ; les
    clés d'appariement aussi. Comparer avant d'écrire évite des `UPDATE` inutiles
    sur des milliers de lignes inchangées et distingue `updated` de `skipped`.
    """
    changes = {}
    for key, value in fields.items():
        if key in _CLES_APPARIEMENT or key == "status":
            continue
        if _is_empty(value):
            continue
        if getattr(existing, key) != value:
            changes[key] = value
    return changes


def _resolve_status(existing, scraped: ScrapedResult, changes: dict) -> str:
    """Statut fusionné. Un statut explicite du scraper écrase ; sinon on le
    re-dérive du `total_time` **fusionné** (base + écrasement éventuel), jamais du
    scrapé seul : une source ayant perdu le temps ne doit pas basculer un
    finisher en DNF alors que le temps, lui, survit (vide n'écrase pas).
    """
    if scraped.status:
        return scraped.status
    merged_total = changes.get("total_time", existing.total_time)
    return STATUS_FINISHER if merged_total else STATUS_DNF


class _Persister:
    """Persiste les résultats scrapés en **upsert**, avec déduplication.

    Point de persistance unique des trois entrées (rescrape-db, import-sheet, web
    SSE). Deux clés d'appariement, par course :
      - le dossard, quand il existe (`uq_participation_bib`) ;
      - sinon l'athlète, en **multiset** — mais la mise à jour ne s'applique que
        si l'athlète n'a qu'une seule participation sur la course (cf. `add`).

    Une ligne appariée est **fusionnée prudemment** (`_merge_fields`) : la source
    ne réécrit que ses valeurs non vides. `athlete_id` n'est jamais réécrit.
    """

    def __init__(self, db: Session, event_url: str):
        self.db = db
        self.event_url = event_url
        self._by_bib: dict[int, dict[str, Participation]] = {}
        self._added_bibs: dict[int, set[str]] = {}
        self._duplicate_bibs: dict[int, int] = {}
        self._without_bib: dict[int, dict[int, list[Participation]]] = {}
        self._credits: dict[int, dict[int, int]] = {}
        self._updated_single: dict[int, set[int]] = {}
        self._courses: dict[int, Course] = {}
        self.imported = 0
        self.updated = 0
        self.skipped = 0

    def _index_course(self, course_id: int) -> None:
        """Charge et indexe une fois les participations de la course (une requête)."""
        if course_id in self._by_bib:
            return
        rows = participation_repository.list_for_course(self.db, course_id)
        by_bib: dict[str, Participation] = {}
        without: dict[int, list[Participation]] = {}
        for row in rows:
            if row.bib_number:
                by_bib[row.bib_number] = row
            else:
                without.setdefault(row.athlete_id, []).append(row)
        self._by_bib[course_id] = by_bib
        self._added_bibs[course_id] = set()
        self._without_bib[course_id] = without
        self._credits[course_id] = {aid: len(rs) for aid, rs in without.items()}
        self._updated_single[course_id] = set()

    def _upsert(self, existing: "Participation", scraped: ScrapedResult) -> None:
        """Fusionne prudemment une ligne appariée. Compte `updated` ou `skipped`."""
        fields = mapping.participation_fields(
            scraped, athlete_id=existing.athlete_id, course_id=existing.course_id
        )
        changes = _merge_fields(existing, fields)
        status = _resolve_status(existing, scraped, changes)
        if status != existing.status:
            changes["status"] = status
        if changes:
            participation_repository.update(self.db, existing, **changes)
            self.updated += 1
        else:
            self.skipped += 1

    def add(self, scraped: ScrapedResult) -> None:
        course = mapping.get_or_create_course(self.db, scraped, self.event_url)
        self._courses[course.id] = course
        self._index_course(course.id)
        bib = scraped.bib_number or None

        if bib is not None:
            added = self._added_bibs[course.id]
            if bib in added:
                # La source se contredit dans ce scrape : deux lignes, même
                # dossard. La 2e est perdue — anomalie de fiabilité.
                self.skipped += 1
                self._duplicate_bibs[course.id] = self._duplicate_bibs.get(course.id, 0) + 1
                return
            existing = self._by_bib[course.id].get(bib)
            if existing is not None:
                added.add(bib)
                self._upsert(existing, scraped)
                return
            # Dossard neuf : on tombe sur la création commune plus bas.

        athlete = mapping.get_or_create_athlete(self.db, scraped)

        if bib is None:
            existing = self._match_without_bib(course.id, athlete.id)
            if existing is not None:
                self._upsert(existing, scraped)
                return
            if self._credits[course.id].get(athlete.id, 0) > 0:
                self._credits[course.id][athlete.id] -= 1
                self.skipped += 1
                return

        created = participation_repository.create(
            self.db,
            **mapping.participation_fields(
                scraped, athlete_id=athlete.id, course_id=course.id
            ),
        )
        if bib is not None:
            self._added_bibs[course.id].add(bib)
            self._by_bib[course.id][bib] = created
        self.imported += 1

    def _match_without_bib(self, course_id: int, athlete_id: int) -> "Participation | None":
        """Ligne sans dossard à mettre à jour : seulement si l'athlète n'a qu'**une**
        participation sur la course, et pas déjà mise à jour dans ce scrape.

        Deux occurrences ou plus : on ne devine pas quelle ligne source correspond
        à quelle ligne en base, on conserve le skip multiset (cf. `add`).
        """
        rows = self._without_bib[course_id].get(athlete_id, [])
        if len(rows) != 1 or athlete_id in self._updated_single[course_id]:
            return None
        self._updated_single[course_id].add(athlete_id)
        self._credits[course_id][athlete_id] -= 1
        return rows[0]

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


def import_event(db: Session, url: str, settings: Settings, force: bool = False) -> dict:
    """Import complet (bloquant). Renvoie {imported, updated, skipped, [cached]}.

    force=True saute le cache TTL (`_cached_result`) → le scraping a toujours lieu.
    """
    url = _validate_url(url)

    if not force:
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

    return {
        "imported": persister.imported,
        "updated": persister.updated,
        "skipped": persister.skipped,
    }


def iter_import_event(
    db: Session, url: str, settings: Settings, force: bool = False
) -> Iterator[dict]:
    """
    Générateur de progression pour le SSE. Émet des dicts de phase :
      {phase: scraping} → {phase: saving, progress, total, imported, skipped}
      → {phase: done, …}   (ou {phase: error, message})

    force=True saute le cache TTL (`_cached_result`).
    """
    try:
        url = _validate_url(url)
    except InvalidUrlError as exc:
        yield {"phase": "error", "message": exc.message}
        return

    if not force:
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
