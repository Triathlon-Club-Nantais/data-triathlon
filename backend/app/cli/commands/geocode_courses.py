"""Commande `geocode-courses` : persiste les coordonnées des épreuves (#579).

Sort Nominatim du chemin de requête : `GET /stats/events-geo` ne fait plus
qu'un `SELECT`, cette commande est désormais le **seul** point d'écriture de
`Course.latitude`/`longitude`/`geocoded_at`. Volontairement tenue à l'écart de
l'import (web comme CLI) : `import_event` sert aussi le flux SSE synchrone du
site public, et y ajouter jusqu'à 2,2 s par épreuve neuve aurait réintroduit,
en plus petit, exactement le défaut que cette issue corrige. Zéro logique
métier ici : options Typer, câblage, affichage.
"""
from datetime import timedelta

import typer

from app.cli.reports import emit_outcome, render_geocode_report
from app.core.database import session_scope
from app.services.geocode_service import RETRY_APRES, run_geocode_courses


def _progression(actif: bool):
    """`None` si la progression est coupée : `run_geocode_courses` n'appelle rien."""
    if not actif:
        return None

    def _sur_tentative(index: int, total: int, nom: str, coord) -> None:
        issue = "géocodée" if coord is not None else "échec (ville introuvable)"
        typer.echo(f"[{index + 1}/{total}] {nom} → {issue}", err=True)

    return _sur_tentative


def geocode_courses(
    limit: int | None = typer.Option(
        None, "--limit", help="Borne le nombre d'épreuves géocodées."
    ),
    retry_after_days: int = typer.Option(
        RETRY_APRES.days, "--retry-after-days",
        help="Ne retente un échec qu'après ce délai (jours).",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Liste les épreuves ciblées sans appeler Nominatim ni rien persister.",
    ),
    json_output: bool = typer.Option(
        False, "--json",
        help="stdout ne contient que le JSON ; le rapport texte passe sur stderr.",
    ),
    no_progress: bool = typer.Option(
        False, "--no-progress", help="Aucun affichage de progression."
    ),
) -> None:
    """Géocode les épreuves sans coordonnées (Nominatim, ~1 à 2 s par épreuve).

    Persiste `latitude`/`longitude` sur `Course` : c'est ce qui permet à
    `GET /stats/events-geo` de ne plus jamais appeler Nominatim. Un échec
    (ville introuvable) pose quand même `geocoded_at`, pour ne pas être
    retenté avant `--retry-after-days` (7 par défaut).

    À lancer une fois après le déploiement de la migration (colonnes vides sur
    l'existant), puis périodiquement — chaque nouvelle épreuve importée n'a
    pas encore de coordonnées tant que cette commande ne les lui a pas
    données.
    """
    with session_scope() as db:
        outcome = run_geocode_courses(
            db,
            limit=limit,
            retry_after=timedelta(days=retry_after_days),
            dry_run=dry_run,
            on_item=_progression(not no_progress and not dry_run),
        )

    emit_outcome(
        outcome,
        render_geocode_report(outcome, dry_run=dry_run),
        json_output=json_output,
    )
