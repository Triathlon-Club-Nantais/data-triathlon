"""Boucle de batch commune à l'import de masse et au rescrape.

Consomme `import_service.iter_import_event()` — le même générateur de phases que
le SSE du frontend — et relaie la progression à un `ProgressReporter`. Une
épreuve en échec n'interrompt pas le batch ; un Ctrl-C l'arrête proprement en
conservant le travail déjà persisté (chaque épreuve est commitée séparément).
"""
import logging
import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services import import_service
from app.services.progress import NullReporter, ProgressReporter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BatchItem:
    """Une épreuve à traiter : l'URL à scraper, et son libellé d'affichage."""
    url: str
    label: str


@dataclass
class BatchTotals:
    """Compteurs cumulés d'un batch. `interrupted` = arrêté par Ctrl-C."""
    imported: int = 0
    skipped: int = 0
    errors: int = 0
    interrupted: bool = False


def _import_one(
    db: Session,
    url: str,
    settings: Settings,
    *,
    force: bool,
    reporter: ProgressReporter,
) -> tuple[int, int, str | None]:
    """Consomme les phases d'une épreuve. Renvoie (imported, skipped, error).

    `iter_import_event` *yield* une phase `error` au lieu de lever : c'est cette
    phase qui porte l'échec, pas une exception.
    """
    imported = skipped = 0
    error: str | None = None

    for phase in import_service.iter_import_event(db, url, settings, force=force):
        nom = phase.get("phase")
        if nom == "saving":
            reporter.item_progress(phase.get("progress", 0), phase.get("total", 0))
        elif nom == "done":
            imported = phase.get("imported", 0)
            skipped = phase.get("skipped", 0)
        elif nom == "error":
            error = phase.get("message", "erreur inconnue")

    return imported, skipped, error


def run_batch(
    db: Session,
    items: list[BatchItem],
    settings: Settings,
    *,
    force: bool,
    delay: float = 1.0,
    reporter: ProgressReporter | None = None,
) -> BatchTotals:
    """Importe chaque épreuve en séquence, en rapportant la progression.

    `delay` est une pause de politesse entre deux scrapes (pas après le dernier).
    """
    reporter = reporter or NullReporter()
    totals = BatchTotals()

    reporter.batch_start(len(items))
    try:
        for i, item in enumerate(items):
            reporter.item_start(i, item.label)
            try:
                imported, skipped, error = _import_one(
                    db, item.url, settings, force=force, reporter=reporter
                )
            except Exception as exc:  # filet : un bug ne doit pas tuer le batch
                logger.warning("Échec import %s : %s", item.url, exc)
                imported = skipped = 0
                error = str(exc)
                try:
                    # invariant : la Session doit être saine pour l'épreuve suivante
                    db.rollback()
                except Exception:
                    logger.warning("Rollback de rattrapage impossible — Session irrécupérable")

            if error:
                totals.errors += 1
            else:
                totals.imported += imported
                totals.skipped += skipped
            reporter.item_done(imported, skipped, error)

            if delay and i < len(items) - 1:
                time.sleep(delay)
    except KeyboardInterrupt:
        # Ctrl-C : on ne perd pas le bilan de ce qui est déjà en base.
        totals.interrupted = True
        logger.warning("Interruption clavier — arrêt du batch")
    finally:
        reporter.batch_end()

    return totals
