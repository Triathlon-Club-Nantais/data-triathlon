"""Commande `set-site-code` : pose le code d'accès au site sans session (#929).

**Voie d'amorçage**, jumelle d'`allow-email` et `grant-role` : sur une base neuve
aucun code n'est posé, la garde fail-closed ferme toutes les pages, et l'écran
`/admin/acces` exige une session admin, donc une application OAuth. Sans cette
commande, consulter le seed de démo en local demanderait de configurer le SSO.

Même service que l'écran (`site_access.replace_password`) : le hachage, la
rotation du secret de session (qui ferme les sessions ouvertes) et l'écriture
des trois champs ensemble ne sont pas dupliqués ici.
"""
import typer

from app.core.database import session_scope
from app.schemas.site_access import MAX_PASSWORD_LENGTH
from app.schemas.site_access_config import MIN_TYPED_PASSWORD_LENGTH
from app.services import site_access

#: Convention Click / Typer, comme `allow-email` : `2` = erreur d'usage.
USAGE = 2


def set_site_code(
    code: str | None = typer.Option(
        None, "--code", help="Code à poser. Absent : un code robuste est généré et affiché."
    ),
) -> None:
    """Pose (ou remplace) le code d'accès au site. Ferme les sessions ouvertes."""
    if code is not None and not MIN_TYPED_PASSWORD_LENGTH <= len(code) <= MAX_PASSWORD_LENGTH:
        typer.echo(
            f"Le code doit compter entre {MIN_TYPED_PASSWORD_LENGTH} et "
            f"{MAX_PASSWORD_LENGTH} caractères."
        )
        raise typer.Exit(USAGE)

    with session_scope() as db:
        _, mot_de_passe = site_access.replace_password(db, password=code, admin_user_id=None)
        db.commit()

    if code is None:
        typer.echo("Code d'accès généré (il ne sera plus affiché) :")
        typer.echo(mot_de_passe)
    else:
        typer.echo("Code d'accès posé.")
