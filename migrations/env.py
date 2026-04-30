"""Alembic env — uses sync psycopg driver against the configured database.

We import the metadata via ``backend.core.db.Base`` and let it discover all
mapped models by importing the modules that define them.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from backend.config import get_settings
from backend.core.db import SCHEMAS, Base

# Import every module that declares ORM models so they register on the
# shared metadata before autogenerate runs.
from backend.core import models  # noqa: F401
from backend.modules.inventory import models as inventory_models  # noqa: F401
from backend.modules.wms import models as wms_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def include_object(object_, name, type_, reflected, compare_to):
    """Restrict autogenerate to schemas we own."""
    if type_ == "schema":
        return name in SCHEMAS
    return True


def _ensure_schemas(connection) -> None:
    for schema in SCHEMAS:
        connection.exec_driver_sql(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_object=include_object,
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
        _ensure_schemas(connection)
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
