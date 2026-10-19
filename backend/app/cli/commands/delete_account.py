"""Commande `delete-account` : effacer un compte refusé en 409 (#1634). Zéro logique métier.

La suppression en libre service (#1326) refuse un compte cité par une donnée
obligatoire du club (journal, validation de saison, cas écartés, configuration
de l'accès bénévoles). Cette commande honore la demande d'effacement : les
données restent et passent au compte système, puis le compte est supprimé comme
en libre service. Passe à blanc sans `--yes`. Comme `revoke-sessions`, elle
contourne la garde de pouvoir : l'accès au serveur est le privilège.
"""
import typer

from app.core.database import session_scope
from app.core.exceptions import DomainError
from app.repositories import user_repository
from app.services.auth import accounts

#: Convention Click / Typer, comme `revoke-sessions` : `2` = erreur d'usage.
USAGE = 2


def delete_account(
    user_id: int | None = typer.Option(None, "--user-id", help="Identifiant du compte."),
    email: str | None = typer.Option(None, "--email", help="Adresse du compte (refusée si plusieurs comptes la portent)."),
    yes: bool = typer.Option(False, "--yes", help="Appliquer ; sans lui, passe à blanc."),
) -> None:
    """Efface un compte cité par des données du club, qui passent au compte système."""
    if (user_id is None) == (email is None):
        typer.echo("Choisissez une cible, et une seule : --user-id ou --email.")
        raise typer.Exit(USAGE)

    with session_scope() as db:
        if user_id is not None:
            user = user_repository.get(db, user_id)
        else:
            matches = user_repository.find_by_email(db, email)
            if len(matches) > 1:
                typer.echo(f"{len(matches)} comptes portent cette adresse : désignez-en un par --user-id.")
                raise typer.Exit(USAGE)
            user = matches[0] if matches else None
        if user is None:
            typer.echo("Aucun compte ne correspond. Rien n'a été modifié.")
            raise typer.Exit(USAGE)

        target = user.id
        try:
            counts = accounts.force_delete_account(db, user, dry_run=not yes)
        except DomainError as refusal:  # dernier administrateur, compte système
            typer.echo(f"Refusé : {refusal.message}")
            raise typer.Exit(1) from refusal
        if yes:
            db.commit()

    for reference, count in counts.items():
        typer.echo(f"{reference} : {count}")
    if not counts:
        typer.echo("Aucune donnée obligatoire ne cite ce compte.")
    if yes:
        typer.echo(f"Compte {target} supprimé ; les références ci-dessus passent au compte système.")
    else:
        typer.echo(f"Compte {target} : passe à blanc, rien n'a été modifié. Relancez avec --yes pour appliquer.")
