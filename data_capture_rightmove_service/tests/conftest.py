"""
Main conftest file that imports and re-exports all fixtures from modular files.
This approach improves maintainability by organizing fixtures into logical modules.
"""

import asyncio
import os
from typing import AsyncGenerator, Generator

import pytest
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Explicitly load the test environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env.test")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path, override=True)
else:
    print(f"Warning: .env.test file not found at {dotenv_path}")

# Now reload the config to ensure it picks up test settings
from importlib import reload

from src.data_capture_rightmove_service import config

reload(config)

# Use a dedicated database for testing
# This should be different from the development database
SQLALCHEMY_TEST_DATABASE_URL = f"postgresql+psycopg://{config.DB_USER}:{config.DB_PASSWORD}@{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}_test"

# Create async engine and session for testing
test_engine = create_async_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    echo=False,
    connect_args={"server_settings": {"search_path": "rightmove,public"}},
)

TestAsyncSessionLocal = async_sessionmaker(
    test_engine, expire_on_commit=False, class_=AsyncSession
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
    """
    # Create tables and set up schema
    async with test_engine.begin() as conn:
        # Create the rightmove schema if it doesn't exist
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS rightmove;"))

        # Import and create tables based on models
        from data_capture_rightmove_service.models.base import Base
        from data_capture_rightmove_service.models.properties_details_v2 import (  # Import all other models used in the tests
            ApiPropertiesDetailsV2,
        )
        from data_capture_rightmove_service.models.property_details import (  # Import all other models used in the tests
            ApiPropertyDetails,
        )

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
    """
    async with TestAsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def seed_rightmove_property():
    """Helper fixture to seed a test Rightmove property."""

    async def _seed_rightmove_property(
        db_session: AsyncSession, property_id=None, with_relations=False
    ):
        """Seed a test Rightmove property record with specified ID or auto-generated one.

        Args:
            db_session: The database session
            property_id: Optional property ID to use (BigInt)
            with_relations: Whether to create related records too

        Returns:
            The ID of the created property
        """
        import random

        from data_capture_rightmove_service.models.properties_details_v2 import (
            ApiPropertiesDetailsV2,
            ApiPropertiesDetailsV2Misinfo,
            ApiPropertiesDetailsV2Price,
        )

        # Create base property
        if property_id is None:
            property_id = random.randint(10000000, 99999999)

        # Create main property record
        property_record = ApiPropertiesDetailsV2(
            id=property_id,
            transaction_type="SALE",
            bedrooms=3,
            summary="Test property for unit tests",
            address="123 Test Street, Testville",
        )
        db_session.add(property_record)
        await db_session.flush()

        if with_relations:
            # Add misinfo relation
            misinfo = ApiPropertiesDetailsV2Misinfo(
                api_property_id=property_id,
                branch_id=12345,
                brand_plus=False,
                featured_property=True,
                channel="BUY",
            )
            db_session.add(misinfo)

            # Add price relation
            price = ApiPropertiesDetailsV2Price(
                api_property_id=property_id,
                amount=250000,
                currency_code="GBP",
                frequency=None,
                qualifier="Guide Price",
            )
            db_session.add(price)

        await db_session.commit()
        return property_id

    return _seed_rightmove_property
