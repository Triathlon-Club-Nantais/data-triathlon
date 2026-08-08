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
from app.cli.commands.grant_role import grant_role
from app.cli.commands.import_sheet import import_sheet
from app.cli.commands.rescrape_db import rescrape_db
from app.cli.commands.revoke_sessions import revoke_sessions
from app.core.logging import setup_logging

app = typer.Typer(help="Outillage d'import de masse et de rescrape.")
app.command("allow-email")(allow_email)
app.command("club-labels")(club_labels)
app.command("grant-role")(grant_role)
app.command("import-sheet")(import_sheet)
app.command("rescrape-db")(rescrape_db)
app.command("revoke-sessions")(revoke_sessions)


def configure_cli_logging() -> None:
    """Logs de la CLI sur **stderr**, horodatés (utile en cron), jamais sur stdout.

    Appelé par le point d'entrée `python -m app.cli` (`__main__.py`) — pas à
    l'import du module : configurer le root logger est le rôle du process, pas
    d'une bibliothèque importée (l'API web fait de même dans `create_app()`).
    """
    setup_logging(stream=sys.stderr)


def configure_cli_tracing() -> None:
    """Démarre le traçage OTel pour un batch, s'il est activé.

    Comme pour le logging, c'est le rôle du process (`__main__.py`), pas d'un
    module importé.
    """
    from app.core.config import get_settings
    from app.core.database import engine
    from app.core.tracing import setup_tracing

    setup_tracing(enabled=get_settings().otel_enabled, engine=engine)


def shutdown_cli_tracing() -> None:
    """Vide les spans en attente avant la fin du process.

    Un batch est court et le BatchSpanProcessor exporte de façon différée :
    sans cet appel, les spans du dernier import sont perdus.
    """
    from app.core.tracing import shutdown_tracing

    shutdown_tracing()


__all__ = ["app", "configure_cli_logging", "configure_cli_tracing", "shutdown_cli_tracing"]
