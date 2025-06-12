"""
Unit tests for Super ID Service API routes.
"""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import status
from super_id_service.routers.super_id_router import create_super_id
from super_id_service.schemas.super_id import SuperIDRequest as SuperIdRequest
from super_id_service.schemas.auth import TokenData


@pytest.fixture
def mock_token_data():
    """Mock token data with required permissions."""
    return TokenData(
        sub="test-client-123",
        exp=1800000000,
        iat=1700000000,
        permissions=["super_id:generate"],
        iss="auth_service",
        client_id="test-client-123"
    )


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for testing."""
    mock_client = MagicMock()
    # Set up the method chain that will be called
    mock_table = MagicMock()
    mock_insert = MagicMock()
    mock_execute = AsyncMock()
    
    mock_client.table.return_value = mock_table
    mock_table.insert.return_value = mock_insert
    mock_execute.return_value = {"data": [{"id": 1}], "error": None}
    mock_insert.execute = mock_execute
    
    return mock_client


@pytest.mark.asyncio
async def test_create_single_super_id(mock_token_data, mock_supabase_client):
    """Test generating a single super_id."""
    # Create request with count=1
    request = SuperIdRequest(count=1)
    
    # Call the function directly
    response = await create_super_id(
        request=request,
        token_data=mock_token_data,
        supabase_client=mock_supabase_client
    )
    
    # Assert the response has a valid UUID
    assert isinstance(response.super_id, uuid.UUID)
    
    # Verify Supabase interactions
    mock_supabase_client.table.assert_called_once_with("generated_super_ids")
    mock_supabase_client.table().insert.assert_called_once()
    mock_supabase_client.table().insert().execute.assert_called_once()


@pytest.mark.asyncio
async def test_create_multiple_super_ids(mock_token_data, mock_supabase_client):
    """Test generating multiple super_ids."""
    # Create request for 3 super_ids
    request = SuperIdRequest(count=3)
    
    # Call the function directly
    response = await create_super_id(
        request=request,
        token_data=mock_token_data,
        supabase_client=mock_supabase_client
    )
    
    # Assert the response contains 3 valid UUIDs
    assert len(response.super_ids) == 3
    for super_id in response.super_ids:
        assert isinstance(super_id, uuid.UUID)
    
    # Verify Supabase interactions for multiple IDs
    mock_supabase_client.table.assert_called_once_with("generated_super_ids")
    mock_supabase_client.table().insert.assert_called_once()
    mock_supabase_client.table().insert().execute.assert_called_once()


@pytest.mark.asyncio
async def test_create_super_id_missing_permission(mock_token_data, mock_supabase_client):
    """Test that 403 is returned when permission is missing."""
    # Create token data without the required permission
    token_data_no_perm = TokenData(
        sub="test-client-123",
        exp=1800000000,
        iat=1700000000,
        permissions=["some:other:permission"],
        iss="auth_service",
        client_id="test-client-123"
    )
    
    # Create request
    request = SuperIdRequest(count=1)
    
    # Test the endpoint
    with pytest.raises(Exception) as excinfo:
        await create_super_id(
            request=request,
            token_data=token_data_no_perm,
            supabase_client=mock_supabase_client
        )
    
    # Verify the exception is for 403 Forbidden
    assert "403" in str(excinfo.value)
    assert "super_id:generate" in str(excinfo.value)
    
    # Verify Supabase was not called
    mock_supabase_client.table.assert_not_called()


@pytest.mark.asyncio
async def test_create_super_id_database_error(mock_token_data, mock_supabase_client):
    """Test handling of database errors."""
    # Mock a database error
    mock_supabase_client.table().insert().execute.return_value = {
        "error": "Database error",
        "data": None
    }
    
    # Create request
    request = SuperIdRequest(count=1)
    
    # Test the endpoint
    with pytest.raises(Exception) as excinfo:
        await create_super_id(
            request=request,
            token_data=mock_token_data,
            supabase_client=mock_supabase_client
        )
    
    # Verify the exception is for 500 Internal Server Error
    assert excinfo.value.status_code == 500
    assert "Failed to generate or record super_id" in excinfo.value.detail or \
           "Failed to record generated super_ids" in excinfo.value.detail
