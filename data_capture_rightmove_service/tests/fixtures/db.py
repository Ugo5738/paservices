"""
Database fixtures for testing.
"""
import asyncio
import os
from typing import AsyncGenerator, Generator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession, 
    create_async_engine, 
    async_sessionmaker
)

# Import from service config to respect environment variable format
from data_capture_rightmove_service import config

# Following our standardized variable naming convention with service-specific prefixes
# Use test database to avoid interfering with development database
SQLALCHEMY_TEST_DATABASE_URL = (
    f"postgresql+asyncpg://{config.RIGHTMOVE_SERVICE_DB_USER}:{config.RIGHTMOVE_SERVICE_DB_PASSWORD}"
    f"@{config.RIGHTMOVE_SERVICE_DB_HOST}:{config.RIGHTMOVE_SERVICE_DB_PORT}"
    f"/{config.RIGHTMOVE_SERVICE_DB_NAME}_test"
)

# Create async engine and session for testing
test_engine = create_async_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    echo=False,
    connect_args={"server_settings": {"search_path": "rightmove,public"}}
)

TestAsyncSessionLocal = async_sessionmaker(
    test_engine,
    expire_on_commit=False,
    class_=AsyncSession
)


@pytest.fixture
async def event_loop() -> Generator:
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def setup_test_database() -> AsyncGenerator:
    """
    Setup a test database by creating tables and setting up the schema.
    This follows the pattern used in auth_service for test database setup.
    """
    # Create tables and set up schema
    async with test_engine.begin() as conn:
        # Create the rightmove schema if it doesn't exist
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS rightmove;"))
        
        # Import and create tables based on models
        from data_capture_rightmove_service.models.base import Base
        from data_capture_rightmove_service.models.properties_details_v2 import ApiPropertiesDetailsV2
        from data_capture_rightmove_service.models.property_details import ApiPropertyDetails
        
        # Create all tables in the metadata
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    # Teardown - Drop all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session(setup_test_database) -> AsyncGenerator[AsyncSession, None]:
    """
    Create a fresh session for each test, then roll back all the changes.
    Follows the same pattern as auth_service for transaction isolation.
    """
    async with TestAsyncSessionLocal() as session:
        yield session
        await session.rollback()
