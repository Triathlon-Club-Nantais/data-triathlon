"""Commande `sync-club-members` : relit les licenciés FFTri de la saison (#1202). Zéro logique métier.

Lancée par le batch hebdomadaire (`.github/workflows/batch.yml`), après la purge.
"""
from dataclasses import asdict

import typer

from app.cli.reports import emit_report, render_members_sync_report
from app.core.database import session_scope
from app.core.exceptions import DomainError
from app.services import club_members_service


def sync_club_members(
    json_output: bool = typer.Option(
        False, "--json",
        help="stdout ne contient que le JSON ; le rapport texte passe sur stderr.",
    ),
) -> None:
    """Remplace la liste des licenciés de la saison en cours par celle de la FFTri."""
    try:
        with session_scope() as db:
            report = club_members_service.sync_from_fftri(db, user_id=None)
            db.commit()
    except DomainError as error:
        typer.echo(error.message, err=True)
        raise typer.Exit(code=1) from error

    emit_report(render_members_sync_report(report), asdict(report), json_output=json_output)
