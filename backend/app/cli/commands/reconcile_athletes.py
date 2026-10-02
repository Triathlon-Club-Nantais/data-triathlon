"""Commande `reconcile-athletes` : reprise des doublons d'athlètes existants (#906). Zéro logique métier.

Sans `--yes`, elle simule : le plan complet, rien d'écrit. Avec `--yes
--by-email <admin> --plan-from <simulation.json>`, elle applique le plan relu,
une transaction par opération, chaque fusion et chaque renommage journalisés au
nom de ce compte. Sans `--plan-from`, `--yes` recalcule le plan juste avant de
l'appliquer. Relancée après application, elle ne trouve plus rien à faire.
"""
import json
from pathlib import Path

import typer

from app.cli.reports import emit_report, render_reconciliation_report
from app.core.database import session_scope
from app.repositories import user_repository
from app.services import athlete_reconciliation

#: Convention Click / Typer : `2` = erreur d'usage, `130` = Ctrl-C.
USAGE = 2
INTERRUPTED = 130


def _usage(message: str) -> typer.Exit:
    typer.echo(message, err=True)
    return typer.Exit(USAGE)


def _simulation(path: Path) -> dict:
    """Le plan d'une simulation `--json`, ou une erreur d'usage."""
    try:
        planned = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise _usage(f"--plan-from : simulation illisible ({exc}).") from exc
    if not isinstance(planned, dict) or planned.get("applied") is not False or not isinstance(
        planned.get("operations"), list
    ):
        raise _usage("--plan-from attend le JSON d'une simulation (reconcile-athletes --json, sans --yes).")
    return planned


def reconcile_athletes(
    yes: bool = typer.Option(False, "--yes", help="Applique vraiment (sinon : simulation seulement)."),
    by_email: str | None = typer.Option(
        None, "--by-email", help="Compte au nom duquel le journal consigne chaque opération."
    ),
    plan_from: Path | None = typer.Option(
        None, "--plan-from", help="Applique ce plan simulé (sortie de --json) au lieu d'en recalculer un."
    ),
    json_output: bool = typer.Option(
        False, "--json",
        help="stdout ne contient que le JSON ; le rapport texte passe sur stderr.",
    ),
    no_progress: bool = typer.Option(False, "--no-progress", help="Pas de progression sur stderr."),
) -> None:
    """Simule, ou applique avec `--yes`, la reprise des fiches d'athlètes en double :
    noms « NOM, Prénom » mal découpés, graphies équivalentes, noms inversés ou
    concaténés. Les cas douteux sont listés en revue, jamais fusionnés."""
    if plan_from is not None and not yes:
        raise _usage("--plan-from s'applique : il exige --yes.")
    planned = _simulation(plan_from) if plan_from is not None else None
    progress = None if no_progress else (lambda message: typer.echo(message, err=True))
    report: dict = {}
    code = 0
    try:
        with session_scope() as db:
            comptes = []
            if yes:
                comptes = user_repository.find_by_email(db, by_email) if by_email else []
                if not comptes:
                    raise _usage("--yes exige --by-email, l'adresse d'un compte existant.")
            if planned is None:
                planned = athlete_reconciliation.plan(db, progress=progress)
            if not yes:
                report = planned
            else:
                athlete_reconciliation.apply(db, planned, user_id=comptes[0].id, report=report, progress=progress)
                total = len(planned["operations"])
                if total and len(report["errors"]) == total:
                    code = 1
    except KeyboardInterrupt:
        report["interrupted"] = True
        code = INTERRUPTED

    emit_report(render_reconciliation_report(report), report, json_output=json_output)
    if code:
        raise typer.Exit(code)
