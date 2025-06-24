"""
Database fixtures for testing.
Provides fixtures for test database setup, session management, and teardown.
"""
import os
import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from sqlalchemy import text, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from auth_service.config import settings
from auth_service.db import Base
from auth_service.models.profile import Profile

# Create a PostgreSQL engine for testing
# Use NullPool to avoid connection pool issues during tests
engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
    echo=False,  # Set to True for debugging SQL
    future=True  # Use SQLAlchemy 2.0 style
)

# Create the session factory for tests
TestingSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create and yield a single event loop for the test session."""
    # Create a new loop for the test session
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    
    # Set as current event loop to ensure all async code uses this loop
    asyncio.set_event_loop(loop)
    
    yield loop
    
    # Clean up resources and close the loop
    pending = asyncio.all_tasks(loop=loop)
    if pending:
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    """
    Set up the test database once per test session.
    This creates the necessary tables and schema, including a mock of Supabase's auth.users table.
    """
    print(f"\nSetting up test database with URL: {settings.DATABASE_URL}")
    
    # Create database tables from SQLAlchemy models
    async with engine.begin() as conn:
        # First drop all existing tables to ensure a clean state
        await conn.run_sync(Base.metadata.drop_all)
        
        # Create the auth schema required by Supabase references 
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth;"))
        
        # Create a minimal version of auth.users table that satisfies our foreign key constraints
        # This simulates the Supabase auth.users table in the test environment
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS auth.users (
                id UUID PRIMARY KEY,
                instance_id UUID,
                aud VARCHAR,
                role VARCHAR,
                encrypted_password VARCHAR,
                confirmation_token VARCHAR, 
                email_confirmed_at TIMESTAMP WITH TIME ZONE,
                invited_at TIMESTAMP WITH TIME ZONE,
                confirmation_sent_at TIMESTAMP WITH TIME ZONE,
                recovery_token VARCHAR,
                recovery_sent_at TIMESTAMP WITH TIME ZONE,
                email_change_token_new VARCHAR,
                email_change VARCHAR,
                email_change_sent_at TIMESTAMP WITH TIME ZONE,
                last_sign_in_at TIMESTAMP WITH TIME ZONE,
                raw_app_meta_data JSONB,
                raw_user_meta_data JSONB,
                is_super_admin BOOLEAN,
                created_at TIMESTAMP WITH TIME ZONE,
                updated_at TIMESTAMP WITH TIME ZONE,
                phone VARCHAR NULL UNIQUE,
                phone_confirmed_at TIMESTAMP WITH TIME ZONE,
                phone_change VARCHAR NULL DEFAULT ''::character varying,
                phone_change_token VARCHAR NULL DEFAULT ''::character varying,
                phone_change_sent_at TIMESTAMP WITH TIME ZONE,
                confirmed_at TIMESTAMP WITH TIME ZONE,
                is_anonymous BOOLEAN DEFAULT false
            );
        """))
        
        # Create all tables from models
        await conn.run_sync(Base.metadata.create_all)
        
        print("Created test database schema and tables")
    
    # Yield control back to the tests
    yield
    
    # Clean up after tests are done
    print("\nTearing down test database")
    async with engine.begin() as conn:
        # Drop all tables
        await conn.run_sync(Base.metadata.drop_all)
        
        # Drop the auth schema and all its tables
        await conn.execute(text("DROP SCHEMA IF EXISTS auth CASCADE;"))


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for each test with transaction rollback."""
    # Connect to the database and begin a transaction
    connection = await engine.connect()
    # This outer transaction will be rolled back at the end
    trans = await connection.begin()
    
    # Create session bound to this connection
    session = TestingSessionLocal(bind=connection)
    
    try:
        # Yield the session to the test
        yield session
    finally:
        # Clean up regardless of test result
        await session.close()
        # Roll back the transaction - this undoes any database changes in the test
        await trans.rollback()
        # Close the connection
        await connection.close()
