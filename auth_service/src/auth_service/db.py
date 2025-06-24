import asyncio
import time
from typing import AsyncGenerator, Optional

import sqlalchemy.util.concurrency as _concurrency

_concurrency._not_implemented = lambda *args, **kwargs: None

import os
import urllib.parse

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from sqlalchemy.sql import func, text

from auth_service.config import settings
from auth_service.logging_config import logger

# --- 1. Centralized Configuration Access ---
DATABASE_URL = settings.DATABASE_URL

# --- 2. Optimized Engine Configuration ---
# All engine and pool settings are consolidated here for clarity.
# These settings are chosen for a balance of performance and resilience,
# especially in a containerized environment like Docker or Kubernetes.
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    # Log SQL statements in DEBUG mode only.
    echo=settings.LOGGING_LEVEL.upper() == "DEBUG",
    # --- Connection Pool Settings ---
    pool_size=10,  # The number of connections to keep open in the pool.
    max_overflow=20,  # The number of "extra" connections that can be opened.
    pool_timeout=30,  # Seconds to wait before giving up on getting a connection from the pool.
    pool_recycle=1800,  # Recycle connections every 30 minutes to prevent stale connections.
    # --- CRITICAL OPTIMIZATION ---
    # This is the most important setting for resilience. It runs a simple 'SELECT 1'
    # on a connection before it's checked out from the pool. If the connection is dead,
    # it's discarded and a new one is established. This eliminates most connection errors.
    pool_pre_ping=True,
    # Connection arguments passed directly to the psycopg v3 driver
    connect_args={
        "application_name": "auth_service",
        # For psycopg v3, we use options parameter instead of server_settings
        "options": "-c timezone=UTC"
        + ("" if settings.ENVIRONMENT == "testing" else " -c statement_timeout=5000"),
    },
)

# --- 3. Standard Session Factory ---
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# --- 4. Declarative Base ---
# All SQLAlchemy models will inherit from this Base.
Base = declarative_base()


# --- 5. Simplified and Robust Session Dependency ---
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a transactional, auto-closing database session.

    This standard pattern ensures that:
    1. A new session is created for each request.
    2. The session is always closed, preventing connection leaks.
    3. Any database errors during the request cause a rollback, ensuring data integrity.
    """
    session = AsyncSessionLocal()
    try:
        # Yield the session to the route handler.
        yield session
        # If the route handler finishes without errors, commit the transaction.
        await session.commit()
    except SQLAlchemyError as e:
        # If a database-related error occurs, roll back all changes.
        logger.error(f"Database transaction failed: {e}", exc_info=True)
        await session.rollback()
        # Re-raise the exception to be handled by FastAPI's error handlers.
        raise
    finally:
        # Always close the session to release the connection back to the pool.
        await session.close()
