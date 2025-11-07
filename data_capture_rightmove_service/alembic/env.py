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

# models. The Dockerfile sets PYTHONPATH=/app/src, which means we can import the package directly.
# Import all model modules here to ensure they are registered with
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

# Set target_metadata to our SQLAlchemy Base.metadata for autogenerate support
target_metadata = Base.metadata
default_schema = target_metadata.schema
schemas_to_include = {default_schema} if default_schema else None


def _object_schema(obj):
    """Best-effort schema detection for SQLAlchemy schema items."""
    if hasattr(obj, "schema") and obj.schema:
        return obj.schema
    metadata = getattr(obj, "metadata", None)
    if metadata is not None and getattr(metadata, "schema", None):
        return metadata.schema
    table = getattr(obj, "table", None)
    if table is not None and getattr(table, "schema", None):
        return table.schema
    parent = getattr(obj, "parent", None)
    if parent is not None and getattr(parent, "schema", None):
        return parent.schema
    return None


def include_object(object_, name, type_, reflected, compare_to):
    """
    Limit autogenerate to objects inside the managed schema.
    """
    schema_allowed = True
    if schemas_to_include:
        if type_ == "schema":
            return name in schemas_to_include
        schema = _object_schema(object_)
        if schema is None:
            schema_allowed = not reflected
        else:
            schema_allowed = schema in schemas_to_include
    if not schema_allowed:
        return False
    if type_ == "index" and reflected:
        # Skip comparing indexes that already exist in the database to avoid noisy renames
        return False
    return True


def include_name(name, type_, parent_names):
    """Prevent Alembic from reflecting schemas we don't own."""
    if not schemas_to_include:
        return True
    if type_ == "schema":
        return name in schemas_to_include if name is not None else False
    schema = parent_names.get("schema_name")
    if schema is None:
        return False
    return schema in schemas_to_include


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,  # Required for schema support
        include_name=include_name,
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
        include_name=include_name,
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
