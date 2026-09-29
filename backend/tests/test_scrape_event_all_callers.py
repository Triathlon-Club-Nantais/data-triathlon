"""Tout appelant du dispatcher déballe `(results, trace)` (#1016).

Le dispatcher `registry.scrape_event_all` rend un couple depuis #1016. Les tests
réseau (`test_integration_scrapers.py`, hebdomadaires via `scraper-drift.yml`) et
`scripts/audit_scrapers.py` ne tournent pas dans la suite unitaire : un appelant
resté sur l'ancienne forme n'y échouerait qu'en production du rapport de dérive.
Ce garde statique lit leur source sans rien exécuter.
"""
import ast
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
DISPATCHER_NAMES = {"scrape_event_all", "registry_scrape_event_all"}


def _is_dispatcher_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return (
            func.attr == "scrape_event_all"
            and isinstance(func.value, ast.Name)
            and func.value.id == "registry"
        )
    return isinstance(func, ast.Name) and func.id == "registry_scrape_event_all"


def _single_name_assignments(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and _is_dispatcher_call(node.value)
        and not all(isinstance(target, ast.Tuple) for target in node.targets)
    ]


@pytest.mark.parametrize(
    "relative",
    [
        "tests/test_integration_scrapers.py",
        "scripts/audit_scrapers.py",
    ],
)
def test_dispatcher_results_are_unpacked_with_their_trace(relative):
    assert _single_name_assignments(BACKEND / relative) == []
