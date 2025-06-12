#!/usr/bin/env python3
"""
Database Connection Test Script for Auth Service - Pytest Version

This script tests database connections to both direct PostgreSQL and via pgBouncer
to validate that the connection configuration works properly in all environments.
"""
import asyncio
import logging
import os
import sys
from datetime import datetime

import pytest

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("db_test")

try:
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
except ImportError:
    logger.error("Required dependencies not installed. Run: pip install sqlalchemy")
    sys.exit(1)


@pytest.fixture
def direct_db_url():
    """Fixture for direct PostgreSQL connection URL"""
    return os.environ.get(
        "AUTH_SERVICE_DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@supabase_db_paservices:5432/postgres",
    )


@pytest.fixture
def pgbouncer_url():
    """Fixture for pgBouncer connection URL"""
    url = os.environ.get(
        "AUTH_SERVICE_PGBOUNCER_URL",
        "postgresql+psycopg://postgres:postgres@supabase_db_paservices:5432/postgres",
    )

    # Remove pgbouncer parameter from URL if present
    if "?pgbouncer=true" in url:
        url = url.replace("?pgbouncer=true", "")
    elif "&pgbouncer=true" in url:
        url = url.replace("&pgbouncer=true", "")

    return url


@pytest.mark.asyncio
async def test_direct_connection(direct_db_url):
    """Test direct PostgreSQL connection"""
    result = await _test_connection(
        direct_db_url, "Direct PostgreSQL", use_pgbouncer=False
    )
    assert result is True


@pytest.mark.asyncio
async def test_pgbouncer_connection(pgbouncer_url):
    """Test pgBouncer connection"""
    result = await _test_connection(
        pgbouncer_url, "PostgreSQL via pgBouncer", use_pgbouncer=True
    )
    assert result is True


async def _test_connection(url, description, use_pgbouncer=False):
    """Test a database connection with detailed output"""
    logger.info(f"Testing connection to {description}")

    # Sanitize URL for display (hide password)
    display_url = url
    if "@" in url:
        prefix, rest = url.split("@", 1)
        if ":" in prefix:
            user_part = prefix.split(":")[0]
            display_url = f"{user_part}:***@{rest}"

    logger.info(f"URL: {display_url}")

    # Configure connection args for pgBouncer compatibility
    connect_args = {}
    if use_pgbouncer:
        logger.info("Configuring for pgBouncer compatibility")
        # Use proper raw string for escaping
        connect_args["options"] = (
            r"-c standard_conforming_strings=on -c client_encoding=utf8 -c plan_cache_mode=force_custom_plan -c statement_timeout=0 -c default_transaction_isolation=read\ committed"
        )

    try:
        # Create engine with appropriate settings
        engine = create_async_engine(url, connect_args=connect_args, echo=False)

        # Create session
        async_session = async_sessionmaker(
            engine, expire_on_commit=False, class_=AsyncSession
        )

        # Test with multiple queries to verify connection works consistently
        async with async_session() as session:
            # Run basic diagnostic query
            result = await session.execute(
                text("SELECT current_database(), current_user, version()")
            )
            db_info = result.first()
            logger.info(f"Connected to database: {db_info[0]} as user: {db_info[1]}")
            logger.info(f"PostgreSQL version: {db_info[2]}")

            # Run query that would typically use prepared statements
            logger.info("Running parameterized query test")
            for i in range(3):
                # When using pgBouncer, we use a different approach to parameters to avoid prepared statements
                if use_pgbouncer:
                    # Use inline string formatting for pgBouncer connections - not optimal but works with pgBouncer
                    # This is safe only because we control the parameter values completely
                    formatted_query = text(f"SELECT 'Test value {i}' AS result")
                    result = await session.execute(formatted_query)
                else:
                    # Use proper parameterized queries for direct connections
                    result = await session.execute(
                        text("SELECT :test_param AS result"),
                        {"test_param": f"Test value {i}"},
                    )
                value = result.scalar()
                logger.info(f"  Query {i+1} result: {value}")

            logger.info(f"✅ Connection to {description} successful")
            return True

    except SQLAlchemyError as e:
        logger.error(f"❌ Connection failed: {type(e).__name__}: {str(e)}")
        return False
    finally:
        if "engine" in locals():
            await engine.dispose()
