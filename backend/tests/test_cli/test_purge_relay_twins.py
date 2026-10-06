"""La commande `purge-relay-twins` (#1195, #1197)."""
import json
from contextlib import contextmanager
from datetime import date

from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import purge_relay_twins as cmd
from app.models.admin_action_log import AdminActionLog
from app.repositories import (
    athlete_repository,
    course_repository,
    participation_repository,
    user_repository,
)

runner = CliRunner()
URL = "https://www.prolivesport.fr/index.php?eventId=1082&race=TREP"


def _brancher(monkeypatch, db):
    user_repository.create(db, email="admin@exemple.fr", display_name="Admin")
    solo, relais = (
        course_repository.get_or_create(
            db, name="La Baule 2025 - TREP", event_date=date(2025, 6, 22), event_type="triathlon-s",
            source_url=URL, provider="prolivesport", is_relay=is_relay,
        )
        for is_relay in (False, True)
    )
    equipe = athlete_repository.get_or_create(db, nom="MAZARS 1", prenom="")
    for course in (solo, relais):
        participation_repository.create(db, athlete_id=equipe.id, course_id=course.id, bib_number="1")
    db.flush()

    @contextmanager
    def _session():
        yield db

    monkeypatch.setattr(cmd, "session_scope", _session)
    return solo, relais


def test_without_yes_it_lists_and_writes_nothing(monkeypatch, db_session):
    solo, relais = _brancher(monkeypatch, db_session)

    result = runner.invoke(app, ["purge-relay-twins", "--json"])

    assert result.exit_code == 0
    corps = json.loads(result.stdout)
    assert corps["deleted"] is False
    assert [(c["course_id"], c["covered_by"]) for c in corps["courses"]] == [(solo.id, relais.id)]
    assert course_repository.get(db_session, solo.id) is not None


def test_with_yes_it_deletes_and_logs_under_the_given_account(monkeypatch, db_session):
    solo, _relais = _brancher(monkeypatch, db_session)

    result = runner.invoke(app, ["purge-relay-twins", "--yes", "--by-email", "admin@exemple.fr"])

    assert result.exit_code == 0
    assert "1 épreuve(s) supprimée(s)." in result.stdout
    assert course_repository.get(db_session, solo.id) is None
    assert db_session.query(AdminActionLog).filter_by(entity_id=solo.id).count() == 1


def test_yes_without_a_known_account_is_a_usage_error(monkeypatch, db_session):
    solo, _relais = _brancher(monkeypatch, db_session)

    result = runner.invoke(app, ["purge-relay-twins", "--yes"])

    assert result.exit_code == cmd.USAGE
    assert course_repository.get(db_session, solo.id) is not None
