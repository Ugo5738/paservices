import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from httpx import AsyncClient
from fastapi import status

from tests.fixtures.client import client
from tests.fixtures.db import db_session
from tests.fixtures.mocks import mock_supabase_client


@pytest.mark.asyncio
async def test_magic_link_login_success(client: AsyncClient, mock_supabase_client):
    """Test successful magic link login request."""
    # Configure the mock to simulate successful OTP generation
    mock_supabase_client.auth.sign_in_with_otp = AsyncMock()
    
    # Test data
    login_data = {
        "email": "test.magic.link@example.com"
    }
    
    # Make request to magic link endpoint
    response = await client.post("/api/v1/auth/users/login/magiclink", json=login_data)
    
    # Assertions
    assert response.status_code == status.HTTP_200_OK
    assert "message" in response.json()
    assert "magic link" in response.json()["message"].lower()
    
    # Verify Supabase was called with correct parameters
    mock_supabase_client.auth.sign_in_with_otp.assert_called_once_with(
        {"email": login_data["email"], "options": {}}
    )


@pytest.mark.asyncio
async def test_magic_link_login_invalid_email(client: AsyncClient):
    """Test magic link login with invalid email format."""
    # Invalid email
    login_data = {
        "email": "not-a-valid-email"
    }
    
    # Make request with invalid email
    response = await client.post("/api/v1/auth/users/login/magiclink", json=login_data)
    
    # Should fail validation
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_magic_link_login_supabase_error(client: AsyncClient, mock_supabase_client):
    """Test handling of Supabase API errors during magic link login."""
    # Configure mock to raise exception
    from gotrue.errors import AuthApiError
    error_message = "API error during magic link generation"
    mock_supabase_client.auth.sign_in_with_otp = AsyncMock(
        side_effect=AuthApiError(error_message, code=400, status=400)
    )
    
    # Test data
    login_data = {
        "email": "test.error@example.com"
    }
    
    # Make request
    response = await client.post("/api/v1/auth/users/login/magiclink", json=login_data)
    
    # Should return an error
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "error" in response.json()["detail"].lower()
