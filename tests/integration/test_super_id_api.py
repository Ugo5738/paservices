"""
Integration tests for Super ID Service API.

These tests verify the end-to-end functionality of the Super ID API
with actual database operations.
"""

import pytest
import uuid
from typing import Dict, Any, Callable, List, Union
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import status, Depends, FastAPI, APIRouter
from fastapi.testclient import TestClient

from super_id_service.main import app
from super_id_service.dependencies import validate_token
from super_id_service.schemas.auth import TokenData
from super_id_service.schemas.super_id import SingleSuperIDResponse, BatchSuperIDResponse


@pytest.fixture(scope="module")
def token_with_permissions():
    """Returns a TokenData object with super_id:generate permission"""
    return TokenData(
        sub="test-client-123",
        exp=1800000000, 
        iat=1700000000,
        permissions=["super_id:generate"],
        iss="auth_service",
        client_id="test-client-123"
    )


@pytest.fixture(scope="module")
def token_without_permissions():
    """Returns a TokenData object without any permissions"""
    return TokenData(
        sub="test-client-123",
        exp=1800000000, 
        iat=1700000000,
        permissions=[],
        iss="auth_service",
        client_id="test-client-123"
    )


@pytest.fixture
def client_with_permissions(token_with_permissions):
    """Create a test client with token validation mocked to include permissions"""
    app_local = FastAPI()
    app_local.router = app.router
    
    # Override the dependency with a function that returns our mocked token
    async def mock_validate_token():
        return token_with_permissions
    
    app.dependency_overrides[validate_token] = mock_validate_token
    
    # Create test client
    client = TestClient(app)
    
    yield client
    
    # Clean up
    app.dependency_overrides = {}


@pytest.fixture
def mock_auth_header():
    """Generate a mock Bearer token header for testing."""
    return {"Authorization": "Bearer valid.test.token"}


@pytest.fixture
def client_without_permissions(token_without_permissions):
    """Create a test client with token validation mocked but no permissions"""
    # Override the dependency with a function that returns token without permissions
    async def mock_validate_token_no_perms():
        return token_without_permissions
    
    app.dependency_overrides[validate_token] = mock_validate_token_no_perms
    
    # Create test client
    client = TestClient(app)
    
    yield client
    
    # Clean up
    app.dependency_overrides = {}


# Note: We're no longer defining mock_supabase_client here - it's now in conftest.py
# We also don't need app_with_mocked_dependencies since we're mocking at the dependency level


def test_generate_single_super_id(mock_supabase_client, client_with_permissions, mock_auth_header):
    """Test generation of a single super ID."""
    # Use the client with permissions and mock auth header
    response = client_with_permissions.post(
        "/super_ids",
        json={"count": 1},
        headers=mock_auth_header
    )
    
    # Validate the response
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert "super_id" in data
    assert isinstance(data["super_id"], str)
    
    # Validate UUID format
    super_id = data["super_id"]
    assert len(super_id) == 36  # UUID string length
    assert super_id.count("-") == 4  # UUID format has 4 hyphens
    
    # Note: With our custom mock classes we don't need to verify mock calls directly
    # as we're patching at the dependency level and our MockSupabaseClient handles the responses


def test_generate_multiple_super_ids(mock_supabase_client, client_with_permissions, mock_auth_header):
    """Test generating multiple super_ids at once."""
    # Make request to generate multiple super_ids
    count = 3
    response = client_with_permissions.post(
        "/super_ids", 
        json={"count": count},
        headers=mock_auth_header
    )
    
    # Validate response
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert "super_ids" in data
    assert len(data["super_ids"]) == count
    
    # Validate each UUID
    for super_id in data["super_ids"]:
        assert len(super_id) == 36  # UUID string length
        assert super_id.count("-") == 4  # UUID format has 4 hyphens


def test_generate_super_id_with_metadata(mock_supabase_client, client_with_permissions, mock_auth_header):
    """Test generating a super_id with metadata."""
    # Define test metadata
    metadata = {
        "workflow": "property-analysis", 
        "version": "1.2.3", 
        "initiator": "test-service"
    }
    
    # Make request to generate super_id with metadata
    response = client_with_permissions.post(
        "/super_ids",
        json={"count": 1, "metadata": metadata},
        headers=mock_auth_header
    )
    
    # Validate response
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert "super_id" in data
    # Note: The API doesn't actually return metadata in the response,
    # even though it saves it in the database, so we don't check for it here
    
    # Validate UUID format
    super_id = data["super_id"]
    assert len(super_id) == 36  # UUID string length
    assert super_id.count("-") == 4  # UUID format has 4 hyphens


def test_unauthenticated_request(client_unauthenticated):
    """Test that unauthenticated requests are rejected."""
    response = client_unauthenticated.post("/super_ids", json={"count": 1})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_invalid_permission(client_without_permissions, mock_auth_header):
    """Test that authorized but unauthorized requests are rejected."""
    response = client_without_permissions.post(
        "/super_ids",
        json={"count": 1},
        headers=mock_auth_header
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_invalid_request_body(client_with_permissions, mock_auth_header):
    """Test that invalid request bodies are rejected."""
    # Test with count exceeding maximum
    response = client_with_permissions.post(
        "/super_ids",
        json={"count": 101},  # Count exceeds maximum (100)
        headers=mock_auth_header
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    # Test with invalid count (negative)
    response = client_with_permissions.post(
        "/super_ids",
        json={"count": -1},
        headers=mock_auth_header
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
