"""Principe II : seuls les repositories construisent des requêtes sur la Session (#1018)."""
import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
_QUERY_METHODS = {"query", "execute", "scalar", "scalars", "get", "delete"}
_SESSION_NAMES = {"db", "session"}
# Le socle qui fabrique la Session n'est pas une couche applicative.
_ALLOWED = {APP_ROOT / "repositories", APP_ROOT / "core" / "database.py"}


def _is_allowed(path: Path) -> bool:
    return any(path == allowed or allowed in path.parents for allowed in _ALLOWED)


def test_no_session_query_outside_repositories():
    offenders = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        if _is_allowed(path):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in _QUERY_METHODS
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in _SESSION_NAMES
            ):
                offenders.append(f"{path.relative_to(APP_ROOT)}:{node.lineno}")
    assert offenders == []
