"""La commande `purge-orphans` (#1271)."""
import re

from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import purge_orphans as cmd
from app.repositories import athlete_repository

runner = CliRunner()


def test_purge_orphans_deletes_athletes_without_results(brancher_session, db_session):
    brancher_session(cmd)
    orphelin = athlete_repository.get_or_create(db_session, nom="ORPHELIN", prenom="O")
    db_session.flush()

    result = runner.invoke(app, ["purge-orphans"])

    assert result.exit_code == 0
    assert re.search(r"Athlètes orphelins supprimés\s+: 1", result.stdout)
    assert athlete_repository.get(db_session, orphelin.id) is None
