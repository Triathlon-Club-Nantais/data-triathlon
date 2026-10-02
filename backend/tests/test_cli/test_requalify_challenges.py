"""La commande `requalify-challenges` (#1008)."""
import json
from datetime import date

from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import requalify_challenges as cmd
from app.models.athlete import Athlete
from app.models.challenge import Challenge
from app.models.course import Course
from app.models.participation import Participation
from app.repositories import user_repository

runner = CliRunner()
DAY = date(2026, 5, 13)


def _seed(db):
    user_repository.create(db, email="admin@exemple.fr", display_name="Admin")
    xs = Course(name="E - XS", event_date=DAY, event_type="triathlon-xs")
    m = Course(name="E - M", event_date=DAY, event_type="triathlon-m")
    challenge = Course(name="E - START CHALLENGE (XS - M - L)", event_date=DAY, event_type="triathlon-l")
    db.add_all([xs, m, challenge])
    db.flush()
    for i in range(3):
        athlete = Athlete(nom=f"NOM{i}", prenom="Jean")
        db.add(athlete)
        db.flush()
        for course, bib in ((xs, f"x{i}"), (m, f"m{i}"), (challenge, f"c{i}")):
            db.add(Participation(athlete_id=athlete.id, course_id=course.id, bib_number=bib))
    db.flush()
    return challenge


def test_without_yes_it_lists_and_writes_nothing(brancher_session, db_session):
    brancher_session(cmd)
    challenge = _seed(db_session)

    result = runner.invoke(app, ["requalify-challenges", "--json"])

    assert result.exit_code == 0
    corps = json.loads(result.stdout)
    assert corps["converted"] is False
    assert [c["course_id"] for c in corps["challenges"]] == [challenge.id]
    assert db_session.get(Course, challenge.id) is not None


def test_with_yes_it_converts(brancher_session, db_session):
    brancher_session(cmd)
    challenge = _seed(db_session)
    challenge_id = challenge.id

    result = runner.invoke(app, ["requalify-challenges", "--yes", "--by-email", "admin@exemple.fr"])

    assert result.exit_code == 0
    assert "1 épreuve(s) requalifiée(s)." in result.stdout
    assert db_session.get(Course, challenge_id) is None
    assert db_session.query(Challenge).count() == 1


def test_yes_without_a_known_account_is_a_usage_error(brancher_session, db_session):
    brancher_session(cmd)
    challenge = _seed(db_session)

    result = runner.invoke(app, ["requalify-challenges", "--yes"])

    assert result.exit_code == cmd.USAGE
    assert db_session.get(Course, challenge.id) is not None
