"""
Vérifie que la chaîne Alembic s'applique de bout en bout sur une base vierge.

Les fixtures de test construisent le schéma via `Base.metadata.create_all` : sans
ce test, une migration qui dépend du modèle ORM courant peut casser
`alembic upgrade head` (et donc `scripts/reset_db.py`, la CI, tout nouveau
déploiement) sans qu'aucun test ne s'en aperçoive.
"""
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from app.core.config import get_settings

BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def sqlite_url(tmp_path, monkeypatch):
    """URL SQLite jetable, vue par `alembic/env.py` via `get_settings()`."""
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    yield url
    get_settings.cache_clear()


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return cfg


def _columns(url: str, table: str) -> set[str]:
    engine = sa.create_engine(url)
    try:
        return {c["name"] for c in sa.inspect(engine).get_columns(table)}
    finally:
        engine.dispose()


def test_upgrade_head_sur_base_vierge(sqlite_url):
    command.upgrade(_alembic_config(), "head")
    assert {"is_reliable", "quality_issues"} <= _columns(sqlite_url, "courses")


def test_downgrade_puis_upgrade_de_l_indice_de_fiabilite(sqlite_url):
    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    command.downgrade(cfg, "-1")
    assert not {"is_reliable", "quality_issues"} & _columns(sqlite_url, "courses")

    command.upgrade(cfg, "head")
    assert {"is_reliable", "quality_issues"} <= _columns(sqlite_url, "courses")
