"""
Test fumée de la chaîne Alembic, resté dans la boucle locale.

Le reste de `test_migrations.py` porte le marqueur `migrations` et n'est lancé
qu'avec `--migrations` (CI, branche touchant `alembic/` ou `models/`).
"""
from alembic import command

from tests.test_migrations import _alembic_config, _columns, sqlite_url  # noqa: F401, F811


def test_upgrade_head_sur_base_vierge(sqlite_url):  # noqa: F811
    command.upgrade(_alembic_config(), "head")
    assert {"is_reliable_computed", "reliability_override", "quality_issues"} <= _columns(
        sqlite_url, "courses"
    )
    # `is_reliable` est une **propriété** de l'ORM depuis #115, jamais une
    # colonne : la voir reparaître ici signalerait un `add_column` de trop.
    assert "is_reliable" not in _columns(sqlite_url, "courses")
