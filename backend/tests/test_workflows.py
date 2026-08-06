"""Invariants du workflow de batch (#47) — il détient la base de production.

Un méta-test, sur le patron de `test_core_http.py` : il ne teste pas du code
applicatif mais une **règle qui se perd à la modification suivante** si rien ne
la tient.

Pourquoi un test et non un `grep` : `grep 'run:' -A 5 | grep 'inputs\\.'` marque
en faute le bloc `env:` qui suit `run:`, c'est-à-dire précisément la forme
correcte. Le YAML lu, lui, distingue sans ambiguïté un script d'une variable
d'environnement.
"""
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "batch.yml"


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _scripts(workflow: dict) -> list[tuple[str, str]]:
    """(nom d'étape, script) pour chaque `run:` du workflow."""
    scripts = []
    for job_name, job in workflow["jobs"].items():
        for index, step in enumerate(job.get("steps", [])):
            if "run" in step:
                scripts.append((step.get("name", f"{job_name}[{index}]"), step["run"]))
    return scripts


def test_no_input_interpolated_into_a_script(workflow):
    """Aucune entrée du workflow n'atteint un script shell par substitution.

    `${{ inputs.x }}` écrit dans un `run:` est remplacé **avant** l'exécution du
    shell : une valeur portant `"; curl … | sh #` s'exécuterait avec l'accès à
    la base de production. Or ces valeurs viennent d'un fichier téléversé par un
    humain. Les entrées passent donc par `env:`, et le script ne lit que des
    variables citées.
    """
    fautifs = [
        nom
        for nom, script in _scripts(workflow)
        if "${{ inputs." in script or "${{ github.event.inputs." in script
    ]
    assert not fautifs, (
        f"Entrée interpolée dans un script : {fautifs}. "
        "La passer par `env:` et la lire citée (\"$VAR\")."
    )


def test_concurrency_forbids_two_batches_at_once(workflow):
    """Le verrou réel de FR-004 — le refus 409 de l'API ne le remplace pas.

    Ce dernier ne voit ni un lancement fait depuis l'onglet Actions, ni une
    occurrence planifiée.
    """
    assert workflow["concurrency"]["group"] == "batch"
    assert workflow["concurrency"]["cancel-in-progress"] is False


def test_job_cannot_hang_forever(workflow):
    """Sans borne, une exécution coincée gèle tout lancement six heures durant."""
    for job in workflow["jobs"].values():
        assert 0 < job["timeout-minutes"] <= 120
