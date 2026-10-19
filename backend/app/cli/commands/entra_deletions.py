"""Commande `entra-deletions` : les utilisateurs Entra à effacer à la main (#1635). Lecture seule.

Après une suppression de compte, l'utilisateur reste dans l'annuaire du tenant
(la suppression automatique est payante). Cette commande relit le journal
`account.delete` et rend chaque `oid` avec sa commande `az rest`, à lancer après
`az login --tenant <tid> --allow-no-subscriptions`. `--count` rend le seul total,
pour le rappel de la reprise planifiée.
"""
from datetime import datetime, timedelta

import typer

from app.core.database import session_scope
from app.core.time import utcnow
from app.services.auth import accounts

#: Au delà du rythme mensuel annoncé par la politique de confidentialité.
DEFAULT_WINDOW_DAYS = 35


def entra_deletions(
    since: datetime | None = typer.Option(
        None, "--since", formats=["%Y-%m-%d"], help="Date de début (AAAA-MM-JJ), 35 jours par défaut."
    ),
    count: bool = typer.Option(False, "--count", help="Le seul nombre d'identifiants, sans détail."),
) -> None:
    """Liste les identifiants Entra des comptes supprimés depuis une date."""
    with session_scope() as db:
        pending = accounts.pending_entra_deletions(db, since=since or utcnow() - timedelta(days=DEFAULT_WINDOW_DAYS))

    total = sum(len(deletion.oids) for deletion in pending)
    if count:
        typer.echo(total)
        return
    for deletion in pending:
        typer.echo(f"# compte {deletion.user_id}, supprimé le {deletion.deleted_at:%Y-%m-%d}")
        for oid in deletion.oids:
            typer.echo(f"az rest --method delete --url https://graph.microsoft.com/v1.0/users/{oid}")
    typer.echo(f"{total} identifiant(s) Entra à effacer.")
