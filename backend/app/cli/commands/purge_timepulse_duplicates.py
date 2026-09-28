"""Commande `purge-timepulse-duplicates` : nettoyage ponctuel de #1004. Zéro logique métier.

À lancer après le premier `rescrape-db --provider timepulse` de chaque
environnement. Sans `--yes`, elle liste seulement ; avec, elle supprime par le même
geste que l'écran d'administration (`admin_actions.delete_course`, journalisé au
nom de `--by-email`).
"""
import typer

from app.cli.reports import emit_report, render_timepulse_duplicates_report
from app.core.database import session_scope
from app.repositories import user_repository
from app.services import timepulse_cleanup

#: Convention Click / Typer, comme `grant-role` : `2` = erreur d'usage.
USAGE = 2


def purge_timepulse_duplicates(
    yes: bool = typer.Option(False, "--yes", help="Supprime vraiment (sinon : liste seulement)."),
    by_email: str | None = typer.Option(
        None, "--by-email", help="Compte au nom duquel le journal consigne la suppression."
    ),
    json_output: bool = typer.Option(
        False, "--json",
        help="stdout ne contient que le JSON ; le rapport texte passe sur stderr.",
    ),
) -> None:
    """Liste, ou supprime avec `--yes`, les épreuves timepulse d'avant #674 que
    leurs parcours qualifiés couvrent entièrement, au dossard près."""
    with session_scope() as db:
        if not yes:
            courses = timepulse_cleanup.find_superseded(db)
        else:
            comptes = user_repository.find_by_email(db, by_email) if by_email else []
            if not comptes:
                typer.echo("--yes exige --by-email, l'adresse d'un compte existant.", err=True)
                raise typer.Exit(USAGE)
            courses = timepulse_cleanup.purge_superseded(db, user_id=comptes[0].id)

    rows = [
        {"course_id": c.course_id, "name": c.name, "source_url": c.source_url,
         "covered_by": c.covered_by}
        for c in courses
    ]
    emit_report(
        render_timepulse_duplicates_report(rows, deleted=yes),
        {"deleted": yes, "courses": rows},
        json_output=json_output,
    )
