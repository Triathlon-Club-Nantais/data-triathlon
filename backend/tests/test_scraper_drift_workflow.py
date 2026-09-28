"""Invariants du workflow de veille des scrapers (#958).

Les tests `integration` appellent les vrais fournisseurs : ils tournent sur un
calendrier, jamais sur une PR, séquentiellement, et un échec ouvre une issue au
lieu de se perdre dans l'onglet Actions.
"""
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "scraper-drift.yml"


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _triggers(workflow: dict) -> dict:
    # PyYAML lit la clé nue `on` comme le booléen True.
    return workflow.get("on", workflow.get(True))


def _runs(workflow: dict) -> list[str]:
    return [step["run"] for job in workflow["jobs"].values() for step in job["steps"] if "run" in step]


def test_it_runs_on_a_schedule_and_on_demand_but_never_on_a_pull_request(workflow):
    triggers = _triggers(workflow)

    assert set(triggers) == {"schedule", "workflow_dispatch"}


def test_it_runs_the_integration_suite_sequentially(workflow):
    commandes = [run for run in _runs(workflow) if "pytest" in run]

    assert commandes and all("-m integration" in run and "-n 0" in run for run in commandes)


def test_it_only_asks_for_the_permissions_it_uses(workflow):
    assert workflow["permissions"] == {"contents": "read", "issues": "write"}


def test_every_job_is_bounded_in_time(workflow):
    assert all("timeout-minutes" in job for job in workflow["jobs"].values())


def test_a_failure_opens_or_updates_the_drift_issue(workflow):
    etapes = [step for job in workflow["jobs"].values() for step in job["steps"]]
    signalement = [step for step in etapes if step.get("if") == "failure()"]

    assert signalement and "gh issue" in signalement[0]["run"]
