"""
Vérifie que la chaîne Alembic s'applique de bout en bout sur une base vierge.

Les fixtures de test construisent le schéma via `Base.metadata.create_all` : sans
ce test, une migration qui dépend du modèle ORM courant peut casser
`alembic upgrade head` (et donc `scripts/reset_db.py`, la CI, tout nouveau
déploiement) sans qu'aucun test ne s'en aperçoive.
"""
import logging
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

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


def test_upgrade_ne_desactive_pas_les_loggers_existants(sqlite_url):
    """`alembic/env.py` ne doit pas éteindre les loggers déjà enregistrés.

    `fileConfig()` désactive par défaut tout logger absent de `alembic.ini`
    (`disable_existing_loggers=True`). Sans garde-fou, exécuter une migration
    dans la même suite coupe silencieusement les loggers applicatifs (`app.*`).
    """
    logger = logging.getLogger("app.services.import_service")
    original_disabled = logger.disabled
    logger.disabled = False
    try:
        command.upgrade(_alembic_config(), "head")
        assert not logging.getLogger("app.services.import_service").disabled
    finally:
        logger.disabled = original_disabled


def _tables(url: str) -> set[str]:
    engine = sa.create_engine(url)
    try:
        return set(sa.inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_les_tables_d_authentification_sont_creees(sqlite_url):
    command.upgrade(_alembic_config(), "head")
    assert {"users", "identities", "user_sessions"} <= _tables(sqlite_url)


def test_users_ne_porte_aucune_colonne_de_role(sqlite_url):
    """FR-041 / SC-014, vérifié sur le **schéma appliqué**, pas sur le modèle.

    Le rôle de #115 est relatif à une organisation et vivra dans une
    association ; un scalaire posé ici serait à défaire par une migration
    destructive.
    """
    command.upgrade(_alembic_config(), "head")
    assert not {nom for nom in _columns(sqlite_url, "users") if "role" in nom}


def test_downgrade_puis_upgrade_des_tables_d_authentification(sqlite_url):
    """Cycle complet : les contraintes nommées rendent la descente déterministe.

    La cible de descente est **nommée** et non relative (`-1`) : la prochaine
    migration ajoutée décalerait un `-1`, qui descendrait alors autre chose sans
    que l'assertion cesse pour autant de passer.
    """
    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    command.downgrade(cfg, "c3d4e5f6a7b8")  # révision précédant le socle d'auth
    assert not {"users", "identities", "user_sessions"} & _tables(sqlite_url)

    command.upgrade(cfg, "head")
    assert {"users", "identities", "user_sessions"} <= _tables(sqlite_url)


def test_downgrade_puis_upgrade_de_l_indice_de_fiabilite(sqlite_url):
    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    # Cible nommée : `-1` désignait l'indice de fiabilité tant qu'il était en
    # tête, mais toute migration ajoutée depuis le décale (le socle d'auth l'a
    # fait) — l'assertion se serait alors mise à éprouver autre chose.
    command.downgrade(cfg, "b2c3d4e5f6a7")
    assert not {"is_reliable", "quality_issues"} & _columns(sqlite_url, "courses")

    command.upgrade(cfg, "head")
    assert {"is_reliable", "quality_issues"} <= _columns(sqlite_url, "courses")
