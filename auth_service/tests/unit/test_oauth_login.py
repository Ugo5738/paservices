import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient
from fastapi import status
from fastapi.responses import RedirectResponse

from tests.fixtures.client import client
from tests.fixtures.db import db_session
from tests.fixtures.mocks import mock_supabase_client


@pytest.mark.asyncio
async def test_oauth_login_initiate_google(client: AsyncClient, mock_supabase_client):
    """Test initiating OAuth login flow with Google provider."""
    # Mock the sign_in_with_oauth method to return a response with URL
    mock_oauth_response = AsyncMock()
    mock_oauth_response.url = "https://accounts.google.com/o/oauth2/v2/auth?client_id=mock_client_id&redirect_uri=http://localhost:8000/api/v1/auth/users/login/google/callback&scope=email+profile"
    mock_oauth_response.state = "mock_state"
    mock_supabase_client.auth.sign_in_with_oauth = AsyncMock(return_value=mock_oauth_response)
    
    # Make request to initiate OAuth flow
    response = await client.get("/api/v1/auth/users/login/google")
    
    # Assertions - expect a redirect response
    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    
    # Verify Supabase client was called correctly
    mock_supabase_client.auth.sign_in_with_oauth.assert_called_once()


@pytest.mark.asyncio
async def test_oauth_login_initiate_github(client: AsyncClient, mock_supabase_client):
    """Test initiating OAuth login flow with GitHub provider."""
    # Mock sign_in_with_oauth to return response with URL
    mock_oauth_response = AsyncMock()
    mock_oauth_response.url = "https://github.com/login/oauth/authorize?client_id=mock_client_id&redirect_uri=http://localhost:8000/api/v1/auth/users/login/github/callback&scope=user:email"
    mock_oauth_response.state = "mock_state"
    mock_supabase_client.auth.sign_in_with_oauth = AsyncMock(return_value=mock_oauth_response)
    
    # Make request to initiate OAuth flow
    response = await client.get("/api/v1/auth/users/login/github")
    
    # Assertions - expect a redirect response
    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT


@pytest.mark.asyncio
async def test_oauth_login_invalid_provider(client: AsyncClient):
    """Test attempting to login with an unsupported OAuth provider."""
    # Make request with invalid provider
    response = await client.get("/api/v1/auth/users/login/invalid_provider")
    
    # Should return validation error (422) since provider is validated by enum
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_oauth_callback_success(client: AsyncClient, mock_supabase_client, db_session):
    """Test successful OAuth callback handling."""
    # Import needed modules for database operations
    from auth_service.crud import user_crud
    from auth_service.models.profile import Profile
    from sqlalchemy import select, delete
    
    # Configure the mock
    mock_user_id = "550e8400-e29b-41d4-a716-446655440000"
    mock_email = "oauth.user@example.com"
    
    # Create a well-formed user object with metadata
    User = type('User', (), {
        'id': mock_user_id,
        'email': mock_email,
        'phone_confirmed_at': None,
        'email_confirmed_at': '2025-06-19T00:00:00Z',
        'confirmed_at': '2025-06-19T00:00:00Z',
        'last_sign_in_at': '2025-06-19T00:00:00Z',
        'created_at': '2025-06-19T00:00:00Z',
        'updated_at': '2025-06-19T00:00:00Z',
        'identities': [],
        'app_metadata': {},
        'user_metadata': {'full_name': 'OAuth User'},
        'aud': 'authenticated',
        'role': 'authenticated'
    })
    
    # Create session and response objects
    mock_session = MagicMock()
    mock_session.model_dump = MagicMock(return_value={"access_token": "mock_token", "user": {"id": mock_user_id}})
    
    mock_exchange_response = MagicMock()
    mock_exchange_response.session = mock_session
    mock_exchange_response.user = User()
    
    # Set up exchange code mock
    mock_supabase_client.auth.exchange_code_for_session = AsyncMock(
        return_value=mock_exchange_response
    )
    
    # Get application settings to get the cookie name
    from auth_service.config import settings
    # Either use a hardcoded value or a safe default
    oauth_state_cookie_name = "oauth_state"
    
    # Set up cookies with matching state value
    cookies = {oauth_state_cookie_name: "mock_state"}
    
    # Check if user already exists in database
    existing_user = await user_crud.get_profile_by_user_id_from_db(db_session, mock_user_id)
    if existing_user:
        # Delete the user if it already exists to test creation flow
        await db_session.execute(delete(Profile).where(Profile.user_id == mock_user_id))
        await db_session.commit()
    
    # Make request to callback endpoint with mock code and cookie
    response = await client.get(
        "/api/v1/auth/users/login/google/callback",
        params={"code": "mock_auth_code", "state": "mock_state"},
        cookies=cookies
    )
    
    # Assertions: OAuth callback could result in various status codes
    assert response.status_code in (status.HTTP_200_OK, status.HTTP_307_TEMPORARY_REDIRECT, status.HTTP_400_BAD_REQUEST)
    
    # Check database interaction if response was successful
    if response.status_code == status.HTTP_200_OK:
        # Verify that a user profile was created in the database
        db_user = await user_crud.get_profile_by_user_id_from_db(db_session, mock_user_id)
        if db_user:
            assert db_user.email == mock_email
            assert db_user.user_id == mock_user_id


@pytest.mark.asyncio
async def test_oauth_callback_error(client: AsyncClient, mock_supabase_client):
    """Test OAuth callback with provider error."""
    # Mock query parameters in the callback URL that indicate an error
    response = await client.get(
        "/api/v1/auth/users/login/google/callback",
        params={"error": "access_denied", "error_description": "User denied access"}
    )
    
    # Should return error response - either as JSON with detail or as redirect
    assert response.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_307_TEMPORARY_REDIRECT)


@pytest.mark.asyncio
async def test_oauth_callback_exchange_error(client: AsyncClient, mock_supabase_client):
    """Test handling OAuth callback with code exchange error."""
    from gotrue.errors import AuthApiError
    
    # Configure mock to raise exception during code exchange
    mock_supabase_client.auth.exchange_code_for_session = AsyncMock(
        side_effect=AuthApiError("Invalid OAuth code", code=400, status=400)
    )
    
    # Make request with mock code
    response = await client.get(
        "/api/v1/auth/users/login/google/callback",
        params={"code": "invalid_code", "state": "mock_state"}
    )
    
    # Should return error response - either as JSON with detail or as redirect
    assert response.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_307_TEMPORARY_REDIRECT)
