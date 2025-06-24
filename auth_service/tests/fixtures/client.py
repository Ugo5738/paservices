"""
Client fixtures for testing.
Provides HTTP clients and dependency overrides for FastAPI application testing.
"""
import pytest_asyncio
from typing import AsyncGenerator
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.main import app as fastapi_app
from auth_service.db import get_db
from auth_service.supabase_client import get_supabase_client


# Ensure the root_path is set to empty string for tests
fastapi_app.root_path = ""


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, mock_supabase_client) -> AsyncGenerator[AsyncClient, None]:
    """
    Provides an HTTP client for making requests to the FastAPI app.
    It overrides the `get_db` dependency to use the isolated test database session
    and the Supabase client dependency to use our mock.
    """
    print("\nSetting up test client with database session")
    
    # Create dependency overrides for database and Supabase client
    async def override_get_db():
        """Override the database dependency to use our test session."""
        try:
            # Yield the test session to the route handler
            yield db_session
            # Changes will be rolled back by the db_session fixture
        except Exception as e:
            # Ensure rollback on errors
            await db_session.rollback()
            raise

    def override_get_supabase_client():
        """Override the Supabase client dependency to use our mock."""
        return mock_supabase_client

    # Apply the dependency overrides to our test app
    # This ensures our routes use the test database session and mock Supabase client
    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_supabase_client] = override_get_supabase_client
    
    # Create an HTTP client that directly calls our FastAPI app
    # This bypasses the need for a real HTTP server
    transport = ASGITransport(app=fastapi_app)
    
    try:
        # Create and yield the test client
        # Using base_url="http://test" ensures proper URL building
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            print("Test client ready")
            yield client
    finally:
        # Clean up the dependency overrides after the test
        print("Cleaning up test client")
        del fastapi_app.dependency_overrides[get_db]
        del fastapi_app.dependency_overrides[get_supabase_client]
