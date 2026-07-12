"""Outillage CLI (Typer) : import de masse depuis le Google Sheet & rescrape DB.

CLI mince par-dessus les services : aucune logique de scraping ni d'accès DB
direct. Invocable depuis backend/ :
    python -m app.cli import-sheet --dry-run
    python -m app.cli rescrape-db --dry-run
"""
import typer

from app.cli.commands.import_sheet import import_sheet
from app.cli.commands.rescrape_db import rescrape_db

app = typer.Typer(help="Outillage d'import de masse et de rescrape.")
app.command("import-sheet")(import_sheet)
app.command("rescrape-db")(rescrape_db)

__all__ = ["app"]
