"""Commande `club-labels` : inventaire des libellés de club vus en base. Zéro logique métier."""
import typer

from app.cli.reports import emit_report, render_club_labels_report
from app.core.club import is_tcn
from app.core.database import session_scope
from app.repositories import participation_repository


def club_labels(
    like: str | None = typer.Option(
        None, "--like", help="Ne montre que les libellés contenant ce fragment."
    ),
    json_output: bool = typer.Option(
        False, "--json",
        help="stdout ne contient que le JSON ; le rapport texte passe sur stderr.",
    ),
) -> None:
    """Liste les libellés de club distincts, en marquant ceux reconnus comme TCN.

    Le filtre club match à l'égalité sur une liste blanche (`core/club.py`). Une
    variante non répertoriée — « TCN TRIATHLON », « T.C.N. » — fait donc sortir
    un membre des compteurs sans le moindre signal. Cette commande est le filet :

        uv run python -m app.cli club-labels --like nant
    """
    with session_scope() as db:
        rows = participation_repository.club_label_counts(db, like=like)

    labels = [
        {"club": club, "participations": count, "is_tcn": is_tcn(club)}
        for club, count in rows
    ]
    payload = {
        "labels": labels,
        "total_labels": len(labels),
        "tcn_labels": sum(1 for row in labels if row["is_tcn"]),
        "tcn_participations": sum(row["participations"] for row in labels if row["is_tcn"]),
    }
    emit_report(render_club_labels_report(labels), payload, json_output=json_output)
