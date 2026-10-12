"""The `import-member-emails` command (#1334)."""
import json

from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import import_member_emails as cmd
from app.repositories import member_email_repository

runner = CliRunner()


def _file(tmp_path, content: bytes):
    path = tmp_path / "export.csv"
    path.write_bytes(content)
    return str(path)


def test_json_report_alone_on_stdout(brancher_session, db_session, tmp_path):
    brancher_session(cmd)
    path = _file(tmp_path, b"email\njeanne@exemple.fr\nPAUL@Exemple.fr \nfaux\n")

    result = runner.invoke(app, ["import-member-emails", "--season", "2026", "--file", path, "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"season": 2026, "added": 2, "removed": 0, "unchanged": 0, "ignored": 1}
    assert [e.email for e in member_email_repository.list_season(db_session, 2026)] == [
        "jeanne@exemple.fr", "paul@exemple.fr",
    ]


def test_french_text_report(brancher_session, tmp_path):
    brancher_session(cmd)
    path = _file(tmp_path, b"email\njeanne@exemple.fr\n")

    result = runner.invoke(app, ["import-member-emails", "--season", "2026", "--file", path])

    assert result.exit_code == 0
    assert "ADRESSES D'ADHÉRENTS" in result.stdout
    assert "Saison 2026" in result.stdout


def test_a_domain_error_exits_1_without_writing(brancher_session, db_session, tmp_path):
    brancher_session(cmd)
    path = _file(tmp_path, b"Nom\nMARTIN\n")

    result = runner.invoke(app, ["import-member-emails", "--season", "2026", "--file", path, "--json"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Colonne d'adresses e-mail" in result.stderr
    assert member_email_repository.list_season(db_session, 2026) == []


def test_a_missing_file_is_a_usage_error(brancher_session, tmp_path):
    brancher_session(cmd)

    result = runner.invoke(
        app, ["import-member-emails", "--season", "2026", "--file", str(tmp_path / "absent.csv")]
    )

    assert result.exit_code == 2
