"""Commande `purge-retention` : tient les durées de conservation publiées (#1158). Zéro logique métier.

Lancée par le batch hebdomadaire (`.github/workflows/batch.yml`), après la reprise.
"""
from dataclasses import asdict

import typer

from app.cli.reports import emit_report, render_retention_report
from app.core.database import session_scope
from app.core.time import utcnow
from app.services.retention_service import purge_expired


def purge_retention(
    dry_run: bool = typer.Option(False, "--dry-run", help="Compte ce qui serait supprimé, sans rien supprimer."),
    json_output: bool = typer.Option(
        False, "--json",
        help="stdout ne contient que le JSON ; le rapport texte passe sur stderr.",
    ),
) -> None:
    """Supprime les signalements et le journal d'administration de plus de 12 mois,
    les profils jeunes dont l'adhésion a pris fin depuis plus d'une saison, et
    réduit les licenciés du club des saisons échues (fin de saison plus une saison)."""
    with session_scope() as db:
        outcome = purge_expired(db, now=utcnow(), dry_run=dry_run)

    emit_report(render_retention_report(outcome), asdict(outcome), json_output=json_output)
