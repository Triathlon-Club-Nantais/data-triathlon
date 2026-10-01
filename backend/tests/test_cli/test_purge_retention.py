"""La commande `purge-retention` (#1158)."""
import json
import re
from datetime import timedelta

from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import purge_retention as cmd
from app.core.time import utcnow
from app.models.user_feedback import UserFeedback
from app.repositories import feedback_repository

runner = CliRunner()


def _ancien_signalement(db):
    entry = feedback_repository.create(db, type="bug", title="t", body="b")
    entry.created_at = utcnow() - timedelta(days=400)
    db.flush()
    return entry


def test_dry_run_reports_counts_and_deletes_nothing(brancher_session, db_session):
    brancher_session(cmd)
    entry = _ancien_signalement(db_session)

    result = runner.invoke(app, ["purge-retention", "--dry-run", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"dry_run": True, "feedback": 1, "admin_log": 0, "profiles": 0}
    assert db_session.get(UserFeedback, entry.id) is not None


def test_purge_deletes_and_prints_a_french_report(brancher_session, db_session):
    brancher_session(cmd)
    entry = _ancien_signalement(db_session)

    result = runner.invoke(app, ["purge-retention"])

    assert result.exit_code == 0
    assert re.search(r"Signalements supprimés\s+: 1", result.stdout)
    assert db_session.get(UserFeedback, entry.id) is None
