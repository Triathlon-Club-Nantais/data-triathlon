"""Module names are identifiers too (Principle I, #1560): the #88 re-scan walks
the AST and never sees file names, so this guard covers them."""

from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def test_no_app_module_is_named_after_benevole():
    offenders = sorted(
        str(path.relative_to(APP_DIR)) for path in APP_DIR.rglob("*.py") if "benevol" in path.stem.lower()
    )
    assert offenders == []
