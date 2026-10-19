"""Commande `import-member-emails` : importe l'export AssoConnect d'une saison (#1334). Zéro logique métier."""
from dataclasses import asdict
from pathlib import Path

import typer

from app.cli.reports import emit_report, render_member_emails_import_report
from app.core.database import session_scope
from app.core.exceptions import DomainError
from app.core.season import SEASON_MAX, SEASON_MIN
from app.services import member_emails_service


def import_member_emails(
    season: int = typer.Option(
        ..., "--season", min=SEASON_MIN, max=SEASON_MAX, help="Saison (année de début)."
    ),
    file: Path = typer.Option(
        ..., "--file", exists=True, dir_okay=False, readable=True, help="Export .csv ou .xlsx."
    ),
    json_output: bool = typer.Option(
        False, "--json",
        help="stdout ne contient que le JSON ; le rapport texte passe sur stderr.",
    ),
) -> None:
    """Remplace les adresses importées de la saison par celles du fichier ; les
    adresses ajoutées à la main restent."""
    try:
        with session_scope() as db:
            report = member_emails_service.import_file(
                db, season=season, content=file.read_bytes(), filename=file.name, user_id=None
            )
            db.commit()
    except DomainError as error:
        typer.echo(error.message, err=True)
        raise typer.Exit(code=1) from error

    emit_report(render_member_emails_import_report(report), asdict(report), json_output=json_output)
