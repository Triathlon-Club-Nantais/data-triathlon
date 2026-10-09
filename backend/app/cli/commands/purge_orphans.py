"""Commande `purge-orphans` : supprime les athlètes sans résultat (#1271). Zéro logique métier.

Lancée par le passage hebdomadaire (`.github/workflows/batch.yml`), qui ne lance
plus `rescrape-db` : c'est en fin de reprise que ce balayage tournait jusque-là.
"""
import typer

from app.cli.reports import render_orphans_report
from app.core.database import session_scope
from app.repositories import athlete_repository


def purge_orphans() -> None:
    """Supprime les fiches d'athlète vidées par une réassignation de dossard,
    que rien d'autre ne référence (bénévolat, saison, compte lié)."""
    with session_scope() as db:
        removed = athlete_repository.delete_orphans(db)
        db.commit()

    typer.echo(render_orphans_report(removed))
