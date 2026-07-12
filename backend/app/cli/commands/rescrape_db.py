"""Commande `rescrape-db` : options Typer, câblage, affichage. Zéro logique métier."""
import typer

from app.cli.progress import select_reporter
from app.cli.reports import emit_outcome, render_rescrape_report
from app.cli.validators import valider_provider
from app.core.config import get_settings
from app.core.database import session_scope
from app.services import rescrape_service


def rescrape_db(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Liste les courses sans scraper ni persister."
    ),
    older_than: int | None = typer.Option(
        None, "--older-than", help="Ne re-scrape que les courses plus vieilles que N jours."
    ),
    provider: str | None = typer.Option(
        None, "--provider", callback=valider_provider,
        help="Restreint à un provider (défaut : tous).",
    ),
    limit: int | None = typer.Option(None, "--limit", help="Borne le nombre de courses."),
    delay: float = typer.Option(
        1.0, "--delay", help="Pause de politesse entre scrapes (s)."
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
    """Re-scrape tous les events en DB (force=True, bypass du cache TTL)."""
    settings = get_settings()
    reporter = select_reporter(no_progress=no_progress or dry_run, plain=plain)

    with session_scope() as db:
        outcome = rescrape_service.run_rescrape_db(
            db, settings,
            dry_run=dry_run, older_than=older_than, provider=provider,
            limit=limit, delay=delay, reporter=reporter,
        )

    emit_outcome(
        outcome,
        render_rescrape_report(outcome, dry_run=dry_run),
        json_output=json_output,
    )
