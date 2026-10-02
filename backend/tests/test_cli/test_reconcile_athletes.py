"""La commande `reconcile-athletes` (#906) : simulation, application, contrat de sortie."""
import json

import pytest
from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import reconcile_athletes as cmd
from app.models.admin_action_log import AdminActionLog
from app.models.athlete import Athlete
from app.repositories import user_repository
from app.services import athlete_reconciliation

runner = CliRunner()


@pytest.fixture
def doublons(db_session, brancher_session):
    brancher_session(cmd)
    user_repository.create(db_session, email="admin@exemple.fr")
    db_session.add_all([
        Athlete(nom="LETORT", prenom="Léo"),
        Athlete(nom="LETORT", prenom="Leo", homonym_rank=1),
        Athlete(nom="HOFMANN,", prenom="Patrick"),
    ])
    db_session.commit()


def test_without_yes_it_simulates_and_writes_nothing(db_session, doublons):
    result = runner.invoke(app, ["reconcile-athletes", "--json"])

    assert result.exit_code == 0
    body = json.loads(result.stdout)
    assert body["applied"] is False
    assert [(op["family"], op["action"]) for op in body["operations"]] == [
        ("comma_names", "rename"), ("same_key", "merge"),
    ]
    assert db_session.query(Athlete).count() == 3
    assert db_session.query(AdminActionLog).count() == 0


def test_the_text_report_tells_how_to_apply(db_session, doublons):
    result = runner.invoke(app, ["reconcile-athletes"])

    assert result.exit_code == 0
    assert "--yes --by-email" in result.stdout
    assert "same_key" in result.stdout


def test_yes_applies_and_logs_under_the_operator(db_session, doublons):
    result = runner.invoke(app, ["reconcile-athletes", "--yes", "--by-email", "admin@exemple.fr", "--json"])

    assert result.exit_code == 0
    body = json.loads(result.stdout)
    assert (body["applied"], body["errors"]) == (True, [])
    assert db_session.query(Athlete).count() == 2
    admin = user_repository.find_by_email(db_session, "admin@exemple.fr")[0]
    assert {entry.user_id for entry in db_session.query(AdminActionLog)} == {admin.id}


@pytest.mark.parametrize("args", [["--yes"], ["--yes", "--by-email", "inconnu@exemple.fr"]])
def test_yes_needs_a_known_operator(db_session, doublons, args):
    result = runner.invoke(app, ["reconcile-athletes", *args])

    assert result.exit_code == 2
    assert db_session.query(Athlete).count() == 3


def test_a_relaunch_after_application_has_nothing_to_do(db_session, doublons):
    runner.invoke(app, ["reconcile-athletes", "--yes", "--by-email", "admin@exemple.fr"])

    result = runner.invoke(app, ["reconcile-athletes", "--json"])

    assert json.loads(result.stdout)["operations"] == []


def test_a_total_failure_exits_1(db_session, doublons, monkeypatch):
    def nothing_works(db, planned, *, user_id, report=None, progress=None):
        report.update({**planned, "applied": True, "done": 0,
                       "errors": [{"operation": op, "error": "boom"} for op in planned["operations"]]})
        return report

    monkeypatch.setattr(athlete_reconciliation, "apply", nothing_works)

    result = runner.invoke(app, ["reconcile-athletes", "--yes", "--by-email", "admin@exemple.fr", "--json"])

    assert result.exit_code == 1
    assert len(json.loads(result.stdout)["errors"]) == 2


def test_an_interruption_exits_130_with_the_partial_report(db_session, doublons, monkeypatch):
    def interrupted(db, planned, *, user_id, report=None, progress=None):
        report.update({**planned, "applied": True, "done": 1, "errors": []})
        raise KeyboardInterrupt

    monkeypatch.setattr(athlete_reconciliation, "apply", interrupted)

    result = runner.invoke(app, ["reconcile-athletes", "--yes", "--by-email", "admin@exemple.fr", "--json"])

    assert result.exit_code == 130
    body = json.loads(result.stdout)
    assert (body["done"], body["interrupted"]) == (1, True)


def test_plan_from_applies_the_reviewed_simulation_and_nothing_else(db_session, doublons, tmp_path):
    """L'application exécute le plan relu, pas un plan recalculé sur une base qui a bougé."""
    simulation = tmp_path / "simulation.json"
    simulation.write_text(runner.invoke(app, ["reconcile-athletes", "--json"]).stdout)
    db_session.add(Athlete(nom="DURAND", prenom="Paul", homonym_rank=0))
    db_session.add(Athlete(nom="DURAND", prenom="Paul", homonym_rank=1))
    db_session.commit()

    result = runner.invoke(app, [
        "reconcile-athletes", "--yes", "--by-email", "admin@exemple.fr", "--plan-from", str(simulation), "--json",
    ])

    assert result.exit_code == 0
    body = json.loads(result.stdout)
    assert body["operations"] == json.loads(simulation.read_text())["operations"]
    assert db_session.query(Athlete).filter_by(nom="DURAND").count() == 2


@pytest.mark.parametrize("content", ["pas du json", '{"applied": true, "operations": []}', "{}"])
def test_plan_from_refuses_anything_but_a_simulation(db_session, doublons, tmp_path, content):
    simulation = tmp_path / "simulation.json"
    simulation.write_text(content)

    result = runner.invoke(app, [
        "reconcile-athletes", "--yes", "--by-email", "admin@exemple.fr", "--plan-from", str(simulation),
    ])

    assert result.exit_code == 2
    assert db_session.query(Athlete).count() == 3


def test_plan_from_needs_yes(db_session, doublons, tmp_path):
    simulation = tmp_path / "simulation.json"
    simulation.write_text(runner.invoke(app, ["reconcile-athletes", "--json"]).stdout)

    result = runner.invoke(app, ["reconcile-athletes", "--plan-from", str(simulation)])

    assert result.exit_code == 2


def test_progress_goes_to_stderr_unless_disabled(db_session, doublons):
    shown = runner.invoke(app, ["reconcile-athletes", "--yes", "--by-email", "admin@exemple.fr", "--json"])
    json.loads(shown.stdout)
    assert "2/2 opérations" in shown.stderr

    silent = runner.invoke(app, ["reconcile-athletes", "--json", "--no-progress"])
    assert "Mêmes clés" not in silent.stderr


def test_an_interruption_while_planning_exits_130(db_session, doublons, monkeypatch):
    def interrupted(db, *, progress=None):
        raise KeyboardInterrupt

    monkeypatch.setattr(athlete_reconciliation, "plan", interrupted)

    result = runner.invoke(app, ["reconcile-athletes", "--json"])

    assert result.exit_code == 130
    assert json.loads(result.stdout)["interrupted"] is True
