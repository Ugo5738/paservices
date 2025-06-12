"""Pytest fixtures for integration tests.

This file contains fixtures specific to integration tests for the Super ID Service.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import Depends, HTTPException, status

from super_id_service.schemas.auth import TokenData
from super_id_service.main import app
from super_id_service.dependencies import validate_token, get_supabase_client


@pytest.fixture
def token_with_permissions():
    """Return a token with super_id:generate permission."""
    return TokenData(
        sub="test-client-123",
        exp=1800000000,
        iat=1700000000,
        permissions=["super_id:generate"],
        iss="auth_service",
        client_id="test-client-123"
    )


@pytest.fixture
def token_without_permissions():
    """Return a token without super_id:generate permission."""
    return TokenData(
        sub="test-client-123",
        exp=1800000000,
        iat=1700000000,
        permissions=[],
        iss="auth_service",
        client_id="test-client-123"
    )


@pytest.fixture
def mock_supabase_client():
    """Mock the Supabase client using an AsyncMock."""
    # Create a class to act as our mock Supabase client
    class MockSupabaseClient:
        def __init__(self):
            self._tables = {}
        
        def table(self, table_name):
            if table_name not in self._tables:
                self._tables[table_name] = MockTable(table_name)
            return self._tables[table_name]
    
    # Create a class to act as our mock Table
    class MockTable:
        def __init__(self, table_name):
            self.table_name = table_name
        
        def insert(self, data):
            self.data = data
            return MockInsert(data)
    
    # Create a class to act as our mock Insert with async execute method
    class MockInsert:
        def __init__(self, data):
            self.data = data
        
        async def execute(self):
            response = {
                "data": [],
                "count": len(self.data),
                "error": None
            }
            # Add a generated UUID to each item in the response
            for item in self.data:
                super_id = item.get('super_id', str(uuid.uuid4()))
                metadata = item.get('metadata', None)
                client_id = item.get('requested_by_client_id', 'test-client')
                
                response["data"].append({
                    "id": len(response["data"]) + 1,
                    "super_id": super_id,
                    "requested_by_client_id": client_id,
                    "metadata": metadata,
                    "created_at": "2025-06-12T07:00:00Z"
                })
            return response
    
    # Create an instance of our mock client
    mock_client = MockSupabaseClient()
    
    # Patch the create_client function in the dependencies module
    with patch('super_id_service.dependencies.create_client', return_value=mock_client):
        yield mock_client


@pytest.fixture
def client_with_permissions(token_with_permissions, mock_supabase_client):
    """Create a test client with permissions."""
    app.dependency_overrides[validate_token] = lambda: token_with_permissions
    # We don't need to override get_supabase_client as we patch create_client directly
    
    client = TestClient(app)
    yield client
    # Reset dependency overrides after test
    app.dependency_overrides = {}


@pytest.fixture
def client_without_permissions(token_without_permissions, mock_supabase_client):
    """Create a test client without permissions."""
    app.dependency_overrides[validate_token] = lambda: token_without_permissions
    # We don't need to override get_supabase_client as we patch create_client directly
    
    client = TestClient(app)
    yield client
    # Reset dependency overrides after test
    app.dependency_overrides = {}


@pytest.fixture
def client_unauthenticated(mock_supabase_client):
    """Create a test client that fails auth."""
    async def mock_validate_token_error():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    app.dependency_overrides[validate_token] = mock_validate_token_error
    # We don't need to override get_supabase_client as we patch create_client directly
    
    client = TestClient(app)
    yield client
    # Reset dependency overrides after test
    app.dependency_overrides = {}


@pytest.fixture
def mock_auth_header():
    """Return a mock auth header."""
    return {"Authorization": "Bearer valid.test.token"}


@pytest.fixture(autouse=True)
def mock_limiter():
    """Mock rate limiter to avoid actual rate limiting in tests."""
    with patch("super_id_service.routers.super_id_router.limiter.limit"):
        yield
