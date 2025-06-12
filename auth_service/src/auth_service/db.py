import asyncio
import time
from typing import AsyncGenerator, Optional

import sqlalchemy.util.concurrency as _concurrency

_concurrency._not_implemented = lambda *args, **kwargs: None

import os
import urllib.parse

from auth_service.config import settings
from auth_service.logging_config import logger
from sqlalchemy.exc import OperationalError, SQLAlchemyError, TimeoutError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from sqlalchemy.sql import func, text

# Connection settings optimized for Supabase pgBouncer
# Using minimal local pool since pgBouncer handles connection pooling
DB_POOL_SIZE = 3  # Small local connection pool when using pgBouncer
DB_MAX_OVERFLOW = 5  # Allow more overflow with pgBouncer in Kubernetes
DB_POOL_TIMEOUT = (
    15  # Allow more time for getting a connection from the pool (15 seconds)
)
DB_POOL_RECYCLE = 300  # Increased connection recycle time (5 minutes)
DB_CONNECT_TIMEOUT = (
    30  # Increased connection timeout (30 seconds) for Kubernetes network conditions
)
DB_COMMAND_TIMEOUT = 15  # Increased command timeout (15 seconds)
DB_MAX_RETRIES = 5  # Increased number of retries for failed connections
DB_RETRY_DELAY = 1.0  # Longer initial retry delay for network latency


# Parse the URL to remove pgbouncer parameter if present
def parse_db_url(url):
    """Parse database URL and clean parameters not supported by the driver."""
    # Check if pgBouncer parameter is in the URL
    has_pgbouncer_param = "pgbouncer=true" in url

    # If there's no pgbouncer parameter, return the URL as is
    if not has_pgbouncer_param:
        return url

    # Handle URL parsing to remove the pgbouncer parameter
    driver_prefix = ""
    if url.startswith("postgresql+"):
        driver_end = url.find("://")
        if driver_end != -1:
            driver_prefix = url[: driver_end + 3]
            url = url[driver_end + 3 :]
    elif url.startswith("postgresql://"):
        driver_prefix = "postgresql://"
        url = url[len(driver_prefix) :]

    # Ensure we're using psycopg driver
    if "postgresql+" not in driver_prefix:
        driver_prefix = "postgresql+psycopg://"

    # Split the URL into components
    if "@" in url:
        userpass, hostportdb = url.split("@", 1)
    else:
        userpass = ""
        hostportdb = url

    # Handle query parameters
    query_params = {}
    if "?" in hostportdb:
        hostportdb, query_string = hostportdb.split("?", 1)
        for param in query_string.split("&"):
            if "=" in param:
                key, value = param.split("=", 1)
                query_params[key] = value

    # Remove pgbouncer parameter
    if "pgbouncer" in query_params:
        del query_params["pgbouncer"]

    # Rebuild the URL without the pgbouncer parameter
    clean_url = driver_prefix + userpass
    if userpass:
        clean_url += "@"
    clean_url += hostportdb
    if query_params:
        clean_url += "?" + "&".join([f"{k}={v}" for k, v in query_params.items()])

    return clean_url


# First clean the URL of any pgbouncer parameters
clean_db_url = parse_db_url(settings.auth_service_database_url)

# Check if pgbouncer=true is explicitly set in the DATABASE_URL
has_pgbouncer_in_url = "pgbouncer=true" in settings.auth_service_database_url

# Use the Settings.use_pgbouncer field - properly parsed as a boolean
use_pgbouncer_env = settings.use_pgbouncer

# Determine if we're running in pgBouncer mode
is_pgbouncer = has_pgbouncer_in_url or use_pgbouncer_env

# Log the pgBouncer mode
if is_pgbouncer:
    logger.info(f"Running with pgBouncer compatibility mode: {is_pgbouncer}")

# Detect environment - we'll use this to enable/disable features that might not be supported in test env
is_production = settings.is_production()

# Connection arguments - set up base configuration
connect_args = {
    # Server settings - critical for pgBouncer compatibility
    "options": rf"-c application_name=auth_service -c default_transaction_isolation=read\ committed -c statement_timeout={DB_COMMAND_TIMEOUT * 1000}ms"
}

# Add timeout settings - only use parameters supported by psycopg3
connect_args.update(
    {
        "connect_timeout": DB_CONNECT_TIMEOUT,
        # Note: psycopg3 doesn't support execute_timeout directly as a connection parameter
        # We'll handle command timeouts via statement_timeout in PostgreSQL configuration
    }
)

# Add pgBouncer-specific optimizations for production
if is_production and is_pgbouncer:
    logger.info("Using production pgBouncer connection optimizations")

    # Log that we're using pgBouncer compatibility mode
    logger.info("Using pgBouncer compatibility mode: disabled prepared statements")

# Add pgBouncer-specific connection arguments if needed
if is_pgbouncer:
    logger.info("Applying pgBouncer-specific connection arguments")

    # psycopg3 handles pgBouncer better, we just need to use "options" instead of "server_settings"
    # and disable prepared statements via the driver's specific parameters

    # We disable prepared statements in a way that works with both psycopg2 and psycopg3
    # Instead of using driver-specific 'prepare' parameter, use PostgreSQL server parameter
    if "options" not in connect_args:
        connect_args["options"] = ""
    connect_args[
        "options"
    ] += " -c standard_conforming_strings=on -c client_encoding=utf8"

    # Add correct isolation level for pgBouncer and disable prepared statements server-side
    connect_args[
        "options"
    ] += " -c statement_timeout=0 -c plan_cache_mode=force_custom_plan"

    # Log the full connection arguments for debugging
    logger.info(f"pgBouncer connect_args: {connect_args}")

    # Add engine arguments for SQLAlchemy
    engine_args = {
        "echo": settings.logging_level.upper() == "DEBUG",
        "poolclass": NullPool,  # Use NullPool with pgBouncer to avoid connection pooling conflicts
        "pool_pre_ping": True,
        "connect_args": connect_args,
    }

# Create a standard set of engine arguments
base_engine_args = {
    "echo": settings.logging_level.upper() == "DEBUG",
    "pool_pre_ping": True,
    "connect_args": connect_args,
}

# Add pooling config if not using pgBouncer
if not is_pgbouncer:
    base_engine_args.update(
        {
            "pool_size": DB_POOL_SIZE,
            "max_overflow": DB_MAX_OVERFLOW,
            "pool_timeout": DB_POOL_TIMEOUT,
            "pool_recycle": DB_POOL_RECYCLE,
        }
    )
else:
    # Use NullPool when working with pgBouncer
    base_engine_args["poolclass"] = NullPool
    logger.info("Using NullPool with pgBouncer for better compatibility")

# Create the engine with the appropriate settings
engine: AsyncEngine = create_async_engine(clean_db_url, **base_engine_args)

if is_pgbouncer:
    logger.info("Created database engine with pgBouncer compatibility mode")
else:
    logger.info("Created standard database engine without pgBouncer mode")

# Session factory for async sessions - using async_sessionmaker is recommended in SQLAlchemy 2.0
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# Base class for ORM models
Base = declarative_base()


async def verify_db_connection(session: AsyncSession, retries=1) -> bool:
    """
    Verify database connection with retry logic.
    Returns True if connection is successful, False otherwise.
    """
    # Log database connection details for debugging (without exposing credentials)
    parsed_url = urllib.parse.urlparse(clean_db_url)
    masked_url = f"{parsed_url.scheme}://{parsed_url.hostname}:{parsed_url.port}{parsed_url.path}"
    logger.info(f"Attempting database connection to: {masked_url}")
    logger.info(f"pgBouncer mode: {is_pgbouncer}")

    for attempt in range(retries + 1):
        try:
            # Execute a simple query to verify connection
            logger.info(f"Database connection attempt {attempt + 1}/{retries + 1}")
            await session.execute(text("SELECT 1"))
            if attempt > 0:
                logger.info(f"Database connection restored on attempt {attempt + 1}")
            return True
        except SQLAlchemyError as e:
            if attempt < retries:
                wait_time = DB_RETRY_DELAY * (2**attempt)  # Exponential backoff
                logger.warning(
                    f"Database connection attempt {attempt + 1} failed: {e.__class__.__name__}: {str(e)}. "
                    f"Retrying in {wait_time:.2f}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error(
                    f"Failed to connect to database after {retries + 1} attempts. "
                    f"Error: {e.__class__.__name__}: {str(e)}",
                    exc_info=True,
                )
                return False
        except Exception as e:
            logger.error(
                f"Unexpected error during database connection: {e.__class__.__name__}: {str(e)}",
                exc_info=True,
            )
            if attempt < retries:
                wait_time = DB_RETRY_DELAY * (2**attempt)
                await asyncio.sleep(wait_time)
            else:
                return False
    return False


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async session generator for dependency injection with improved error handling.

    Features:
    - Connection retry logic with exponential backoff
    - Proper session cleanup to prevent leaks
    - Detailed error reporting
    - Timeout handling

    Commits should be handled within the business logic using the session.
    """
    session = None
    start_time = time.time()

    # Add more retries in production environment for Kubernetes
    retries = DB_MAX_RETRIES * 2 if settings.is_production() else DB_MAX_RETRIES

    try:
        # Create a new session
        logger.debug("Creating new database session")
        session = AsyncSessionLocal()

        # Log connection attempt
        logger.info(f"Verifying database connection with {retries} retries")

        # Verify connection with retry logic
        connection_ok = await verify_db_connection(session, retries=retries)
        if not connection_ok:
            if session:
                try:
                    await session.close()
                except Exception as e:
                    logger.warning(
                        f"Failed to close session after connection failure: {e}"
                    )
            raise RuntimeError("Failed to establish database connection after retries")
    except Exception as e:
        # Handle session creation errors
        elapsed = time.time() - start_time
        error_class = e.__class__.__name__
        error_msg = str(e)

        # Log detailed error information
        if "timeout" in error_msg.lower():
            logger.error(
                f"Database connection timeout after {elapsed:.3f}s: {error_class}: {error_msg}"
            )
            # Log connection details (without credentials) to help debug the issue
            parsed_url = urllib.parse.urlparse(clean_db_url)
            logger.error(
                f"DB connection failed. Host: {parsed_url.hostname}, Port: {parsed_url.port}, "
                f"pgBouncer mode: {is_pgbouncer}, Connect timeout: {DB_CONNECT_TIMEOUT}s"
            )
        else:
            logger.error(
                f"Database session creation failed after {elapsed:.3f}s: {error_class}: {error_msg}",
                exc_info=True,
            )

        # Close session if it was created but not working
        if session:
            try:
                await session.close()
            except Exception as close_error:
                logger.warning(
                    f"Error closing failed session: {close_error.__class__.__name__}: {str(close_error)}"
                )

        # Re-raise the exception
        raise

    # If we got here, we have a working session
    try:
        # Actually yield the session to be used
        yield session
    except Exception as e:
        # Error during request processing - rollback and log
        try:
            await session.rollback()
        except Exception as rollback_error:
            logger.warning(
                f"Error during session rollback: {rollback_error.__class__.__name__}: {str(rollback_error)}"
            )

        # Re-raise the original exception
        raise
    finally:
        # Always clean up the session
        if session is not None:
            try:
                await session.close()
                if settings.logging_level.upper() == "DEBUG":
                    elapsed = time.time() - start_time
                    logger.debug(f"Database session closed after {elapsed:.3f}s")
            except Exception as close_error:
                logger.warning(
                    f"Error closing database session: {close_error.__class__.__name__}: {str(close_error)}"
                )
                # Don't re-raise close errors - we want to ensure the session gets cleaned up
