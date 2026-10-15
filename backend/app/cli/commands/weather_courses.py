"""Commande `weather-courses` : météo du jour de course, Open-Meteo (#1370).

Seul point d'écriture des colonnes `weather_*` de `Course`, sur le patron de
`geocode-courses`. Zéro logique métier ici : options Typer, câblage, affichage.
"""
import typer

from app.cli.reports import emit_outcome, render_weather_report
from app.core.database import session_scope
from app.services.weather_service import run_weather_courses


def _progress(enabled: bool):
    if not enabled:
        return None

    def _on_item(index: int, total: int, name: str, weather) -> None:
        verdict = f"{weather.temperature_c:.1f} °C" if weather is not None else "échec (météo indisponible)"
        typer.echo(f"[{index + 1}/{total}] {name} → {verdict}", err=True)

    return _on_item


def weather_courses(
    limit: int | None = typer.Option(
        None, "--limit", help="Borne le nombre d'épreuves traitées."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Liste les épreuves ciblées sans appeler Open-Meteo ni rien persister.",
    ),
    json_output: bool = typer.Option(
        False, "--json",
        help="stdout ne contient que le JSON ; le rapport texte passe sur stderr.",
    ),
    no_progress: bool = typer.Option(
        False, "--no-progress", help="Aucun affichage de progression."
    ),
) -> None:
    """Pose la météo du jour de course des épreuves géocodées (Open-Meteo, archive).

    Cible les épreuves géocodées, datées d'au moins 5 jours, sans météo. Idempotente
    et relançable : une épreuve servie n'est plus ciblée, un échec est retenté au
    lancement suivant. À lancer après `geocode-courses`.
    """
    with session_scope() as db:
        outcome = run_weather_courses(
            db,
            limit=limit,
            dry_run=dry_run,
            on_item=_progress(not no_progress and not dry_run),
        )

    emit_outcome(
        outcome,
        render_weather_report(outcome, dry_run=dry_run),
        json_output=json_output,
    )
