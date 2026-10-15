"""`weather-courses` (#1370) : câblage CLI, Open-Meteo bouchonné par `fetch_daily_weather`."""
import json
from contextlib import contextmanager
from datetime import date, timedelta

from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import weather_courses as cmd
from app.repositories import course_repository
from app.services.weather_service import DailyWeather

runner = CliRunner()


def _plug_session(monkeypatch, db_session):
    @contextmanager
    def _session():
        yield db_session

    monkeypatch.setattr(cmd, "session_scope", _session)


def _course(db_session, name):
    course = course_repository.get_or_create(
        db_session, name=name, event_date=date.today() - timedelta(days=30), event_type="triathlon-m"
    )
    course.latitude, course.longitude = 47.2, -1.55
    db_session.flush()
    return course


def test_json_stdout_is_parsable_and_exit_0(monkeypatch, db_session):
    course = _course(db_session, "Triathlon de Nantes")
    _plug_session(monkeypatch, db_session)
    monkeypatch.setattr(
        "app.services.weather_service.fetch_daily_weather",
        lambda lat, lon, day: DailyWeather(18.0, 11.3, 0.4),
    )

    result = runner.invoke(app, ["weather-courses", "--json", "--no-progress"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["fetched"] == 1
    db_session.refresh(course)
    assert course.weather_temperature_c == 18.0


def test_total_failure_exits_1_with_report(monkeypatch, db_session):
    _course(db_session, "Triathlon Muet")
    _plug_session(monkeypatch, db_session)
    monkeypatch.setattr(
        "app.services.weather_service.fetch_daily_weather", lambda lat, lon, day: None
    )

    result = runner.invoke(app, ["weather-courses"])

    assert result.exit_code == 1
    assert "Épreuves en erreur" in result.stdout


def test_dry_run_exits_0_and_lists_targets(monkeypatch, db_session):
    _course(db_session, "Triathlon Aperçu")
    _plug_session(monkeypatch, db_session)

    result = runner.invoke(app, ["weather-courses", "--dry-run"])

    assert result.exit_code == 0
    assert "Triathlon Aperçu" in result.stdout
