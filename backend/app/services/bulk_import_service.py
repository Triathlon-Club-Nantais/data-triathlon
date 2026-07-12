"""Import de masse depuis le Google Sheet des adhérents.

Sélectionne les liens supportés de la source, puis délègue la boucle à
`batch.run_batch`. Les liens non supportés vont au rapport, jamais aux erreurs.
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.scrapers import registry
from app.services import sheet_source
from app.services.batch import BatchItem, est_echec_total, run_batch
from app.services.progress import ProgressReporter


@dataclass
class SheetOutcome:
    """Bilan d'un import-sheet."""
    imported: int = 0
    skipped: int = 0
    errors: int = 0
    rows_without_link: int = 0
    unique_supported: int = 0
    ignored_by_host: dict[str, int] = field(default_factory=dict)
    interrupted: bool = False

    @property
    def echec_total(self) -> bool:
        """Toutes les épreuves ciblées ont échoué (cf. `batch.est_echec_total`).

        `unique_supported` est le nombre d'épreuves **réellement soumises au
        batch** (liens supportés, dédoublonnés, après `--limit`) : c'est bien à
        lui qu'`errors` se compare. Les liens non supportés (`ignored_by_host`)
        n'ont jamais été tentés, ils ne comptent donc ni en succès ni en échec.

        Propriété (et non champ) : `asdict()` ne sérialise que les champs, la
        charge utile `--json` reste inchangée.
        """
        return est_echec_total(epreuves=self.unique_supported, errors=self.errors)


def run_import_sheet(
    db: Session,
    csv_text: str,
    settings: Settings,
    *,
    dry_run: bool = False,
    limit: int | None = None,
    only_provider: str | None = None,
    delay: float = 1.0,
    reporter: ProgressReporter | None = None,
) -> SheetOutcome:
    """Détecte, dédoublonne et importe les liens supportés du CSV du Sheet.

    En dry-run : ne scrape rien, ne persiste rien, ne temporise pas, ne rapporte
    aucune progression.
    """
    links, rows_without_link = sheet_source.parse_sheet_csv(csv_text)
    unique = sheet_source.dedupe_links(links)

    supported: list[str] = []
    ignored_by_host: dict[str, int] = {}
    for url in unique:
        if sheet_source.is_supported(url):
            if only_provider and registry.detect_provider(url) != only_provider:
                continue
            supported.append(url)
        else:
            host = sheet_source.host_of(url)
            ignored_by_host[host] = ignored_by_host.get(host, 0) + 1

    if limit is not None:
        supported = supported[:limit]

    outcome = SheetOutcome(
        rows_without_link=rows_without_link,
        unique_supported=len(supported),
        ignored_by_host=ignored_by_host,
    )
    if dry_run:
        return outcome

    # Le nom de la course n'est connu qu'après le scrape : on libelle par l'URL.
    items = [
        BatchItem(url=url, label=f"{registry.detect_provider(url)} · {url}")
        for url in supported
    ]
    totals = run_batch(
        db, items, settings, force=False, delay=delay, reporter=reporter
    )

    outcome.imported = totals.imported
    outcome.skipped = totals.skipped
    outcome.errors = totals.errors
    outcome.interrupted = totals.interrupted
    return outcome
