"""La commande `purge-orphans` (#1271)."""
import re

from sqlalchemy.exc import IntegrityError
from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import purge_orphans as cmd
from app.repositories import athlete_repository, course_repository, participation_repository

runner = CliRunner()


def _athlete_avec_participation(db):
    course = course_repository.get_or_create(
        db, name="Tri", event_date=None, event_type="triathlon-m",
        source_url="https://k/x", provider="klikego",
    )
    athlete = athlete_repository.get_or_create(db, nom="RATTACHE", prenom="X")
    db.flush()
    participation_repository.create(db, athlete_id=athlete.id, course_id=course.id, bib_number="1")
    db.flush()
    return athlete


def test_purge_orphans_deletes_athletes_without_results(brancher_session, db_session):
    brancher_session(cmd)
    rattache = _athlete_avec_participation(db_session)
    orphelin = athlete_repository.get_or_create(db_session, nom="ORPHELIN", prenom="O")
    db_session.flush()

    result = runner.invoke(app, ["purge-orphans"])

    assert result.exit_code == 0
    assert re.search(r"Athlètes orphelins supprimés\s+: 1", result.stdout)
    assert athlete_repository.get(db_session, orphelin.id) is None
    assert athlete_repository.get(db_session, rattache.id) is not None


def test_purge_orphans_defers_on_a_concurrent_import(brancher_session, db_session, monkeypatch):
    """#1100 : un import concurrent qui rattache un orphelin fait échouer le DELETE.

    Ce n'est pas une panne : le balayage se rattrape au passage suivant.
    """
    brancher_session(cmd)

    def _conflit(db):
        raise IntegrityError("DELETE", {}, Exception("fk"))

    monkeypatch.setattr(athlete_repository, "delete_orphans", _conflit)

    result = runner.invoke(app, ["purge-orphans"])

    assert result.exit_code == 0
    assert "balayage reporté au prochain passage" in result.output
