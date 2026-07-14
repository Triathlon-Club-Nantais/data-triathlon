"""Boucle de batch commune à l'import de masse et au rescrape.

Consomme `import_service.iter_import_event()` — le même générateur de phases que
le SSE du frontend — et relaie la progression à un `ProgressReporter`. Une
épreuve en échec n'interrompt pas le batch ; un Ctrl-C l'arrête proprement en
conservant le travail déjà persisté (chaque épreuve est commitée séparément).
"""
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

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
    """Compteurs cumulés d'un batch. `interrupted` = arrêté par Ctrl-C.

    Deux unités cohabitent, et le bilan doit les nommer : `processed`/`errors`
    comptent des **épreuves**, `imported`/`skipped` des **participants**.
    """
    imported: int = 0
    skipped: int = 0
    errors: int = 0
    #: Épreuves allées au bout (succès **ou** échec). Sous Ctrl-C, celle qui a
    #: été coupée en plein vol n'est pas comptée : elle n'a pas été traitée.
    processed: int = 0
    interrupted: bool = False


def est_echec_total(*, epreuves: int, errors: int) -> bool:
    """Vrai si **toutes** les épreuves ciblées ont échoué — et qu'il y en avait.

    Définition unique de l'« échec total », partagée par les deux bilans
    (`SheetOutcome`, `RescrapeOutcome`) : un cron dont les 53 épreuves échouent
    (site tiers down) doit sortir en code non nul, sinon il n'alerte jamais.

    On compare des **épreuves**, pas des participants : `errors` compte une unité
    par épreuve en échec, alors qu'`imported`/`skipped` comptent des
    participants. Une épreuve qui réussit sans rien importer de neuf (tous les
    participants déjà en base, ou épreuve vide) reste donc un **succès** — d'où
    la comparaison `errors` vs nombre d'épreuves plutôt qu'un test sur `imported`.

    Cas dégénérés couverts par `epreuves > 0` : batch de zéro épreuve (Sheet
    vide, `--limit 0`, filtre sans résultat) → pas un échec. Un dry-run ne
    scrape rien : ses `errors` restent à 0, il ne peut donc jamais être un échec.
    """
    return epreuves > 0 and errors >= epreuves


def _notify(action: Callable[[], None]) -> None:
    """Notifie le reporter sans jamais faire échouer le batch.

    L'affichage est accessoire, les données ne le sont pas : un
    `python -m app.cli rescrape-db 2>&1 | head -20` ferme le tube, le reporter
    lève `BrokenPipeError` — et sans ce filet, l'exception traverserait
    `run_batch`, faisant perdre le `BatchTotals` alors que N épreuves sont déjà
    commitées. L'opérateur recevrait une traceback à la place de son bilan.

    `KeyboardInterrupt` est une `BaseException` : elle n'est pas attrapée ici et
    continue de remonter (Ctrl-C doit rester possible pendant un affichage).
    """
    try:
        action()
    except Exception as exc:
        logger.warning("Reporter en échec (%s) — batch poursuivi", exc)


def _liberer_session(db: Session) -> None:
    """Referme la transaction laissée ouverte par l'épreuve qui vient d'être traitée.

    Deux raisons, une seule instruction :

    - **Transaction de lecture jamais refermée.** `import_service._cached_result`
      ouvre une transaction (SELECT du cache TTL) ; sur les retours « cached » et
      « error », personne ne commit ni ne rollback. Relancer `import-sheet` sur un
      Sheet déjà importé (300 liens tous frais) laissait une transaction Postgres
      ouverte tout le run — `idle in transaction` sur Supabase pendant plusieurs
      minutes.
    - **Session saine pour l'épreuve suivante.** Une exception brute (coupure DB)
      peut laisser la Session en `PendingRollbackError`, ce qui ferait échouer en
      cascade des épreuves sans rapport avec la panne.

    Rien n'est perdu : chaque épreuve est commitée par `import_service` lui-même,
    ce rollback ne porte donc que sur une transaction de lecture (ou sur du travail
    déjà annulé par le rollback interne de l'import).
    """
    try:
        db.rollback()
    except Exception:
        logger.warning("Rollback de rattrapage impossible — Session irrécupérable")


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
            _notify(
                partial(
                    reporter.item_progress,
                    phase.get("progress", 0),
                    phase.get("total", 0),
                )
            )
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

    _notify(partial(reporter.batch_start, len(items)))
    try:
        for i, item in enumerate(items):
            _notify(partial(reporter.item_start, i, item.label))
            try:
                imported, skipped, error = _import_one(
                    db, item.url, settings, force=force, reporter=reporter
                )
            except Exception as exc:  # filet : un bug ne doit pas tuer le batch
                logger.warning("Échec import %s : %s", item.url, exc)
                imported = skipped = 0
                error = str(exc)

            if error:
                totals.errors += 1
            else:
                totals.imported += imported
                totals.skipped += skipped
            totals.processed += 1  # tentée et allée au bout, réussie ou non
            _notify(partial(reporter.item_done, imported, skipped, error))
            _liberer_session(db)

            if delay and i < len(items) - 1:
                time.sleep(delay)
    except KeyboardInterrupt:
        # Ctrl-C : on ne perd pas le bilan de ce qui est déjà en base.
        totals.interrupted = True
        logger.warning("Interruption clavier — arrêt du batch")
        _liberer_session(db)  # le Ctrl-C a pu couper une épreuve en plein SELECT
    finally:
        _notify(reporter.batch_end)

    return totals
