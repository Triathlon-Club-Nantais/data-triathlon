"""La commande `sync-club-members` (#1202)."""
import json

from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import sync_club_members as cmd
from app.scrapers.fftri_club_members import ClubRoster, RosterMember
from app.services import club_members_service

runner = CliRunner()


def _roster(monkeypatch):
    monkeypatch.setattr(
        club_members_service.fftri_club_members, "fetch_club_roster",
        lambda url: ClubRoster(licence_year=2027, members=[RosterMember("MARTIN", "Anne", "F", "C1")]),
    )


def test_json_report_on_stdout(brancher_session, monkeypatch):
    brancher_session(cmd)
    _roster(monkeypatch)

    result = runner.invoke(app, ["sync-club-members", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "season": 2026, "total": 1, "linked": 0, "unlinked": 1, "ambiguous": 0,
    }


def test_french_report(brancher_session, monkeypatch):
    brancher_session(cmd)
    _roster(monkeypatch)

    result = runner.invoke(app, ["sync-club-members"])

    assert result.exit_code == 0
    assert "LICENCIÉS DU CLUB" in result.output
    assert "Saison 2026" in result.output


def test_an_unreachable_page_fails_the_command(brancher_session, monkeypatch):
    brancher_session(cmd)

    def broken(url):
        raise RuntimeError("boom")

    monkeypatch.setattr(club_members_service.fftri_club_members, "fetch_club_roster", broken)

    result = runner.invoke(app, ["sync-club-members"])

    assert result.exit_code == 1
