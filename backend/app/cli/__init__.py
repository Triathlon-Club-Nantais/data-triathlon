"""Outillage CLI (Typer) : import de masse depuis le Google Sheet & rescrape DB.

CLI mince par-dessus les services : aucune logique de scraping ni d'accès DB
direct. Invocable depuis backend/ :
    python -m app.cli import-sheet --dry-run
    python -m app.cli rescrape-db --dry-run

⚠ CONTRAINTE DURE : **stdout doit rester parsable**. Il ne porte que le rapport
final — et, avec `--json`, rien d'autre que la ligne JSON (`… --json | jq`). Tout
le reste (progression, logs) sort sur stderr. Ne jamais appeler `setup_logging()`
sans flux ici : son défaut est stdout, et le premier `logger.warning` d'un batch
(épreuve en échec) casserait le pipe. C'est `configure_cli_logging()` qui fait foi.
"""
import sys

import typer

from app.cli.commands.allow_email import allow_email
from app.cli.commands.club_labels import club_labels
from app.cli.commands.geocode_courses import geocode_courses
from app.cli.commands.grant_role import grant_role
from app.cli.commands.import_sheet import import_sheet
from app.cli.commands.rescrape_db import rescrape_db
from app.cli.commands.revoke_sessions import revoke_sessions
from app.core.logging import setup_logging

app = typer.Typer(help="Outillage d'import de masse et de rescrape.")
app.command("allow-email")(allow_email)
app.command("club-labels")(club_labels)
app.command("geocode-courses")(geocode_courses)
app.command("grant-role")(grant_role)
app.command("import-sheet")(import_sheet)
app.command("rescrape-db")(rescrape_db)
app.command("revoke-sessions")(revoke_sessions)


def load_counter_scope() -> None:
    """Remplit le registre de la portée des compteurs depuis la base (#95).

    Appelé par le point d'entrée `python -m app.cli` (`__main__.py`), comme
    `configure_cli_logging` et pour la même raison : remplir un registre de
    processus est le rôle du process, pas d'une bibliothèque importée.

    Sans ce chargement, `is_tcn` et `is_federal` se prononceraient sur les
    défauts du code plutôt que sur ce qui est configuré — `club-labels`
    signalerait comme manquant un libellé déclaré depuis le panel admin.
    """
    from app.core.database import session_scope
    from app.services import counter_scope

    with session_scope() as db:
        counter_scope.load_from_db(db)


def configure_cli_logging() -> None:
    """Logs de la CLI sur **stderr**, horodatés (utile en cron), jamais sur stdout.

    Appelé par le point d'entrée `python -m app.cli` (`__main__.py`) — pas à
    l'import du module : configurer le root logger est le rôle du process, pas
    d'une bibliothèque importée (l'API web fait de même dans `create_app()`).
    """
    setup_logging(stream=sys.stderr)


__all__ = ["app", "configure_cli_logging", "load_counter_scope"]
