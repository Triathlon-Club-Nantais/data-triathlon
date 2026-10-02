"""Commande `reconcile-athletes` : reprise des doublons d'athlètes existants (#906). Zéro logique métier.

Sans `--yes`, elle simule : le plan complet, rien d'écrit. Avec `--yes
--by-email <admin>`, elle applique exactement ce plan, une transaction par
opération, chaque fusion et chaque renommage journalisés au nom de ce compte.
Relancée après application, elle ne trouve plus rien à faire.
"""
import typer

from app.cli.reports import emit_report, render_reconciliation_report
from app.core.database import session_scope
from app.repositories import user_repository
from app.services import athlete_reconciliation

#: Convention Click / Typer : `2` = erreur d'usage, `130` = Ctrl-C.
USAGE = 2
INTERRUPTED = 130


def reconcile_athletes(
    yes: bool = typer.Option(False, "--yes", help="Applique vraiment (sinon : simulation seulement)."),
    by_email: str | None = typer.Option(
        None, "--by-email", help="Compte au nom duquel le journal consigne chaque opération."
    ),
    json_output: bool = typer.Option(
        False, "--json",
        help="stdout ne contient que le JSON ; le rapport texte passe sur stderr.",
    ),
) -> None:
    """Simule, ou applique avec `--yes`, la reprise des fiches d'athlètes en double :
    noms « NOM, Prénom » mal découpés, graphies équivalentes, noms inversés ou
    concaténés. Les cas douteux sont listés en revue, jamais fusionnés."""
    report: dict = {}
    code = 0
    with session_scope() as db:
        planned = athlete_reconciliation.plan(db)
        if not yes:
            report = planned
        else:
            comptes = user_repository.find_by_email(db, by_email) if by_email else []
            if not comptes:
                typer.echo("--yes exige --by-email, l'adresse d'un compte existant.", err=True)
                raise typer.Exit(USAGE)
            try:
                athlete_reconciliation.apply(db, planned, user_id=comptes[0].id, report=report)
            except KeyboardInterrupt:
                report["interrupted"] = True
                code = INTERRUPTED
            else:
                total = len(planned["operations"])
                if total and len(report["errors"]) == total:
                    code = 1

    emit_report(render_reconciliation_report(report), report, json_output=json_output)
    if code:
        raise typer.Exit(code)
