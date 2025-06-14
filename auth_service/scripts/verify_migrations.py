#!/usr/bin/env python
"""
Verify database migrations script.

This script verifies that the actual database schema matches what is expected
based on SQLAlchemy models. It helps detect inconsistencies between Alembic
migration records and the actual database state.

Usage:
    python -m scripts.verify_migrations

Or directly:
    ./scripts/verify_migrations.py
"""

import asyncio
import logging
import sys
from typing import Any, Dict, List, Set, Tuple

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql import sqltypes

# Import settings and Base
sys.path.append("/app")
from auth_service.config.settings import settings
from auth_service.db import Base

# Import all models to ensure they're registered with Base.metadata
from auth_service.models.app_client import AppClient
from auth_service.models.app_client_role import AppClientRole
from auth_service.models.profile import Profile
from auth_service.models.role import Role

# Import any other models here

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("migration_verification")


async def verify_migrations() -> bool:
    """Verify that the actual database schema matches the expected schema from SQLAlchemy models."""
    url = settings.database_url
    engine = create_async_engine(url)

    try:
        expected_tables, expected_columns = get_expected_schema_from_models()
        actual_tables, actual_columns = await get_actual_schema_from_db(engine)

        # Verify tables
        missing_tables = expected_tables - actual_tables
        if missing_tables:
            logger.error(f"Missing tables in database: {missing_tables}")
            return False

        # Verify columns
        schema_issues = []
        for table_name, expected_cols in expected_columns.items():
            if table_name not in actual_columns:
                continue  # Already reported as missing table

            actual_cols = actual_columns[table_name]
            missing_columns = expected_cols - actual_cols

            if missing_columns:
                schema_issues.append(
                    f"Table '{table_name}' is missing columns: {missing_columns}"
                )

        if schema_issues:
            for issue in schema_issues:
                logger.error(issue)
            return False

        logger.info(
            "✅ Database schema verification passed - all expected tables and columns exist"
        )
        return True

    except Exception as e:
        logger.error(f"Error verifying migrations: {e}")
        return False
    finally:
        await engine.dispose()


def get_expected_schema_from_models() -> Tuple[Set[str], Dict[str, Set[str]]]:
    """Extract expected schema information from SQLAlchemy models."""
    tables = set()
    columns = {}

    for table_name, table in Base.metadata.tables.items():
        # Skip auth schema tables that might be managed by Supabase
        if table_name.startswith("auth."):
            continue

        # For tables with schema, use just the table name for comparison
        if "." in table_name:
            simple_name = table_name.split(".")[-1]
        else:
            simple_name = table_name

        tables.add(simple_name)
        columns[simple_name] = set(column.name for column in table.columns)

    return tables, columns


async def get_actual_schema_from_db(engine) -> Tuple[Set[str], Dict[str, Set[str]]]:
    """Extract actual schema information from the database."""
    tables = set()
    columns = {}

    async with engine.connect() as conn:
        # Get all tables in the public schema
        result = await conn.execute(
            text(
                """SELECT table_name FROM information_schema.tables 
               WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"""
            )
        )

        for row in result:
            table_name = row[0]
            tables.add(table_name)

            # Get columns for this table
            col_result = await conn.execute(
                text(
                    """SELECT column_name FROM information_schema.columns 
                   WHERE table_schema = 'public' AND table_name = :table_name"""
                ),
                {"table_name": table_name},
            )

            columns[table_name] = set(row[0] for row in col_result)

    return tables, columns


def colored(text: str, color: str) -> str:
    """Apply ANSI color to text for terminal output."""
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "reset": "\033[0m",
    }
    return f"{colors.get(color, '')}{text}{colors['reset']}"


async def main() -> None:
    """Main entry point for the script."""
    print(colored("\n===== DATABASE MIGRATION VERIFICATION =====\n", "yellow"))
    success = await verify_migrations()

    if success:
        print(colored("\n✅ All migrations have been correctly applied!\n", "green"))
        sys.exit(0)
    else:
        print(colored("\n❌ Migration verification failed! See errors above.\n", "red"))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
