"""
Outillage CLI (Typer) : import de masse depuis le Google Sheet & rescrape DB.

CLI mince par-dessus les services : aucune logique de scraping ni d'accès DB
direct. Invocable depuis backend/ :
    python -m app.cli import-sheet --dry-run
    python -m app.cli rescrape-db --dry-run
"""
import json
import logging
import time
from dataclasses import asdict, dataclass, field

import typer

from app.core.config import get_settings
from app.core.database import session_scope
from app.repositories import course_repository
from app.scrapers import registry
from app.services import import_service
from app.services.sheet_source import (  # noqa: F401 — ré-export transitoire (Task 7)
    DEFAULT_SHEET_URL,
    dedupe_links,
    download_csv,
    host_of,
    is_supported,
    normalize_url,
    parse_sheet_csv,
)

logger = logging.getLogger(__name__)

app = typer.Typer(help="Outillage d'import de masse et de rescrape.")


@dataclass
class SheetOutcome:
    """Bilan d'un import-sheet."""
    imported: int = 0
    skipped: int = 0
    errors: int = 0
    rows_without_link: int = 0
    unique_supported: int = 0
    ignored_by_host: dict[str, int] = field(default_factory=dict)


def run_import_sheet(
    db,
    csv_text: str,
    settings,
    *,
    dry_run: bool = False,
    limit: int | None = None,
    only_provider: str | None = None,
    delay: float = 1.0,
) -> SheetOutcome:
    """Détecte, dédoublonne et importe les liens supportés du CSV du Sheet.

    En dry-run : ne scrape rien, ne persiste rien, ne temporise pas.
    Les liens non supportés vont au rapport (ignored_by_host) ; jamais une erreur.
    """
    links, rows_without_link = parse_sheet_csv(csv_text)
    unique = dedupe_links(links)

    supported: list[str] = []
    ignored_by_host: dict[str, int] = {}
    for url in unique:
        if is_supported(url):
            if only_provider and registry.detect_provider(url) != only_provider:
                continue
            supported.append(url)
        else:
            host = host_of(url)
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

    for i, url in enumerate(supported):
        try:
            res = import_service.import_event(db, url, settings, force=False)
            outcome.imported += res.get("imported", 0)
            outcome.skipped += res.get("skipped", 0)
        except Exception as exc:
            outcome.errors += 1
            logger.warning("Échec import %s : %s", url, exc)
        if delay and i < len(supported) - 1:
            time.sleep(delay)

    return outcome


def render_sheet_report(outcome: SheetOutcome, *, dry_run: bool) -> str:
    """Rapport texte lisible : compteurs + table des ignorés groupés par host."""
    lignes = []
    titre = "IMPORT SHEET (dry-run)" if dry_run else "IMPORT SHEET"
    lignes.append(f"=== {titre} ===")
    lignes.append(f"Liens supportés uniques : {outcome.unique_supported}")
    lignes.append(f"Lignes sans lien        : {outcome.rows_without_link}")
    if not dry_run:
        lignes.append(f"Importées : {outcome.imported}")
        lignes.append(f"Ignorées  : {outcome.skipped}")
        lignes.append(f"En erreur : {outcome.errors}")
    if outcome.ignored_by_host:
        lignes.append("Liens non supportés (suivis dans #33) :")
        for host, count in sorted(outcome.ignored_by_host.items()):
            lignes.append(f"  - {host} : {count}")
    return "\n".join(lignes)


@app.command("import-sheet")
def import_sheet(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Détecte et dédoublonne sans scraper ni persister."
    ),
    limit: int | None = typer.Option(None, "--limit", help="Borne le nombre d'épreuves."),
    only_provider: str | None = typer.Option(
        None, "--only-provider", help="Restreint à un provider (ex. klikego)."
    ),
    sheet_url: str = typer.Option(
        DEFAULT_SHEET_URL, "--sheet-url", envvar="IMPORT_SHEET_URL",
        help="Override la source CSV.",
    ),
    delay: float = typer.Option(
        1.0, "--delay", help="Pause de politesse entre scrapes réels (s)."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Rapport machine-lisible en plus du texte."
    ),
) -> None:
    """Amorce la base depuis le Google Sheet des adhérents."""
    settings = get_settings()
    csv_text = download_csv(sheet_url)
    with session_scope() as db:
        outcome = run_import_sheet(
            db, csv_text, settings,
            dry_run=dry_run, limit=limit, only_provider=only_provider, delay=delay,
        )
    typer.echo(render_sheet_report(outcome, dry_run=dry_run))
    if json_output:
        typer.echo(json.dumps(asdict(outcome), ensure_ascii=False))


@dataclass
class RescrapeOutcome:
    """Bilan d'un rescrape-db."""
    total: int = 0
    imported: int = 0
    skipped: int = 0
    errors: int = 0
    dry_run_urls: list[str] = field(default_factory=list)


def run_rescrape_db(
    db,
    settings,
    *,
    dry_run: bool = False,
    older_than: int | None = None,
    provider: str | None = None,
    limit: int | None = None,
    delay: float = 1.0,
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

    outcome = RescrapeOutcome(
        total=len(courses),
        dry_run_urls=[c.source_url for c in courses],
    )
    if dry_run:
        return outcome

    for i, course in enumerate(courses):
        try:
            res = import_service.import_event(db, course.source_url, settings, force=True)
            outcome.imported += res.get("imported", 0)
            outcome.skipped += res.get("skipped", 0)
        except Exception as exc:
            outcome.errors += 1
            logger.warning("Échec rescrape %s : %s", course.source_url, exc)
        if delay and i < len(courses) - 1:
            time.sleep(delay)

    return outcome


def render_rescrape_report(outcome: RescrapeOutcome, *, dry_run: bool) -> str:
    """Rapport texte lisible pour rescrape-db."""
    lignes = []
    titre = "RESCRAPE DB (dry-run)" if dry_run else "RESCRAPE DB"
    lignes.append(f"=== {titre} ===")
    lignes.append(f"Courses ciblées : {outcome.total}")
    if dry_run:
        for url in outcome.dry_run_urls:
            lignes.append(f"  - {url}")
    else:
        lignes.append(f"Importées : {outcome.imported}")
        lignes.append(f"Ignorées  : {outcome.skipped}")
        lignes.append(f"En erreur : {outcome.errors}")
    return "\n".join(lignes)


@app.command("rescrape-db")
def rescrape_db(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Liste les courses sans scraper ni persister."
    ),
    older_than: int | None = typer.Option(
        None, "--older-than", help="Ne re-scrape que les courses plus vieilles que N jours."
    ),
    provider: str | None = typer.Option(
        None, "--provider", help="Restreint à un provider."
    ),
    limit: int | None = typer.Option(None, "--limit", help="Borne le nombre de courses."),
    delay: float = typer.Option(
        1.0, "--delay", help="Pause de politesse entre scrapes (s)."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Rapport machine-lisible en plus du texte."
    ),
) -> None:
    """Re-scrape tous les events en DB (force=True, bypass du cache TTL)."""
    settings = get_settings()
    with session_scope() as db:
        outcome = run_rescrape_db(
            db, settings,
            dry_run=dry_run, older_than=older_than, provider=provider,
            limit=limit, delay=delay,
        )
    typer.echo(render_rescrape_report(outcome, dry_run=dry_run))
    if json_output:
        typer.echo(json.dumps(asdict(outcome), ensure_ascii=False))


if __name__ == "__main__":
    app()
