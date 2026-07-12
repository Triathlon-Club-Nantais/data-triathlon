from contextlib import contextmanager

from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import import_sheet as cmd_import
from app.cli.commands import rescrape_db as cmd_rescrape
from app.services.bulk_import_service import SheetOutcome
from app.services.rescrape_service import RescrapeOutcome

runner = CliRunner()


@contextmanager
def _fausse_session():
    yield None


def test_import_sheet_dry_run_affiche_le_rapport(monkeypatch):
    monkeypatch.setattr(cmd_import, "session_scope", _fausse_session)
    monkeypatch.setattr(cmd_import.sheet_source, "download_csv", lambda url: "a,b\n")
    monkeypatch.setattr(
        cmd_import.bulk_import_service, "run_import_sheet",
        lambda *a, **k: SheetOutcome(unique_supported=4, rows_without_link=1),
    )

    result = runner.invoke(app, ["import-sheet", "--dry-run"])

    assert result.exit_code == 0
    assert "IMPORT SHEET (dry-run)" in result.stdout
    assert "Liens supportés uniques : 4" in result.stdout


def test_import_sheet_json_emet_du_json_sur_stdout(monkeypatch):
    import json

    monkeypatch.setattr(cmd_import, "session_scope", _fausse_session)
    monkeypatch.setattr(cmd_import.sheet_source, "download_csv", lambda url: "a,b\n")
    monkeypatch.setattr(
        cmd_import.bulk_import_service, "run_import_sheet",
        lambda *a, **k: SheetOutcome(imported=7, skipped=2, unique_supported=1),
    )

    result = runner.invoke(app, ["import-sheet", "--json"])

    assert result.exit_code == 0
    derniere = result.stdout.strip().splitlines()[-1]
    assert json.loads(derniere)["imported"] == 7


def test_import_sheet_interrompu_sort_en_130(monkeypatch):
    monkeypatch.setattr(cmd_import, "session_scope", _fausse_session)
    monkeypatch.setattr(cmd_import.sheet_source, "download_csv", lambda url: "a,b\n")
    monkeypatch.setattr(
        cmd_import.bulk_import_service, "run_import_sheet",
        lambda *a, **k: SheetOutcome(imported=3, unique_supported=9, interrupted=True),
    )

    result = runner.invoke(app, ["import-sheet"])

    assert result.exit_code == 130
    assert "Importées : 3" in result.stdout  # le bilan partiel est bien affiché


def test_rescrape_db_dry_run_affiche_les_urls(monkeypatch):
    monkeypatch.setattr(cmd_rescrape, "session_scope", _fausse_session)
    monkeypatch.setattr(
        cmd_rescrape.rescrape_service, "run_rescrape_db",
        lambda *a, **k: RescrapeOutcome(total=1, dry_run_urls=["https://k/1"]),
    )

    result = runner.invoke(app, ["rescrape-db", "--dry-run"])

    assert result.exit_code == 0
    assert "Courses ciblées : 1" in result.stdout
    assert "https://k/1" in result.stdout


def test_rescrape_db_interrompu_sort_en_130(monkeypatch):
    monkeypatch.setattr(cmd_rescrape, "session_scope", _fausse_session)
    monkeypatch.setattr(
        cmd_rescrape.rescrape_service, "run_rescrape_db",
        lambda *a, **k: RescrapeOutcome(total=9, imported=2, interrupted=True),
    )

    result = runner.invoke(app, ["rescrape-db"])

    assert result.exit_code == 130
