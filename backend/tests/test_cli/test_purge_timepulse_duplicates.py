"""La commande `purge-timepulse-duplicates` (#1004)."""
import json
from contextlib import contextmanager
from datetime import date

from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import purge_timepulse_duplicates as cmd
from app.models.admin_action_log import AdminActionLog
from app.repositories import (
    athlete_repository,
    course_repository,
    participation_repository,
    user_repository,
)

runner = CliRunner()
URL = "https://timepulse.fr/epreuves/resultats/3054"


def _peupler(db):
    user_repository.create(db, email="admin@exemple.fr", display_name="Admin")
    ancienne = course_repository.get_or_create(
        db, name="DUATHLON COUERON", event_date=date(2025, 5, 4), event_type="duathlon-s",
        source_url=URL, provider="timepulse",
    )
    qualifiee = course_repository.get_or_create(
        db, name="DUATHLON COUERON - Duathlon S", event_date=date(2025, 5, 4),
        event_type="duathlon-s", source_url=URL, provider="timepulse",
    )
    athlete = athlete_repository.get_or_create(db, nom="ALPHA", prenom="Test")
    for course in (ancienne, qualifiee):
        participation_repository.create(db, athlete_id=athlete.id, course_id=course.id, bib_number="1")
    db.flush()
    return ancienne


def _brancher(monkeypatch, db_session):
    ancienne = _peupler(db_session)

    @contextmanager
    def _session():
        yield db_session

    monkeypatch.setattr(cmd, "session_scope", _session)
    return ancienne


def test_without_yes_it_lists_and_writes_nothing(monkeypatch, db_session):
    ancienne = _brancher(monkeypatch, db_session)

    result = runner.invoke(app, ["purge-timepulse-duplicates", "--json"])

    assert result.exit_code == 0
    corps = json.loads(result.stdout)
    assert corps["deleted"] is False
    assert [c["course_id"] for c in corps["courses"]] == [ancienne.id]
    assert course_repository.get(db_session, ancienne.id) is not None


def test_with_yes_it_deletes_and_logs_under_the_given_account(monkeypatch, db_session):
    ancienne = _brancher(monkeypatch, db_session)

    result = runner.invoke(
        app, ["purge-timepulse-duplicates", "--yes", "--by-email", "admin@exemple.fr"]
    )

    assert result.exit_code == 0
    assert "1 épreuve(s) supprimée(s)." in result.stdout
    assert course_repository.get(db_session, ancienne.id) is None
    assert db_session.query(AdminActionLog).filter_by(entity_id=ancienne.id).count() == 1


def test_yes_without_a_known_account_is_a_usage_error(monkeypatch, db_session):
    ancienne = _brancher(monkeypatch, db_session)

    result = runner.invoke(app, ["purge-timepulse-duplicates", "--yes"])

    assert result.exit_code == cmd.USAGE
    assert course_repository.get(db_session, ancienne.id) is not None
