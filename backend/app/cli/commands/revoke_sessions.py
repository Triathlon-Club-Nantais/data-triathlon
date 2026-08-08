"""Commande `revoke-sessions` : la révocation d'urgence (#169). Zéro logique métier.

**Le geste d'incident**, et la raison d'être de la commande : jusqu'ici, fermer
les sessions de tout le monde supposait d'ouvrir `psql` sur Supabase à la main,
sous stress, en production. La purge des sessions *expirées*, elle, reste
opportuniste (`session.open_for`) et n'a besoin d'aucun outil — ce sont deux
besoins distincts, et les avoir fondus est ce que cette commande corrige.

Elle contourne délibérément la garde de pouvoir, comme `allow-email` et
`grant-role` : sans session, il n'y a pas d'acteur dont comparer les pouvoirs, et
l'accès au serveur *est* le privilège. C'est aussi ce qui la rend utilisable
quand le back-office jumeau (`/admin/acces`) est justement ce dont on se méfie.
C'est aussi le seul chemin pour fermer les sessions d'une adresse **déjà
retirée** de la liste d'autorisation, que l'écran ne montre plus.

**Elle ne désactive aucun compte** : elle coupe des jetons, elle ne met personne
dehors. Fermer *un* compte pour de bon reste le retrait de son adresse (#170).
"""
import logging

import typer

from app.core.database import session_scope
from app.repositories import user_repository
from app.services.auth import allowed_emails
from app.services.auth import session as session_service

logger = logging.getLogger(__name__)

#: Convention Click / Typer, comme `grant-role` et `allow-email` : `2` = erreur
#: d'usage.
USAGE = 2


def revoke_sessions(
    all_sessions: bool = typer.Option(
        False, "--all", help="Toutes les sessions ouvertes, tous comptes confondus."
    ),
    email: str | None = typer.Option(
        None, "--email", help="Les sessions des comptes portant cette adresse."
    ),
    yes: bool = typer.Option(
        False, "--yes", help="Ne pas demander de confirmation (--all seulement)."
    ),
) -> None:
    """Ferme des sessions ouvertes. Les comptes, eux, restent actifs.

    Deux cibles, **exclusives** l'une de l'autre — deux modes, pas des filtres à
    composer, même parti pris que `rescrape-db`. Aucune n'est le défaut : un
    `revoke-sessions` nu qui déconnecterait tout le club serait le pire des
    défauts imaginables.
    """
    if all_sessions == (email is not None):
        typer.echo("Choisissez une cible, et une seule : --all ou --email <adresse>.")
        raise typer.Exit(USAGE)

    if email is not None:
        # Même validation que la ressource HTTP et qu'`allow-email`, par le
        # **même service** : deux notions de « adresse valide » divergeraient au
        # premier ajustement. Sans elle, `--email ""` était une cible recevable.
        try:
            allowed_emails.validate_email(email)
        except allowed_emails.InvalidEmailError as invalide:
            typer.echo(invalide.message)
            raise typer.Exit(USAGE) from invalide

    # `--yes` ne garde que `--all` : fermer les sessions d'une personne se répare
    # par une reconnexion, fermer celles de tout le club non — et c'est le seul
    # des deux gestes qui déconnecte aussi celui qui le lance.
    if all_sessions and not yes and not typer.confirm(
        "Toutes les sessions vont être fermées, la vôtre comprise. Confirmer ?"
    ):
        typer.echo("Annulé.")
        return

    with session_scope() as db:
        # `email is None` équivaut à `--all` : l'exclusivité ci-dessus l'a établi.
        if email is None:
            sessions, comptes = session_service.revoke_all(db)
        else:
            # Diagnostic préalable, pas une seconde règle : le service reste seul
            # à décider *ce que* la révocation ferme. « 0 session fermée » est un
            # compte rendu juste pour `--all`, et un piège sur une adresse — il
            # confond « rien à fermer » et « vous avez mal tapé », au moment
            # exact où l'exploitant a besoin de croire ce qu'il lit. Même refus
            # que `grant-role`, sur la même liste.
            if not user_repository.find_by_email(db, email):
                typer.echo(
                    f"Aucun compte ne porte l'adresse « {email.strip()} ». "
                    "Rien n'a été fermé — vérifiez l'orthographe, ou utilisez "
                    "--all."
                )
                raise typer.Exit(USAGE)
            sessions, comptes = session_service.revoke_for_email(db, email)
        db.commit()

    logger.info(
        "Sessions revoked by cli: actor=cli target=%s sessions=%s accounts=%s",
        "all" if all_sessions else email,
        sessions,
        comptes,
    )
    typer.echo(f"{sessions} session(s) fermée(s) sur {comptes} compte(s).")
