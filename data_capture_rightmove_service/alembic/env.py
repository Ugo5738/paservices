"""
Alembic environment module for database migrations.
"""

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# models. The Dockerfile sets PYTHONPATH=/app/src, which means we can import
# the package directly.
# We import all model modules here to ensure they are registered with
# SQLAlchemy's metadata before 'autogenerate' runs.
from data_capture_rightmove_service.config import settings
from data_capture_rightmove_service.db import Base

# The 'noqa' comments prevent linters from complaining about an unused wildcard import.
from data_capture_rightmove_service.models import *  # noqa: F401, F403

# --- Alembic Config ---
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", str(settings.DATABASE_URL))

# add model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    """
    Tells Alembic to only pay attention to objects within our 'rightmove' schema.
    This prevents it from trying to manage tables in other schemas (e.g., 'public').
    """
    if type_ == "table" and object.schema != target_metadata.schema:
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,  # Required for schema support
        include_object=include_object,  # Use our schema filter
        compare_type=True,  # Compare column types
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Run the actual migrations within a connection context."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,  # Required for schema support
        include_object=include_object,  # Use our schema filter
        compare_type=True,  # Compare column types
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine and associate a connection with the context."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
