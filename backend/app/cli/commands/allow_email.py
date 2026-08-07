"""Commande `allow-email` : autorise une adresse sans session. Zéro logique métier.

**La voie d'amorçage** (#170, FR-014), jumelle de `grant-role` : sur une base
neuve la liste d'autorisation est vide, donc personne ne peut ouvrir de session,
donc personne ne peut ouvrir le back-office pour autoriser quelqu'un. C'est aussi
le rattrapage hors ligne si l'écran devient inaccessible.

Elle contourne délibérément la garde de pouvoir, exactement comme `grant-role` :
sans session, il n'y a pas d'acteur dont comparer les pouvoirs, et l'accès au
serveur *est* le privilège.

**Elle ne retire pas.** Le retrait vit dans l'écran, où il est gardé par
l'invariant du dernier administrateur. Une commande de retrait sans cet invariant
serait un verrou à distribuer, et l'erreur qu'elle rendrait possible — se fermer
soi-même l'accès — n'a pas de rattrapage plus simple que celui qu'elle
prétendrait offrir. Réinscrire suffit à réparer un retrait fait par erreur.
"""
import typer

from app.core.database import session_scope
from app.services.auth import allowed_emails

#: Convention Click / Typer, comme `grant-role` : `2` = erreur d'usage.
USAGE = 2


def allow_email(
    email: str = typer.Option(..., "--email", help="Adresse à autoriser."),
) -> None:
    """Autorise une adresse à ouvrir une session. **Idempotent**.

    Ne crée **pas** d'utilisateur : le compte naît de la première connexion. Pour
    lui donner un rôle ensuite, `grant-role --email <adresse> --role admin`.
    """
    try:
        with session_scope() as db:
            # Même validation que la ressource HTTP, par le **même service** :
            # deux notions de « adresse valide » divergeraient au premier
            # ajustement, et c'est déjà arrivé une fois — le DTO validait pour
            # l'API, la CLI rattrapait à part, et seule l'une des deux parlait
            # français. `add` valide **avant** d'écrire, donc un refus ne laisse
            # rien derrière lui, sans avoir à valider une seconde fois ici.
            entree, creee, reactives = allowed_emails.add(db, None, email=email)
            adresse = entree.email
            db.commit()
    except allowed_emails.InvalidEmailError as invalide:
        typer.echo(invalide.message)
        raise typer.Exit(USAGE) from invalide

    if creee:
        typer.echo(f"Adresse « {adresse} » autorisée à ouvrir une session.")
    else:
        typer.echo(f"Rien à faire : « {adresse} » est déjà autorisée.")
    if reactives:
        typer.echo(f"{reactives} compte(s) réactivé(s).")
