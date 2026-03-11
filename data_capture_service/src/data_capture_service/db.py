"""
Database configuration and session management for the Data Capture Service.
"""

from typing import AsyncGenerator

import sqlalchemy.util.concurrency as _concurrency

_concurrency._not_implemented = lambda *args, **kwargs: None

from fastapi import Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from data_capture_service.config import settings
from data_capture_service.utils.logging_config import logger

# --- 1. Centralized Configuration Access ---
DATABASE_URL = settings.DATABASE_URL

# --- 2. Optimized Engine Configuration ---
is_cloud_db = "supabase.com" in DATABASE_URL
logger.info(f"Initializing database connection with psycopg3 driver")
logger.info(f"Database type detected: {'Cloud' if is_cloud_db else 'Local'}")

# Setup cloud-optimized connection arguments
connect_args = {
    "application_name": "data_capture_service",
    "options": "-c timezone=UTC"
    + (
        "" if settings.ENVIRONMENT == "testing" else " -c statement_timeout=30000"
    ),
    # Disable prepared statement cache for PgBouncer compatibility
    "prepare_threshold": None,
}

if is_cloud_db:
    connect_args.update({"sslmode": "require"})

engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=settings.LOGGING_LEVEL.upper() == "DEBUG",
    pool_pre_ping=True,
    poolclass=NullPool,
    connect_args=connect_args,
)

# --- 3. Standard Session Factory ---
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

SAFE_HTTP_METHODS = {"GET", "HEAD", "OPTIONS"}


# --- 4. Session Dependency ---
async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a transactional, auto-closing database session.
    """
    session = AsyncSessionLocal()
    try:
        yield session
        if request.method in SAFE_HTTP_METHODS:
            if session.in_transaction():
                await session.rollback()
        else:
            await session.commit()
    except SQLAlchemyError as e:
        logger.error(f"Database transaction failed: {e}", exc_info=True)
        await session.rollback()
        raise
    finally:
        await session.close()
