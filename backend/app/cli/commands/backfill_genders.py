"""Commande `backfill-genders` : rattrapage ponctuel de #1201. Zéro logique métier.

Sans `--yes`, elle chiffre seulement ; avec, elle écrit le sexe des fiches dont
tous les résultats le désignent.
"""
import typer

from app.cli.reports import emit_report, render_gender_backfill_report
from app.core.database import session_scope
from app.services import gender_backfill


def backfill_genders(
    yes: bool = typer.Option(False, "--yes", help="Écrit vraiment (sinon : simulation)."),
    json_output: bool = typer.Option(
        False, "--json",
        help="stdout ne contient que le JSON ; le rapport texte passe sur stderr.",
    ),
) -> None:
    """Remplit le sexe vide des fiches depuis la catégorie ou la ligne source de leurs résultats."""
    with session_scope() as db:
        fills = gender_backfill.apply(db) if yes else gender_backfill.plan(db)

    rows = [{"athlete_id": fill.athlete_id, "gender": fill.gender} for fill in fills]
    emit_report(
        render_gender_backfill_report(rows, applied=yes),
        {"applied": yes, "athletes": rows},
        json_output=json_output,
    )
