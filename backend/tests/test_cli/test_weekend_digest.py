"""`weekend-digest`: Monday Slack board of the club's weekend results (#1363)."""
import logging

import pytest
from pydantic import SecretStr
from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import weekend_digest as cmd
from app.core.config import Settings
from app.services.weekend_digest import DigestDeliveryError
from tests.test_services.test_weekend_digest import SAT, _course, _result

runner = CliRunner()
ARGS = ["weekend-digest", "--date", "2026-10-19"]


@pytest.fixture
def sent(monkeypatch, brancher_session):
    brancher_session(cmd)
    calls = []
    monkeypatch.setattr(cmd.weekend_digest_service, "send", lambda text, url: calls.append((text, url)))
    return calls


def _webhook(monkeypatch, url="https://hooks.slack.com/services/T/B/S"):
    monkeypatch.setattr(cmd, "get_settings", lambda: Settings(slack_digest_webhook_url=SecretStr(url)))


def test_without_webhook_it_logs_and_exits_zero(monkeypatch, sent, caplog):
    _webhook(monkeypatch, "")
    monkeypatch.setattr(cmd, "session_scope", lambda: pytest.fail("database opened"))

    with caplog.at_level(logging.WARNING):
        result = runner.invoke(app, ARGS)

    assert result.exit_code == 0
    assert "SLACK_DIGEST_WEBHOOK_URL" in caplog.text
    assert sent == []


def test_an_empty_weekend_posts_nothing(monkeypatch, sent):
    _webhook(monkeypatch)

    assert runner.invoke(app, ARGS).exit_code == 0
    assert sent == []


def test_a_weekend_with_results_is_posted(monkeypatch, sent, db_session):
    _webhook(monkeypatch)
    _result(db_session, _course(db_session, SAT), "Jean", "Dupont")

    result = runner.invoke(app, ARGS)

    assert result.exit_code == 0
    assert len(sent) == 1 and "Tri de Nantes" in sent[0][0]


def test_dry_run_prints_without_posting(monkeypatch, sent, db_session):
    _webhook(monkeypatch, "")
    _result(db_session, _course(db_session, SAT), "Jean", "Dupont")

    result = runner.invoke(app, [*ARGS, "--dry-run"])

    assert result.exit_code == 0 and "Tri de Nantes" in result.stdout
    assert sent == []


def test_a_delivery_failure_exits_one(monkeypatch, brancher_session, db_session):
    brancher_session(cmd)
    _webhook(monkeypatch)
    _result(db_session, _course(db_session, SAT), "Jean", "Dupont")

    def fail(text, url):
        raise DigestDeliveryError("Slack a répondu 404.")

    monkeypatch.setattr(cmd.weekend_digest_service, "send", fail)

    assert runner.invoke(app, ARGS).exit_code == 1
