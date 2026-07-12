"""Commande `import-sheet` : options Typer, câblage, affichage. Zéro logique métier."""
import typer

from app.cli.progress import select_reporter
from app.cli.reports import emit_outcome, render_sheet_report
from app.core.config import get_settings
from app.core.database import session_scope
from app.services import bulk_import_service, sheet_source


def import_sheet(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Détecte et dédoublonne sans scraper ni persister."
    ),
    limit: int | None = typer.Option(None, "--limit", help="Borne le nombre d'épreuves."),
    only_provider: str | None = typer.Option(
        None, "--only-provider", help="Restreint à un provider (ex. klikego)."
    ),
    sheet_url: str = typer.Option(
        sheet_source.DEFAULT_SHEET_URL, "--sheet-url", envvar="IMPORT_SHEET_URL",
        help="Override la source CSV.",
    ),
    delay: float = typer.Option(
        1.0, "--delay", help="Pause de politesse entre scrapes réels (s)."
    ),
    json_output: bool = typer.Option(
        False, "--json",
        help="stdout ne contient que le JSON ; le rapport texte passe sur stderr.",
    ),
    no_progress: bool = typer.Option(
        False, "--no-progress", help="Aucun affichage de progression."
    ),
    plain: bool = typer.Option(
        False, "--plain", help="Progression ligne à ligne même dans un terminal."
    ),
) -> None:
    """Amorce la base depuis le Google Sheet des adhérents."""
    settings = get_settings()
    csv_text = sheet_source.download_csv(sheet_url)
    reporter = select_reporter(no_progress=no_progress or dry_run, plain=plain)

    with session_scope() as db:
        outcome = bulk_import_service.run_import_sheet(
            db, csv_text, settings,
            dry_run=dry_run, limit=limit, only_provider=only_provider,
            delay=delay, reporter=reporter,
        )

    emit_outcome(
        outcome,
        render_sheet_report(outcome, dry_run=dry_run),
        json_output=json_output,
    )
