"""Re-scrape en masse des épreuves déjà en base (force=True, bypass du cache TTL).

Unité de travail : l'**épreuve**, c'est-à-dire une `source_url` unique — et non
la course. La table `course` en porte N par épreuve (heats Breizh Chrono,
variantes individuel/relais) ; un seul scrape d'épreuve les réimporte toutes.
Compteurs et `--limit` raisonnent donc en épreuves (cf. `_dedupe_par_url`).
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.course import Course
from app.repositories import course_repository
from app.services import sheet_source
from app.services.batch import BatchFailure, BatchItem, est_echec_total, run_batch
from app.services.progress import ProgressReporter


def _dedupe_par_url(courses: list[Course]) -> list[Course]:
    """Une épreuve par `source_url`, en conservant la première course rencontrée.

    Une même URL porte souvent **plusieurs** courses : heats auto-découverts de
    Breizh Chrono, variantes individuel/relais de wiclax/timepulse… Or un seul
    scrape d'épreuve les réimporte toutes. Sans dédup, on scraperait la même URL
    N fois (base de dev : 53 courses pour 12 URLs, dont une portée par 13 heats)
    — requêtes inutiles vers les sites tiers, `skipped` et `errors` gonflés d'un
    facteur N, et `--limit` qui ne bornerait plus des épreuves mais des courses.

    Clé de dédup : `sheet_source.normalize_url`, par symétrie avec `dedupe_links`
    de l'import de masse. Ces URLs viennent de la DB (donc des scrapers, pas
    d'une saisie manuelle) : la normalisation est ici quasi neutre, elle ne fait
    que rattraper les écarts de casse d'hôte ou de slash final entre deux
    providers. La course retenue fournit le libellé `provider · name`.
    """
    uniques: dict[str, Course] = {}
    for course in courses:
        uniques.setdefault(sheet_source.normalize_url(course.source_url), course)
    return list(uniques.values())


def _items_depuis_urls(db: Session, urls: list[str]) -> list[BatchItem]:
    """Épreuves ciblées **explicitement** : la base ne sert plus qu'à libeller.

    Une URL inconnue en base est le cas **nominal** du rejeu d'un échec
    d'import : l'épreuve fautive n'a rien persisté, elle est absente de la table
    `course`. La sélectionner via `iter_all` porterait sur zéro épreuve et
    sortirait en code 0 — un silence trompeur. On soumet donc les URLs telles
    quelles au batch, connues ou non.

    Le libellé est purement cosmétique (ligne de progression) : quand la course
    est inconnue, il retombe sur l'URL, sans avertissement ni dégradation.
    """
    items: list[BatchItem] = []
    for url in sheet_source.dedupe_links(urls):
        course = course_repository.get_latest_by_source_url(db, url)
        label = f"{course.provider} · {course.name}" if course else url
        items.append(BatchItem(url=url, label=label))
    return items


@dataclass
class RescrapeOutcome:
    """Bilan d'un rescrape-db. `total` = nombre d'**épreuves** (URLs uniques).

    `total`, `processed` et `errors` comptent des **épreuves** ; `imported` et
    `skipped`, des **participants**. Le rapport texte nomme ces unités.
    """
    total: int = 0
    imported: int = 0
    skipped: int = 0
    errors: int = 0
    #: Épreuves réellement traitées — égal à `total`, sauf sous Ctrl-C.
    processed: int = 0
    dry_run_urls: list[str] = field(default_factory=list)
    interrupted: bool = False
    #: Épreuves fautives (URL + cause). Borné aux seuls échecs : léger,
    #: contrairement à la liste de toutes les épreuves. `asdict()` l'embarque
    #: dans `--json`, ce qui referme la boucle de rejeu sans fichier d'état.
    failures: list[BatchFailure] = field(default_factory=list)

    @property
    def echec_total(self) -> bool:
        """Toutes les épreuves ciblées ont échoué (cf. `batch.est_echec_total`).

        `total` est le nombre d'épreuves soumises au batch (URLs uniques, après
        `--limit`) : c'est à lui qu'`errors` se compare.

        Propriété (et non champ) : `asdict()` ne sérialise que les champs, la
        charge utile `--json` reste inchangée.
        """
        return est_echec_total(epreuves=self.total, errors=self.errors)


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
    urls: list[str] | None = None,
) -> RescrapeOutcome:
    """Re-scrape toutes les épreuves en DB avec force=True (bypass du cache TTL).

    Ne retient que les courses ayant une source_url (clé de re-scraping), puis
    dédoublonne par URL : on raisonne en **épreuves à scraper**, pas en courses.
    `limit` borne donc les épreuves, et s'applique **après** la dédup.
    En dry-run : liste les URLs sans scraper ni persister.

    Deux modes de sélection, un seul batch en aval. `urls=None` : les épreuves
    viennent de la base (`provider`, `older_than`, dédup par URL). `urls`
    fourni : la base **n'est pas interrogée pour sélectionner**, chaque URL
    devient une épreuve — c'est ce qui permet de rejouer un échec d'import, dont
    l'épreuve n'existe pas en base. `limit` borne la liste finale dans les deux
    cas ; `force=True`, `delay`, dry-run et Ctrl-C sont inchangés.
    """
    if urls is not None:
        items = _items_depuis_urls(db, urls)
    else:
        courses = course_repository.iter_all(
            db, provider=provider, older_than_days=older_than
        )
        epreuves = _dedupe_par_url([c for c in courses if c.source_url])
        # Le nom de la course vient de la DB : on peut libeller proprement.
        items = [
            BatchItem(url=c.source_url, label=f"{c.provider} · {c.name}")
            for c in epreuves
        ]
    if limit is not None:
        items = items[:limit]

    outcome = RescrapeOutcome(total=len(items))
    if dry_run:
        # Charge utile réservée au dry-run : hors dry-run, embarquer l'URL de
        # chaque épreuve gonflerait la sortie --json de plusieurs dizaines de Ko.
        outcome.dry_run_urls = [item.url for item in items]
        return outcome

    totals = run_batch(db, items, settings, force=True, delay=delay, reporter=reporter)

    outcome.imported = totals.imported
    outcome.skipped = totals.skipped
    outcome.errors = totals.errors
    outcome.failures = totals.failures
    outcome.processed = totals.processed
    outcome.interrupted = totals.interrupted
    return outcome
