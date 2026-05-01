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
from backend.core import models, models_audit  # noqa: F401
from backend.modules.accounting import models as accounting_models  # noqa: F401
from backend.modules.group import models as group_models  # noqa: F401
from backend.modules.group import models_finance as group_finance_models  # noqa: F401
from backend.modules.group import models_governance as group_governance_models  # noqa: F401
from backend.modules.group import models_partner as group_partner_models  # noqa: F401
from backend.modules.hr import models as hr_models  # noqa: F401
from backend.modules.inventory import models as inventory_models  # noqa: F401
from backend.modules.inventory import models_advanced as inventory_advanced_models  # noqa: F401
from backend.modules.inventory import models_count as inventory_count_models  # noqa: F401
from backend.modules.mfg import models as mfg_models  # noqa: F401
from backend.modules.mfg import models_advanced as mfg_advanced_models  # noqa: F401
from backend.modules.ops import models as ops_models  # noqa: F401
from backend.modules.outbound import models as outbound_models  # noqa: F401
from backend.modules.purchase import models as purchase_models  # noqa: F401
from backend.modules.purchase import models_advanced as purchase_advanced_models  # noqa: F401
from backend.modules.quality import models as quality_models  # noqa: F401
from backend.modules.sales import models as sales_models  # noqa: F401
from backend.modules.sales import models_advanced as sales_advanced_models  # noqa: F401
from backend.modules.wms import models as wms_models  # noqa: F401
from backend.modules.wms import models_outbound as wms_outbound_models  # noqa: F401

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
        connection.commit()  # commit schema creation before the migration's own tx
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
