"""Boucle de batch commune à l'import de masse et au rescrape.

Consomme `import_service.iter_import_event()` — le même générateur de phases que
le SSE du frontend — et relaie la progression à un `ProgressReporter`. Une
épreuve en échec n'interrompt pas le batch ; un Ctrl-C l'arrête proprement en
conservant le travail déjà persisté (chaque épreuve est commitée séparément).
"""
import itertools
import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from functools import partial
from urllib.parse import urlparse

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.sql_observability import measure_queries
from app.scrapers.registry import detect_provider
from app.services import import_service
from app.services.import_service import PassiveSource, Reassignment
from app.services.progress import NullReporter, ProgressReporter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BatchItem:
    """Une épreuve à traiter : l'URL à scraper, et son libellé d'affichage."""
    url: str
    label: str


@dataclass(frozen=True)
class BatchFailure:
    """Une épreuve en échec, de quoi la diagnostiquer sans rejouer le batch.

    `url` pour la retrouver (ou la rescraper), `message` pour la cause — la phase
    `error` d'`iter_import_event`, ou l'exception rattrapée par le filet de
    `run_batch`. `label` reprend le libellé d'affichage (`provider · …`).
    """
    url: str
    label: str
    message: str


@dataclass
class BatchTotals:
    """Compteurs cumulés d'un batch. `interrupted` = arrêté par Ctrl-C.

    Deux unités cohabitent, et le bilan doit les nommer : `processed`/`errors`
    comptent des **épreuves**, `imported`/`updated`/`skipped` des **participants**.
    """
    imported: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    #: Épreuves allées au bout (succès **ou** échec). Sous Ctrl-C, celle qui a
    #: été coupée en plein vol n'est pas comptée : elle n'a pas été traitée.
    processed: int = 0
    interrupted: bool = False
    #: Détail des épreuves en échec (une entrée par `errors`), dans l'ordre du
    #: batch : le compteur `errors` dit combien, celui-ci dit lesquelles et pourquoi.
    failures: list[BatchFailure] = field(default_factory=list)
    #: Participations réconciliées (identité réassignée) sur l'ensemble du batch.
    reconciled: int = 0
    #: Détail des réassignations, cumulé dans l'ordre du batch (léger : ~1 par
    #: participation réconciliée, pas une ligne par participation traitée).
    reassignments: list[Reassignment] = field(default_factory=list)
    #: Les URLs enregistrées en sources passives, cumulées dans l'ordre du batch.
    #: Ni des erreurs ni des imports : une épreuve qui n'a fait *que* ça sort en
    #: succès, avec zéro participant touché (#283).
    passive_sources: list[PassiveSource] = field(default_factory=list)


#: Les compteurs que `BatchTotals` et les deux `*Outcome` portent à l'identique.
#: Ils restent **plats** sur l'Outcome : `asdict()` alimente la sortie `--json` de
#: la CLI, dont la forme est un contrat (le pipeline `import-sheet --json |
#: jq -r '.failures[].url' | rescrape-db --urls-from -`). Une imbrication
#: `totals: {…}` la casserait.
CHAMPS_COMMUNS = (
    "imported", "updated", "skipped", "errors", "processed", "interrupted", "failures",
    "passive_sources",
)


def copy_totals(outcome, totals: BatchTotals) -> None:
    """Reporte les compteurs communs du batch sur le bilan de la commande.

    `outcome` est un `SheetOutcome` ou un `RescrapeOutcome` — pas de `Protocol`
    à inventer pour deux dataclasses, `CHAMPS_COMMUNS` est le contrat, et
    `test_batch` épingle les deux.
    """
    for champ in CHAMPS_COMMUNS:
        setattr(outcome, champ, getattr(totals, champ))


@dataclass
class _ItemResult:
    """Ce qu'une épreuve rapporte au batch. `error` non nul = épreuve fautive."""
    imported: int = 0
    updated: int = 0
    skipped: int = 0
    error: str | None = None
    reconciled: int = 0
    reassignments: list[Reassignment] = field(default_factory=list)
    passive_sources: list[PassiveSource] = field(default_factory=list)


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


def _group_by_host(items: list[BatchItem]) -> list[tuple[str, list[BatchItem]]]:
    """Regroupe les épreuves par chronométreur, dans l'ordre de première rencontre.

    La clé est celle du registre des scrapers (`detect_provider`), pas le
    domaine réseau littéral de l'URL : un chronométreur qui publie sur
    plusieurs domaines (Wiclax, RaceResult) doit rester une unité de politesse
    unique — deux domaines du même provider ne doivent jamais tourner en
    parallèle l'un de l'autre (clarification de `spec.md`). Une URL non
    reconnue par le registre retombe sur son hôte réseau littéral, pour ne pas
    fusionner deux inconnues sans rapport sous une même clé vide.
    """
    groups: dict[str, list[BatchItem]] = {}
    for item in items:
        host_key = detect_provider(item.url) or (urlparse(item.url).hostname or "")
        groups.setdefault(host_key, []).append(item)
    return list(groups.items())


@dataclass(frozen=True)
class _ReporterPourGroupe:
    """Lie un `ProgressReporter` à un chronométreur : `_import_one` continue
    d'appeler `item_start`/`item_progress`/`item_done` sans connaître le
    regroupement — cet adaptateur ajoute `host` à chaque appel, seul endroit
    qui a besoin de le savoir.
    """
    reporter: ProgressReporter
    host: str

    def item_start(self, index: int, label: str) -> None:
        self.reporter.item_start(index, label, self.host)

    def item_progress(self, done: int, total: int) -> None:
        self.reporter.item_progress(done, total, self.host)

    def item_done(self, imported: int, skipped: int, error: str | None) -> None:
        self.reporter.item_done(imported, skipped, error, self.host)


def _import_one(
    db: Session,
    url: str,
    settings: Settings,
    *,
    force: bool,
    persist: bool,
    reporter: ProgressReporter,
    single_heat: bool = False,
) -> _ItemResult:
    """Consomme les phases d'une épreuve et en fait un `_ItemResult`.

    `iter_import_event` *yield* une phase `error` au lieu de lever : c'est cette
    phase qui porte l'échec, pas une exception. `persist=False` (dry-run) fait
    scraper l'épreuve sans rien écrire.
    """
    result = _ItemResult()

    for phase in import_service.iter_import_event(
        db, url, settings, force=force, persist=persist, single_heat=single_heat,
    ):
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
            result.imported = phase.get("imported", 0)
            result.updated = phase.get("updated", 0)
            result.skipped = phase.get("skipped", 0)
            result.reconciled = phase.get("reconciled", 0)
            result.reassignments = phase.get("reassignments", [])
            result.passive_sources = phase.get("passive_sources", [])
        elif nom == "error":
            result.error = phase.get("message", "erreur inconnue")

    return result


def run_batch(
    db: Session,
    items: list[BatchItem],
    settings: Settings,
    *,
    force: bool,
    persist: bool = True,
    delay: float = 1.0,
    reporter: ProgressReporter | None = None,
    single_heat: bool = False,
    max_concurrent_hosts: int = 4,
) -> BatchTotals:
    """Importe les épreuves en parallèle par chronométreur, en rapportant la progression.

    Les épreuves d'un même chronométreur (`_group_by_host`) restent traitées en
    séquence — `delay` est une pause de politesse entre deux scrapes du même
    chronométreur, pas après le dernier de son groupe. Des chronométreurs
    différents scrapent en même temps, bornés par `max_concurrent_hosts`.

    Chaque groupe ouvre sa propre `Session` (liée au même moteur que `db`, via
    `db.get_bind()`) : une `Session` SQLAlchemy n'est pas thread-safe, `db` sert
    donc uniquement au travail qui encadre le batch (l'appelant), jamais au
    scrape lui-même.
    """
    reporter = reporter or NullReporter()
    totals = BatchTotals()
    lock = threading.Lock()
    stop_event = threading.Event()
    compteur = itertools.count()
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db.get_bind())

    def _traiter_epreuve(group_db: Session, item: BatchItem, group_reporter: ProgressReporter) -> None:
        index = next(compteur)
        _notify(partial(group_reporter.item_start, index, item.label))
        with measure_queries(item.label):
            try:
                result = _import_one(
                    group_db, item.url, settings, force=force, persist=persist,
                    reporter=group_reporter, single_heat=single_heat,
                )
            except Exception as exc:  # filet : un bug ne doit pas tuer le batch
                logger.warning("Échec import %s : %s", item.url, exc)
                result = _ItemResult(error=str(exc) or exc.__class__.__name__)

        with lock:
            if result.error:
                totals.errors += 1
                totals.failures.append(
                    BatchFailure(url=item.url, label=item.label, message=result.error)
                )
            else:
                totals.imported += result.imported
                totals.updated += result.updated
                totals.skipped += result.skipped
                totals.reconciled += result.reconciled
                totals.reassignments.extend(result.reassignments)
                totals.passive_sources.extend(result.passive_sources)
            totals.processed += 1  # tentée et allée au bout, réussie ou non
        _notify(partial(group_reporter.item_done, result.imported, result.skipped, result.error))
        _liberer_session(group_db)

    def _traiter_groupe(host: str, host_items: list[BatchItem]) -> None:
        if stop_event.is_set():
            return
        group_db = session_factory()
        group_reporter = _ReporterPourGroupe(reporter, host)
        try:
            for position, item in enumerate(host_items):
                if stop_event.is_set():
                    return
                try:
                    _traiter_epreuve(group_db, item, group_reporter)
                except KeyboardInterrupt:
                    # Ctrl-C pendant cette épreuve : elle n'est pas comptée (comme
                    # aujourd'hui), et plus aucun groupe ne démarre d'épreuve neuve.
                    stop_event.set()
                    logger.warning("Interruption clavier — arrêt du batch")
                    _liberer_session(group_db)
                    return
                if delay and position < len(host_items) - 1 and not stop_event.is_set():
                    time.sleep(delay)
        finally:
            group_db.close()

    groupes = _group_by_host(items)

    _notify(partial(reporter.batch_start, len(items)))
    executor = ThreadPoolExecutor(max_workers=max(1, max_concurrent_hosts))
    try:
        futures = [executor.submit(_traiter_groupe, host, host_items) for host, host_items in groupes]
        try:
            for future in as_completed(futures):
                future.result()
            executor.shutdown(wait=True)
        except KeyboardInterrupt:
            # Ctrl-C reçu par le thread principal (cas réel : bloqué ici en
            # attente). Aucun groupe pas encore démarré ne doit démarrer ; ceux
            # déjà en cours vont à leur terme (on ne peut pas tuer un thread).
            stop_event.set()
            logger.warning("Interruption clavier — arrêt du batch")
            executor.shutdown(wait=True, cancel_futures=True)
    finally:
        if stop_event.is_set():
            totals.interrupted = True
        _notify(reporter.batch_end)

    return totals
