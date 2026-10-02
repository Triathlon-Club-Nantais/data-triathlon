"""Environnement Alembic — branché sur Settings et Base.metadata de l'application."""
import importlib
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, make_url, pool

from app.core.config import get_settings
from app.core.database import Base

# Chargement pour l'effet de bord seul : le package `app.models` enregistre toutes
# les tables sur `Base.metadata`, dont `--autogenerate` se sert pour comparer le
# modèle au schéma en base. Aucun symbole n'en est utilisé ici, d'où l'appel
# explicite plutôt qu'un `import app.models` que tout détecteur d'import inutilisé
# (ruff F401, CodeQL py/unused-import) signale.
importlib.import_module("app.models")

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# PostgreSQL réécrit l'expression de ces index dans son catalogue (casts, `TRIM(BOTH
# FROM ...)`) : la comparaison textuelle d'Alembic ne converge jamais (#1023).
# PostgreSQL relit `last_name_key || first_name_key` avec des casts `::text` qu'Alembic ne
# sait pas dépouiller symétriquement : comparés, ces index paraîtraient toujours à recréer.
_UNCOMPARABLE_EXPRESSION_INDEXES = {
    "ix_participations_club_normalized",
    "ix_athletes_identity_last_first",
    "ix_athletes_identity_first_last",
}
# Déclarés au modèle avec `ddl_if(dialect="postgresql")` : absents ailleurs, à dessein.
_POSTGRESQL_ONLY_INDEXES = {"ix_courses_name_trgm"}
_IS_POSTGRESQL = make_url(get_settings().database_url).get_backend_name() == "postgresql"


def include_object(object_, name, type_, reflected, compare_to) -> bool:
    if type_ != "index":
        return True
    if name in _UNCOMPARABLE_EXPRESSION_INDEXES:
        return False
    return _IS_POSTGRESQL or name not in _POSTGRESQL_ONLY_INDEXES


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # nécessaire pour ALTER sous SQLite
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
