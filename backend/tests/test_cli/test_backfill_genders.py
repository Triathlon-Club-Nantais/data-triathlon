"""La commande `backfill-genders` (#1201)."""
import json
from contextlib import contextmanager
from datetime import date

from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import backfill_genders as cmd
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation

runner = CliRunner()


def _brancher(monkeypatch, db):
    athlete = Athlete(nom="DUPONT", prenom="Lea", gender="")
    course = Course(name="Tri", event_date=date(2026, 1, 1), event_type="triathlon-s")
    db.add_all([athlete, course])
    db.flush()
    db.add(Participation(athlete_id=athlete.id, course_id=course.id, category="V1F"))
    db.flush()

    @contextmanager
    def _session():
        yield db

    monkeypatch.setattr(cmd, "session_scope", _session)
    return athlete


def test_without_yes_it_simulates(monkeypatch, db_session):
    athlete = _brancher(monkeypatch, db_session)

    result = runner.invoke(app, ["backfill-genders", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "applied": False, "athletes": [{"athlete_id": athlete.id, "gender": "F"}],
    }
    db_session.refresh(athlete)
    assert athlete.gender == ""


def test_with_yes_it_writes(monkeypatch, db_session):
    athlete = _brancher(monkeypatch, db_session)

    result = runner.invoke(app, ["backfill-genders", "--yes"])

    assert result.exit_code == 0
    assert "1 fiche(s) remplie(s) : 0 M, 1 F." in result.stdout
    db_session.refresh(athlete)
    assert athlete.gender == "F"
