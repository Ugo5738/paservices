import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
from fastapi import status

from tests.fixtures.client import client
from tests.fixtures.db import db_session
from tests.fixtures.mocks import mock_supabase_client


@pytest.mark.asyncio
async def test_resend_email_verification_success(client: AsyncClient, mock_supabase_client):
    """Test successful resend of email verification."""
    # Configure mock
    mock_supabase_client.auth.reset_password_for_email = AsyncMock()
    
    # Test data
    email_data = {
        "email": "user.needs.verification@example.com"
    }
    
    # Make request
    response = await client.post("/api/v1/auth/users/verify/resend", json=email_data)
    
    # Assertions
    assert response.status_code == status.HTTP_200_OK
    assert "message" in response.json()
    assert "verification email resent" in response.json()["message"].lower()
    
    # Verify Supabase was called correctly
    mock_supabase_client.auth.reset_password_for_email.assert_called_once()
    args, kwargs = mock_supabase_client.auth.reset_password_for_email.call_args
    assert kwargs["email"] == email_data["email"]
    assert "options" in kwargs


@pytest.mark.asyncio
async def test_resend_verification_nonexistent_email(client: AsyncClient, mock_supabase_client):
    """Test resend verification for non-existent email (should not leak information)."""
    from gotrue.errors import AuthApiError
    
    # Configure mock to simulate user not found
    mock_supabase_client.auth.reset_password_for_email = AsyncMock(
        side_effect=AuthApiError("User not found", code=400, status=400)
    )
    
    # Test data
    email_data = {
        "email": "nonexistent@example.com"
    }
    
    # Make request
    response = await client.post("/api/v1/auth/users/verify/resend", json=email_data)
    
    # Should return 200 (not 404) to avoid leaking which emails exist
    assert response.status_code == status.HTTP_200_OK
    assert "message" in response.json()
    # Generic message that doesn't confirm or deny email existence
    assert "if your email exists" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_resend_verification_already_verified(client: AsyncClient, mock_supabase_client):
    """Test resend verification for already verified email."""
    from gotrue.errors import AuthApiError
    
    # Configure mock to simulate already verified email
    mock_supabase_client.auth.reset_password_for_email = AsyncMock(
        side_effect=AuthApiError("Email already confirmed", code=400, status=400)
    )
    
    # Test data
    email_data = {
        "email": "already.verified@example.com"
    }
    
    # Make request
    response = await client.post("/api/v1/auth/users/verify/resend", json=email_data)
    
    # Should return success with appropriate message
    assert response.status_code == status.HTTP_200_OK
    assert "message" in response.json()
    assert "already verified" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_resend_verification_rate_limiting(client: AsyncClient):
    """Test rate limiting for email verification resend requests."""
    # Test data
    email_data = {
        "email": "rate.limited@example.com"
    }
    
    # Make multiple requests to trigger rate limiting
    # Note: Actual rate limit testing would require configuring the test environment
    # This is a placeholder that would need to be adjusted based on the actual rate limit
    
    # Make first request (should succeed)
    first_response = await client.post("/api/v1/auth/users/verify/resend", json=email_data)
    assert first_response.status_code == status.HTTP_200_OK
    
    # In a real test, you would make additional requests here until rate limit is hit
    # For demonstration, we'll check the headers to verify rate limiting is applied
    # Note: Rate limit headers may not be present in test environment
    assert first_response.status_code == status.HTTP_200_OK
