"""Commande `purge-orphans` : supprime les athlètes sans résultat (#1271). Zéro logique métier.

Lancée par le seul passage planifié (`.github/workflows/batch.yml`), qui ne lance
plus `rescrape-db` : une reprise manuelle balaie déjà en fin de batch.
"""
import logging

import typer
from sqlalchemy.exc import IntegrityError

from app.cli.reports import render_orphans_report
from app.core.database import session_scope
from app.repositories import athlete_repository

logger = logging.getLogger(__name__)


def purge_orphans() -> None:
    """Supprime les fiches d'athlète vidées par une réassignation de dossard,
    que rien d'autre ne référence (bénévolat, saison, compte lié)."""
    with session_scope() as db:
        try:
            removed = athlete_repository.delete_orphans(db)
            db.commit()
        except IntegrityError:
            # Import concurrent qui rattache un orphelin (#1100) : pas une panne.
            db.rollback()
            logger.warning("Orphan purge failed, left to the next run", exc_info=True)
            typer.echo("Conflit avec un import en cours : balayage reporté au prochain passage.")
            return

    typer.echo(render_orphans_report(removed))
