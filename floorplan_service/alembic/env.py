"""
Alembic environment module for database migrations.
"""

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# --- Path Setup for Alembic ---
# This ensures that Alembic can find all the necessary modules from both
# the service's `src` directory and the project's shared `shared` directory.
service_dir = Path(__file__).parent.parent.absolute()
project_root = service_dir.parent

# Add the service's own source code to the path
sys.path.insert(0, str(service_dir / "src"))
# Add the shared library to the path
sys.path.insert(0, str(project_root))

# Now we can safely import our project's modules
from floorplan_service.config import settings
from floorplan_service.db import Base

# Import all models to ensure they're registered with Base.metadata
from floorplan_service.models import *

# --- Alembic Configuration ---
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
    """Return the schema for the given SQLAlchemy object."""
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
    """Limit autogenerate to the schemas we manage (floorplan)."""
    if type_ == "schema":
        if not schemas_to_include:
            return True
        return name in schemas_to_include
    schema = _object_schema(object_)
    if not schemas_to_include:
        return True
    if schema is None:
        # Exclude reflected public objects so we don't diff Supabase system tables
        return not reflected
    return schema in schemas_to_include


def include_name(name, type_, parent_names):
    """Prevent Alembic from even reflecting schemas we don't own."""
    if not schemas_to_include:
        return True
    if type_ == "schema":
        return name in schemas_to_include
    schema = parent_names.get("schema_name")
    if schema is None:
        return False
    return schema in schemas_to_include


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = create_async_engine(settings.DATABASE_URL)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_name=include_name,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
