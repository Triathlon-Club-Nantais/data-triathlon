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
    assert {"is_reliable_computed", "reliability_override", "quality_issues"} <= _columns(
        sqlite_url, "courses"
    )
    # `is_reliable` est une **propriété** de l'ORM depuis #115, jamais une
    # colonne : la voir reparaître ici signalerait un `add_column` de trop.
    assert "is_reliable" not in _columns(sqlite_url, "courses")


def test_upgrade_head_creates_the_group_tables(sqlite_url):
    """#197 — les deux tables, et surtout ce qu'elles **ne** portent pas.

    Les absences sont assertées plutôt que supposées : un `is_superuser` sur
    `groups` ferait entrer un groupe dans la décision d'accès (FR-017), et un
    `organisation_id` sur `user_groups` rendrait représentable une appartenance
    dont le club contredit celui du groupe.
    """
    command.upgrade(_alembic_config(), "head")

    assert _columns(sqlite_url, "groups") == {
        "id",
        "organisation_id",
        "slug",
        "name",
        "description",
        "created_at",
    }
    assert _columns(sqlite_url, "user_groups") == {
        "id",
        "user_id",
        "group_id",
        "joined_at",
    }


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
    assert not {"is_reliable", "is_reliable_computed", "quality_issues"} & _columns(
        sqlite_url, "courses"
    )

    command.upgrade(cfg, "head")
    assert {"is_reliable_computed", "reliability_override", "quality_issues"} <= _columns(
        sqlite_url, "courses"
    )


def test_les_tables_du_rbac_sont_creees(sqlite_url):
    command.upgrade(_alembic_config(), "head")
    assert {
        "organisations",
        "roles",
        "role_permissions",
        "user_roles",
    } <= _tables(sqlite_url)


def _lignes(url: str, requete: str) -> list[tuple]:
    engine = sa.create_engine(url)
    try:
        with engine.connect() as connexion:
            return [tuple(ligne) for ligne in connexion.execute(sa.text(requete))]
    finally:
        engine.dispose()


def test_la_migration_seme_exactement_trois_roles_systeme(sqlite_url):
    """FR-041 — et ce semis ne se rejoue **jamais**.

    Aucune migration ultérieure ne doit recomposer ces trois lignes : leur
    composition devient une donnée d'exploitation dès la première édition à
    chaud, et une migration qui la réécrirait effacerait une décision humaine
    sans laisser de trace. Ce test verrouille le **seul** semis autorisé.
    """
    command.upgrade(_alembic_config(), "head")

    roles = _lignes(
        sqlite_url,
        "SELECT slug, is_system, is_superuser, organisation_id FROM roles ORDER BY slug",
    )

    assert [ligne[0] for ligne in roles] == ["admin", "moderator", "validator"]
    assert all(ligne[1] for ligne in roles), "un rôle semé n'est pas is_system"
    assert all(ligne[3] is None for ligne in roles), "un rôle semé n'est pas global"


def test_admin_est_le_seul_superutilisateur_et_ne_porte_aucun_code(sqlite_url):
    """`is_superuser` franchit tout pouvoir, **y compris ceux pas encore écrits**.

    Lui coller les neuf codes du jour le figerait au jour d'aujourd'hui — c'est
    exactement ce que ce booléen évite (FR-014).
    """
    command.upgrade(_alembic_config(), "head")

    superutilisateurs = _lignes(sqlite_url, "SELECT slug FROM roles WHERE is_superuser")
    assert superutilisateurs == [("admin",)]

    codes_admin = _lignes(
        sqlite_url,
        "SELECT permission_code FROM role_permissions"
        " JOIN roles ON roles.id = role_permissions.role_id WHERE roles.slug = 'admin'",
    )
    assert codes_admin == []


def test_moderator_porte_ses_deux_codes_couples(sqlite_url):
    """Instruire un signalement sans pouvoir lire la liste n'a pas de sens.

    C'est la raison d'être du semis de ce rôle : l'oubli du pouvoir de lecture
    est le bug attendu d'une composition à la main.
    """
    command.upgrade(_alembic_config(), "head")

    codes = _lignes(
        sqlite_url,
        "SELECT permission_code FROM role_permissions"
        " JOIN roles ON roles.id = role_permissions.role_id"
        " WHERE roles.slug = 'moderator' ORDER BY permission_code",
    )

    assert codes == [("pending_providers:handle",), ("pending_providers:read",)]


def test_validator_porte_le_seul_pouvoir_de_qualite(sqlite_url):
    command.upgrade(_alembic_config(), "head")

    codes = _lignes(
        sqlite_url,
        "SELECT permission_code FROM role_permissions"
        " JOIN roles ON roles.id = role_permissions.role_id WHERE roles.slug = 'validator'",
    )

    assert codes == [("quality:override",)]


def test_l_organisation_du_club_est_semee(sqlite_url):
    """`user_roles.organisation_id` est non nul : sans elle, aucune attribution."""
    command.upgrade(_alembic_config(), "head")

    assert _lignes(sqlite_url, "SELECT slug FROM organisations") == [("tcn",)]


def test_le_renommage_de_is_reliable_conserve_les_donnees(sqlite_url):
    """`alter_column`, pas `drop`/`add` — le verdict calculé survit à la montée.

    C'est le seul point de cette révision qui porte des données en place, et
    celui qu'un `drop_column`/`add_column` aurait perdu sans bruit.
    """
    cfg = _alembic_config()
    command.upgrade(cfg, "d5e6f7a8b9c0")  # révision précédant le RBAC

    engine = sa.create_engine(sqlite_url)
    try:
        with engine.begin() as connexion:
            connexion.execute(
                sa.text(
                    "INSERT INTO courses (name, source_url, provider, event_type,"
                    " is_relay, is_reliable, scraped_at, created_at)"
                    " VALUES ('Épreuve', '', '', '', 0, 1, '2026-01-01', '2026-01-01')"
                )
            )
    finally:
        engine.dispose()

    command.upgrade(cfg, "head")

    assert _lignes(sqlite_url, "SELECT is_reliable_computed, reliability_override FROM courses") == [
        (1, None)
    ]


def test_downgrade_puis_upgrade_du_rbac(sqlite_url):
    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    command.downgrade(cfg, "d5e6f7a8b9c0")
    assert not {"organisations", "roles", "role_permissions", "user_roles"} & _tables(
        sqlite_url
    )
    assert "is_reliable" in _columns(sqlite_url, "courses")

    command.upgrade(cfg, "head")
    assert {"organisations", "roles", "role_permissions", "user_roles"} <= _tables(
        sqlite_url
    )
