"""Commande `requalify-challenges` : reprise ponctuelle de #1008. Zéro logique métier.

Sans `--yes`, elle liste les épreuves qui sont des classements Challenge ; avec,
elle les convertit et les supprime par le geste d'administration (journalisé au
nom de `--by-email`).
"""
import typer

from app.cli.reports import emit_report, render_challenge_requalification_report
from app.core.database import session_scope
from app.repositories import user_repository
from app.services import challenge_requalification

#: Convention Click / Typer, comme `grant-role` : `2` = erreur d'usage.
USAGE = 2


def requalify_challenges(
    yes: bool = typer.Option(False, "--yes", help="Convertit vraiment (sinon : liste seulement)."),
    by_email: str | None = typer.Option(
        None, "--by-email", help="Compte au nom duquel le journal consigne la suppression."
    ),
    json_output: bool = typer.Option(
        False, "--json",
        help="stdout ne contient que le JSON ; le rapport texte passe sur stderr.",
    ),
) -> None:
    """Liste, ou convertit avec `--yes`, les épreuves qui sont des classements Challenge."""
    with session_scope() as db:
        if not yes:
            found = challenge_requalification.requalify(db, user_id=None)
        else:
            comptes = user_repository.find_by_email(db, by_email) if by_email else []
            if not comptes:
                typer.echo("--yes exige --by-email, l'adresse d'un compte existant.", err=True)
                raise typer.Exit(USAGE)
            found = challenge_requalification.requalify(db, user_id=comptes[0].id)

    rows = [
        {"course_id": r.course_id, "name": r.name, "linked_course_ids": r.linked_course_ids,
         "rows": r.rows}
        for r in found
    ]
    emit_report(
        render_challenge_requalification_report(rows, converted=yes),
        {"converted": yes, "challenges": rows},
        json_output=json_output,
    )
