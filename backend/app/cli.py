"""
Outillage CLI (Typer) : import de masse depuis le Google Sheet & rescrape DB.

CLI mince par-dessus les services : aucune logique de scraping ni d'accès DB
direct. Invocable depuis backend/ :
    python -m app.cli import-sheet --dry-run
    python -m app.cli rescrape-db --dry-run
"""
import json
from dataclasses import asdict

import typer

from app.core.config import get_settings
from app.core.database import session_scope
from app.services.bulk_import_service import (  # noqa: F401 — ré-export transitoire (Task 7)
    SheetOutcome,
    run_import_sheet,
)
from app.services.rescrape_service import (  # noqa: F401 — ré-export transitoire (Task 7)
    RescrapeOutcome,
    run_rescrape_db,
)
from app.services.sheet_source import (  # noqa: F401 — ré-export transitoire (Task 7)
    DEFAULT_SHEET_URL,
    dedupe_links,
    download_csv,
    host_of,
    is_supported,
    normalize_url,
    parse_sheet_csv,
)

app = typer.Typer(help="Outillage d'import de masse et de rescrape.")


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
