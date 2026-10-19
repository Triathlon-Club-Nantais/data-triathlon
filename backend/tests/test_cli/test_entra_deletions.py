"""`entra-deletions`: what is left to erase in the Entra directory (#1635)."""
from datetime import datetime

from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import entra_deletions as cmd
from app.models.admin_action_log import AdminActionLog
from app.models.user import SYSTEM_USER_EMAIL
from app.repositories import user_repository

runner = CliRunner()


def _deleted(db, oids):
    system = user_repository.create(db, email=SYSTEM_USER_EMAIL, display_name="")
    db.add(AdminActionLog(user_id=system.id, action="account.delete", entity_type="user", entity_id=7,
                          payload={"origin": "request", "entra_oids": oids}, created_at=datetime(2026, 10, 10)))
    db.flush()


def test_lists_each_oid_with_its_az_command_and_the_total(brancher_session, db_session):
    brancher_session(cmd)
    _deleted(db_session, ["oid-1", "oid-2"])

    result = runner.invoke(app, ["entra-deletions", "--since", "2026-10-01"])

    assert result.exit_code == 0
    assert "az rest --method delete --url https://graph.microsoft.com/v1.0/users/oid-1" in result.stdout
    assert "oid-2" in result.stdout
    assert "2 identifiant(s) Entra à effacer" in result.stdout


def test_count_prints_the_bare_total(brancher_session, db_session):
    brancher_session(cmd)
    _deleted(db_session, ["oid-1", "oid-2"])

    result = runner.invoke(app, ["entra-deletions", "--since", "2026-10-01", "--count"])

    assert (result.exit_code, result.stdout.strip()) == (0, "2")


def test_since_accepts_a_time_for_an_exact_weekly_window(brancher_session, db_session):
    """The scheduled reminder counts an exact week, to the second (review of #1635)."""
    brancher_session(cmd)
    _deleted(db_session, ["oid-1"])

    before = runner.invoke(app, ["entra-deletions", "--since", "2026-10-09T23:59:59", "--count"])
    after = runner.invoke(app, ["entra-deletions", "--since", "2026-10-10T00:00:01", "--count"])

    assert (before.stdout.strip(), after.stdout.strip()) == ("1", "0")


def test_nothing_to_erase(brancher_session, db_session):
    brancher_session(cmd)

    result = runner.invoke(app, ["entra-deletions", "--since", "2026-10-01"])

    assert result.exit_code == 0
    assert "0 identifiant(s) Entra à effacer" in result.stdout
