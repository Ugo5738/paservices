from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import status
from httpx import AsyncClient, ASGITransport
from gotrue.errors import AuthApiError
from sqlalchemy.ext.asyncio import AsyncSession
from supabase._async.client import AsyncClient as AsyncSupabaseClient

from auth_service.config import settings
from auth_service.dependencies import get_app_settings
from auth_service.supabase_client import get_supabase_client
from auth_service.main import app


@pytest.fixture
def test_settings():
    """Test settings fixture"""
    mock_settings = MagicMock()
    mock_settings.ENVIRONMENT = "test"
    mock_settings.EMAIL_CONFIRMATION_REDIRECT_URL = (
        "http://localhost:3000/confirm-email"
    )
    return mock_settings


@pytest.fixture
def mock_supabase():
    """Mock Supabase client"""
    client = AsyncMock(spec=AsyncSupabaseClient)
    client.auth = AsyncMock()
    client.auth.reset_password_for_email = AsyncMock()
    return client


@pytest_asyncio.fixture
async def async_client(mock_supabase, test_settings):
    """Async test client fixture with mocked dependencies"""
    # Store the original dependency to restore it later
    original_dependencies = app.dependency_overrides.copy()
    
    # Override dependencies
    app.dependency_overrides[get_app_settings] = lambda: test_settings
    app.dependency_overrides[get_supabase_client] = lambda: mock_supabase

    # Create transport for FastAPI application testing
    transport = ASGITransport(app=app)
    
    # Use AsyncClient with transport for async tests
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    # Restore original dependencies
    app.dependency_overrides = original_dependencies


@pytest.mark.asyncio
async def test_resend_email_verification_success(async_client, mock_supabase):
    """Test successful email verification resend"""
    # Configure mock to return successfully
    mock_supabase.auth.reset_password_for_email.return_value = None

    # Make request to resend verification
    response = await async_client.post(
        "/auth/users/verify/resend", json={"email": "test@example.com"}
    )

    # Verify response
    assert response.status_code == status.HTTP_200_OK
    assert "message" in response.json()
    assert "Verification email resent" in response.json()["message"]

    # Verify Supabase was called with correct parameters
    mock_supabase.auth.reset_password_for_email.assert_called_once_with(
        email="test@example.com",
        options={"email_redirect_to": "http://localhost:3000/confirm-email"},
    )


@pytest.mark.asyncio
async def test_resend_email_verification_user_not_found(async_client, mock_supabase):
    """Test email verification resend when user not found"""
    # Configure mock to raise a user not found error
    error = AuthApiError(message="User not found", status=400, code="400")
    mock_supabase.auth.reset_password_for_email.side_effect = error

    # Make request to resend verification
    response = await async_client.post(
        "/auth/users/verify/resend", json={"email": "nonexistent@example.com"}
    )

    # Verify response - should still return 200 to avoid leaking info
    assert response.status_code == status.HTTP_200_OK
    assert "message" in response.json()
    assert "If your email exists" in response.json()["message"]


@pytest.mark.asyncio
async def test_resend_email_verification_already_verified(async_client, mock_supabase):
    """Test email verification resend when email already verified"""
    # Configure mock to raise an already verified error
    error = AuthApiError(message="Email already confirmed", status=400, code="400")
    mock_supabase.auth.reset_password_for_email.side_effect = error

    # Make request to resend verification
    response = await async_client.post(
        "/auth/users/verify/resend", json={"email": "verified@example.com"}
    )

    # Verify response
    assert response.status_code == status.HTTP_200_OK
    assert "message" in response.json()
    assert "already verified" in response.json()["message"]


@pytest.mark.asyncio
async def test_resend_email_verification_service_error(async_client, mock_supabase):
    """Test email verification resend when Supabase service has an error"""
    # Configure mock to raise a general service error
    error = AuthApiError(message="Service unavailable", status=503, code="503")
    mock_supabase.auth.reset_password_for_email.side_effect = error

    # Make request to resend verification
    response = await async_client.post(
        "/auth/users/verify/resend", json={"email": "test@example.com"}
    )

    # Verify response
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "detail" in response.json()
    assert "Error processing email verification" in response.json()["detail"]
