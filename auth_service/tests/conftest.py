# auth_service/tests/conftest.py

pytest_plugins = "pytest_asyncio"

import asyncio
import inspect
import logging
import os
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Dict, Generator, Optional

import alembic
import alembic.config
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from auth_service.config import Settings
from auth_service.db import AsyncSessionLocal, Base
from auth_service.db import engine as db_engine
from auth_service.db import get_db
from auth_service.dependencies import get_app_settings
from auth_service.main import app as fastapi_app
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import TIMESTAMP, Boolean, Column, MetaData, String, Table, event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

# Set up logger for test diagnostics
logger = logging.getLogger("test_setup")
logger.setLevel(logging.DEBUG)

# Create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# Create formatter and add it to the handler
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)

# Add handler to logger
logger.addHandler(ch)
# alembic.command is not directly used in the new approach
import os  # To construct path to alembic.ini
import uuid
from unittest.mock import AsyncMock, MagicMock

from alembic import (
    context as alembic_global_context,  # For managing global alembic context
)
from alembic.config import Config as AlembicConfig
from alembic.runtime.environment import EnvironmentContext
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from auth_service.config import settings
from auth_service.db import Base
from auth_service.main import app
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

Table(
    "users",
    Base.metadata,
    Column("id", PGUUID(as_uuid=True), primary_key=True),
    Column("email", String(255), unique=True),
    Column("phone_number", String(255), unique=True, nullable=True),
    Column("username", String(255), unique=True, nullable=True),
    Column("password_hash", String(255), nullable=True),
    Column("first_name", String(255), nullable=True),
    Column("last_name", String(255), nullable=True),
    Column("is_active", Boolean, server_default=text("true")),
    Column("is_verified", Boolean, server_default=text("false")),
    Column("last_login_at", TIMESTAMP(timezone=True), nullable=True),
    Column(
        "created_at", TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    ),
    Column(
        "updated_at", TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    ),
    schema="auth",
    extend_existing=True,
)

# Test database configuration
# This approach prioritizes:
# 1. Explicit TEST_DATABASE_URL environment variable if provided
# 2. Creating a dedicated test database to avoid corrupting production data
# 3. Providing sensible defaults for different environments (local, CI, Docker)

# If a TEST_DATABASE_URL is explicitly defined in the environment, use that
if os.environ.get("TEST_DATABASE_URL"):
    TEST_DATABASE_URL = os.environ["TEST_DATABASE_URL"]
    logger.info(f"Using database URL from TEST_DATABASE_URL environment variable")

# For CI environments, use a standard configuration
elif os.environ.get("CI") == "true":
    TEST_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/auth_test_db"
    logger.info(f"Using CI database URL: {TEST_DATABASE_URL}")

# For Docker environments (when we can resolve the Docker service name)
else:
    base_db_url = settings.auth_service_database_url

    # Try to detect if we're in a Docker environment
    try:
        import socket
        from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

        socket.gethostbyname("supabase_db_paservices")

        # Parse the base URL to handle query parameters properly
        parsed_url = urlparse(base_db_url)

        # Extract query parameters
        query_params = parse_qs(parsed_url.query)

        # Remove problematic parameters that cause issues with migrations
        problematic_params = [
            "isolation_level",
            "default_transaction_isolation",
            "options",
        ]

        for param in problematic_params:
            if param in query_params:
                logger.info(f"Removing problematic parameter from test URL: {param}")
                del query_params[param]

        # Rebuild the query string
        clean_query = urlencode(query_params, doseq=True)

        # We're in Docker - use a dedicated test schema instead of the main one
        path = parsed_url.path
        if "postgres" in path:
            # Create a dedicated test database by replacing the DB name
            test_path = path.replace("/postgres", "/auth_test_db")
        else:
            # If using a different DB name, just append '_test'
            path_parts = path.split("/")
            path_parts[-1] = path_parts[-1] + "_test"
            test_path = "/".join(path_parts)

        # Reconstruct the URL with the test database and clean query params
        TEST_DATABASE_URL = urlunparse(
            (
                parsed_url.scheme,
                parsed_url.netloc,
                test_path,
                parsed_url.params,
                clean_query,
                parsed_url.fragment,
            )
        )

        logger.info(f"Using Docker test database URL (sanitized): {TEST_DATABASE_URL}")

    except socket.gaierror:
        # We're in local development - use localhost with proper credentials
        # Parse the base URL to handle query parameters properly
        parsed_url = urlparse(base_db_url)

        # Extract query parameters
        query_params = parse_qs(parsed_url.query)

        # Remove problematic parameters
        problematic_params = [
            "isolation_level",
            "default_transaction_isolation",
            "options",
        ]

        for param in problematic_params:
            if param in query_params:
                logger.info(f"Removing problematic parameter from test URL: {param}")
                del query_params[param]

        # Rebuild the query string
        clean_query = urlencode(query_params, doseq=True)

        # Replace hostname with localhost but keep everything else
        TEST_DATABASE_URL = urlunparse(
            (
                parsed_url.scheme,
                parsed_url.netloc.replace("supabase_db_paservices", "localhost"),
                parsed_url.path,
                parsed_url.params,
                clean_query,
                parsed_url.fragment,
            )
        )

        logger.info(f"Using local test database URL (sanitized): {TEST_DATABASE_URL}")

# Always log the database URL without credentials for security
redacted_url = TEST_DATABASE_URL
if "@" in redacted_url:
    # Redact the username:password part
    parts = redacted_url.split("@")
    protocol_creds = parts[0].split("://")
    redacted_url = f"{protocol_creds[0]}://****:****@{parts[1]}"

logger.info(f"Using test database: {redacted_url}")


# Determine the root directory of the project where alembic.ini is located
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALEMBIC_INI_PATH = os.path.join(PROJECT_ROOT, "alembic.ini")

# Use standard alembic migrations for tests
ALEMBIC_SCRIPT_LOCATION = os.path.join(PROJECT_ROOT, "alembic")
print(f"[CONFTEST] Using standard alembic migrations from: {ALEMBIC_SCRIPT_LOCATION}")

# Using standard alembic.ini but with dynamic config for test database
TEST_ALEMBIC_INI_CONTENT = """
[alembic]
script_location = %(here)s/alembic
prepend_sys_path = .
functions.migration_generator_function = 
version_path_separator = os

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = INFO
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stdout,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""

# Create a test-specific alembic.ini file
TEST_ALEMBIC_INI_PATH = os.path.join(PROJECT_ROOT, "test_alembic.ini")
with open(TEST_ALEMBIC_INI_PATH, "w") as f:
    f.write(TEST_ALEMBIC_INI_CONTENT)

# Use the test-specific alembic.ini
ALEMBIC_INI_PATH = TEST_ALEMBIC_INI_PATH
print(f"[CONFTEST] PROJECT_ROOT: {PROJECT_ROOT}")
print(f"[CONFTEST] ALEMBIC_INI_PATH: {ALEMBIC_INI_PATH}")
print(f"[CONFTEST] ALEMBIC_SCRIPT_LOCATION: {ALEMBIC_SCRIPT_LOCATION}")


# Helper function for alembic configuration, adapted from parts of alembic/env.py logic
def _include_object_for_conftest(object_item, name, type_, reflected, compare_to):
    """Filter function for Alembic to determine which database objects to include in migrations."""
    # For tables, include only those in public and auth schemas
    if type_ == "table":
        return object_item.schema in [None, "public", "auth"]
    # For schemas, include only public and auth
    elif type_ == "schema":
        return name in ["auth", "public"]
    return True


def _run_alembic_upgrade_sync(connection, config):
    """Run alembic upgrade head synchronously with proper error handling"""
    # Store the current engine context to restore later
    current_context = config.attributes.get("connection", None)

    try:
        # Configure alembic to use our connection
        config.attributes["connection"] = connection

        print("[ALEMBIC] Starting Alembic migrations")

        # Initialize the script directory with necessary arguments
        # This ensures compatibility with newer Alembic versions
        script = ScriptDirectory.from_config(config)

        # Run the migration with better error handling
        try:
            # Direct upgrade without using asyncio.run()
            # We use the synchronous command interface since we're within an async context
            # that already has an event loop running
            from alembic.command import upgrade as alembic_upgrade

            alembic_upgrade(config, "head")
            print("[ALEMBIC] Alembic migrations completed successfully")
        except Exception as migration_error:
            print(f"[ALEMBIC] Alembic migration error: {migration_error}")
            print("[ALEMBIC] Checking for available migrations...")

            # Add additional diagnostics
            try:
                # Get current revision - compatible with Alembic 1.16+
                migration_context = MigrationContext.configure(connection)
                current_rev = migration_context.get_current_revision()
                print(f"[ALEMBIC] Current database revision: {current_rev or 'None'}")
            except Exception as context_error:
                print(f"[ALEMBIC] Error getting current revision: {context_error}")

            # Re-raise the original error
            raise migration_error
    finally:
        # Restore the original connection or None
        config.attributes["connection"] = current_context
        print("[ALEMBIC] Connection context restored")


@pytest_asyncio.fixture(scope="session")
async def apply_migrations_to_test_db() -> None:
    """Apply migrations to the test database.

    This fixture runs at the session level and is responsible for setting up the database
    schema for the test run.
    """
    logger.info(f"Setting up test database using URL: {TEST_DATABASE_URL}")

    try:
        # Run our custom migration script that avoids the transaction isolation parameter issue
        import os
        import subprocess
        import urllib.parse
        from pathlib import Path

        # Setup common environment variables for both scripts
        env = os.environ.copy()
        env["DATABASE_URL"] = TEST_DATABASE_URL
        
        # Parse the database URL to extract actual host used by the test environment
        url_parts = urllib.parse.urlparse(TEST_DATABASE_URL)
        netloc_parts = url_parts.netloc.split('@')
        if len(netloc_parts) > 1:
            host_port = netloc_parts[1].split(':')[0]
            logger.info(f"Using host from TEST_DATABASE_URL: {host_port}")
            env["DB_HOST"] = host_port
        else:
            # Fallback to Docker container name for database host
            env["DB_HOST"] = "supabase_db_paservices"
            logger.info(f"Using supabase_db_paservices for database host")
        
        env["DB_PORT"] = "5432"
        env["DB_USER"] = "postgres"
        env["DB_PASSWORD"] = "postgres"
        env["DB_NAME"] = "auth_test_db"
        env["ALEMBIC_DIR"] = str(Path(PROJECT_ROOT) / "alembic")

        # STEP 1: First, set up the auth schema before running migrations
        # This is crucial because the profiles table has a foreign key to auth.users
        logger.info("STEP 1: Setting up auth schema for test database...")
        
        # Find the auth schema copy script
        project_root = Path(PROJECT_ROOT)
        if os.path.exists("/app"):  # Docker environment
            project_root = Path("/app")
        
        # Start by looking for copy_auth_schema.py in the proper scripts folder
        copy_auth_script = project_root / "scripts" / "copy_auth_schema.py"
        logger.info(f"Looking for script at: {copy_auth_script}")
        
        # If not found, try with auth_service prefix (might be needed in some Docker setups)
        if not copy_auth_script.exists():
            copy_auth_script = project_root / "auth_service" / "scripts" / "copy_auth_schema.py"
            logger.info(f"Looking for script at: {copy_auth_script}")
        
        # Only fall back to legacy locations if absolutely necessary
        if not copy_auth_script.exists():
            logger.warning("Script not found in preferred location, trying fallbacks")
            # Try the project root
            copy_auth_script = project_root / "copy_auth_schema.py"
            
            if not copy_auth_script.exists():
                copy_auth_script = Path(PROJECT_ROOT).parent / "copy_auth_schema.py"
                
            if not copy_auth_script.exists():
                logger.warning(f"Auth schema copy script not found at any expected location")
                raise FileNotFoundError(f"Cannot find copy_auth_schema.py in any location")
        
        logger.info(f"Running auth schema copy script: {copy_auth_script}")
            
        # Run the auth schema copy script
        copy_result = subprocess.run(
            ["python", str(copy_auth_script)],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        if copy_result.returncode == 0:
            logger.info("Auth schema setup completed successfully")
            logger.info(f"Auth script output: {copy_result.stdout}")
        else:
            logger.error(f"Auth schema setup failed with code {copy_result.returncode}")
            logger.error(f"Error output: {copy_result.stderr}")
            logger.error(f"Standard output: {copy_result.stdout}")
            raise RuntimeError(f"Failed to set up auth schema: {copy_result.stderr}")
            
        # STEP 2: Now run the Alembic migrations
        logger.info("STEP 2: Running Alembic migrations on test database...")
            
        # Find the migration script in the scripts directory first
        migration_script = project_root / "scripts" / "auth_test_migrations.py"
        logger.info(f"Looking for migration script at: {migration_script}")
        
        # If not found, try with auth_service prefix
        if not migration_script.exists():
            migration_script = project_root / "auth_service" / "scripts" / "auth_test_migrations.py"
            logger.info(f"Looking for migration script at: {migration_script}")
        
        # Fall back to legacy locations only if necessary
        if not migration_script.exists():
            logger.warning("Migration script not found in scripts directory, trying fallbacks")
            migration_script = project_root / "apply_test_migrations.py"
            logger.info(f"Looking for migration script at: {migration_script}")
            
            if not migration_script.exists():
                migration_script = Path(PROJECT_ROOT).parent / "apply_test_migrations.py"
                logger.info(f"Looking for migration script at: {migration_script}")
            
            if not migration_script.exists():
                logger.warning(f"Migration script not found at any expected location")
                raise FileNotFoundError(f"Cannot find migration script")
            
        logger.info(f"Running migration script: {migration_script}")

        # Set environment variables for the script
        env = os.environ.copy()
        env["DATABASE_URL"] = TEST_DATABASE_URL
        
        # Parse the database URL to extract actual host used by the test environment
        url_parts = urllib.parse.urlparse(TEST_DATABASE_URL)
        netloc_parts = url_parts.netloc.split('@')
        if len(netloc_parts) > 1:
            host_port = netloc_parts[1].split(':')[0]
            logger.info(f"Using host from TEST_DATABASE_URL: {host_port}")
            env["DB_HOST"] = host_port
        else:
            # Fallback to Docker container name for database host
            env["DB_HOST"] = "supabase_db_paservices"
            logger.info(f"Using supabase_db_paservices for database host")
        
        env["DB_PORT"] = "5432"
        env["DB_USER"] = "postgres"
        env["DB_PASSWORD"] = "postgres"
        env["DB_NAME"] = "auth_test_db"
        env["ALEMBIC_DIR"] = str(Path(PROJECT_ROOT) / "alembic")

        # Run the script in a subprocess
        result = subprocess.run(
            ["python", str(migration_script)],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        if result.returncode == 0:
            logger.info("Migration script completed successfully")
            logger.info(f"Script output: {result.stdout}")
            
            # Now run the auth schema setup script
            logger.info("Setting up auth schema for test database...")
            auth_script = project_root / "auth_service" / "scripts" / "setup_auth_schema.py"
            
            if not auth_script.exists():
                logger.warning(f"Auth schema setup script not found at {auth_script}")
                for path in [Path(PROJECT_ROOT), Path(os.getcwd()), Path("/app")]:
                    test_path = path / "setup_auth_schema.py"
                    if test_path.exists():
                        auth_script = test_path
                        logger.info(f"Found auth schema setup script at {auth_script}")
                        break
                else:
                    logger.warning("Auth schema setup script not found, tests requiring auth.users table may fail")
                    return
            
            # Run the auth schema setup script
            auth_result = subprocess.run(
                ["python", str(auth_script), "--db-host", env["DB_HOST"], "--db-port", env["DB_PORT"], "--db-name", "auth_test_db"],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            
            if auth_result.returncode == 0:
                logger.info("Auth schema setup completed successfully")
                logger.info(f"Auth script output: {auth_result.stdout}")
                return
            else:
                logger.warning(f"Auth schema setup failed with code {auth_result.returncode}")
                logger.warning(f"Error output: {auth_result.stderr}")
                logger.warning(f"Standard output: {auth_result.stdout}")
                logger.warning("Tests requiring auth.users table may fail")
                return
        else:
            logger.error(f"Migration script failed with code {result.returncode}")
            logger.error(f"Error output: {result.stderr}")
            logger.error(f"Standard output: {result.stdout}")
            raise RuntimeError(f"Failed to run migration script: {result.stderr}")

    except Exception as e:
        logger.error(f"Error during test database setup: {e}")
        raise


@pytest_asyncio.fixture(scope="session")
async def test_engine_fixture(
    apply_migrations_to_test_db: None,
) -> AsyncGenerator[AsyncEngine, None]:
    """Create test database engine."""
    # Handle pgbouncer parameter properly
    import urllib.parse

    url_parts = urllib.parse.urlparse(TEST_DATABASE_URL)
    query_dict = dict(urllib.parse.parse_qsl(url_parts.query))

    # Remove pgbouncer from URL query parameters
    pgbouncer_enabled = False
    if "pgbouncer" in query_dict:
        pgbouncer_enabled = query_dict.pop("pgbouncer") == "true"

    # Reconstruct URL without pgbouncer parameter
    clean_query = urllib.parse.urlencode(query_dict)
    clean_url_parts = list(url_parts)
    clean_url_parts[4] = clean_query  # index 4 is query
    clean_url = urllib.parse.urlunparse(clean_url_parts)

    # Create connect_args dict with pgBouncer settings if needed
    connect_args = {}
    if pgbouncer_enabled:
        # Use server-side parameters to disable prepared statements and emulate prepare=False for pgBouncer compatibility
        options = r"-c standard_conforming_strings=on -c client_encoding=utf8 -c plan_cache_mode=force_custom_plan -c statement_timeout=0 -c default_transaction_isolation=read\ committed"
        connect_args = {"options": options}

    logger.info(
        f"Using test database URL: {clean_url} with pgbouncer={pgbouncer_enabled}"
    )

    engine = create_async_engine(
        clean_url,
        echo=False,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session_for_crud(
    test_engine_fixture: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session that properly manages transactions.

    This fixture uses a nested transaction pattern with savepoints to allow
    tests to commit their changes while still ensuring all changes are rolled back
    at the end of the test.
    """
    # Create a connection that will be used for the entire test
    connection = await test_engine_fixture.connect()

    # Start an outer transaction that will be rolled back at the end
    trans = await connection.begin()

    # Create session bound to the connection
    async_session_maker = sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=True,
        autocommit=False,
    )

    session = async_session_maker()

    # Begin a nested transaction (savepoint)
    try:
        await session.begin_nested()
    except Exception as e:
        # Some drivers might not support nested transactions directly
        # In that case, we'll use a different approach
        print(f"Warning: begin_nested failed: {e}")
        pass

    # If the inner transaction is committed, start a new one
    @event.listens_for(session.sync_session, "after_transaction_end")
    def end_savepoint(session_sync, transaction):
        if transaction.nested and not transaction._parent.nested:
            session.sync_session.begin_nested()

    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()  # Roll back the outer transaction
        await connection.close()


@pytest_asyncio.fixture(scope="function")
async def async_client(
    db_session_for_crud: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client with database session override."""

    async def override_get_db():
        yield db_session_for_crud

    # Override the database dependency
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Clean up override
    if get_db in app.dependency_overrides:
        del app.dependency_overrides[get_db]
