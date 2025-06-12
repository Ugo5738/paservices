# Standard library imports
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

# Third-party imports
import pytest
from fastapi import status
from gotrue.errors import AuthApiError
from httpx import AsyncClient
from httpx import Response as HttpxResponse
from tests.test_helpers import (  # Absolute import from project root
    create_mock_supa_session,
    create_mock_supa_user,
)

from auth_service.config import settings as app_config_settings

# Application-specific imports
from auth_service.main import app  # Required for dependency overrides
from auth_service.schemas.user_schemas import (
    MagicLinkLoginRequest,
    MagicLinkSentResponse,
    SupabaseSession,
    UserLoginRequest,
)
# Import the real supabase client function
from auth_service.supabase_client import get_supabase_client


# test_login_user_successful
@pytest.mark.asyncio
async def test_login_user_successful(
    async_client: AsyncClient, monkeypatch  # Ensure monkeypatch is present
):
    user_id = uuid4()
    test_login_data = {
        "email": f"login_user_{user_id.hex[:6]}@example.com",
        "password": "aSecurePassword123",
    }

    mock_supa_user_instance = create_mock_supa_user(
        email=test_login_data["email"], id_val=user_id, confirmed=True
    )
    mock_supa_session_instance = create_mock_supa_session(user=mock_supa_user_instance)

    mock_auth_response = MagicMock()
    mock_auth_response.user = mock_supa_user_instance
    mock_auth_response.session = mock_supa_session_instance

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.sign_in_with_password = AsyncMock(
        return_value=mock_auth_response
    )

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(get_supabase_client)
    app.dependency_overrides[get_supabase_client] = mock_get_supabase_override

    try:
        response = await async_client.post("/auth/users/login", json=test_login_data)

        assert response.status_code == status.HTTP_200_OK, f"Response: {response.text}"
        response_data = response.json()
        assert "access_token" in response_data
        assert (
            response_data["access_token"]
            == f"mock_access_token_for_{mock_supa_user_instance.id}"
        )
        assert "user" in response_data
        assert response_data["user"]["email"] == test_login_data["email"]
        assert response_data["user"]["id"] == str(user_id)

    finally:
        if original_get_supabase:
            app.dependency_overrides[get_supabase_client] = original_get_supabase
        else:
            if get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[get_supabase_client]


# test_login_user_invalid_credentials
@pytest.mark.asyncio
async def test_login_user_invalid_credentials(async_client: AsyncClient, monkeypatch):
    test_login_data = {
        "email": "user@example.com",
        "password": "wrongPassword123",
    }

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.sign_in_with_password = AsyncMock(
        side_effect=AuthApiError(
            "Invalid login credentials", status=400, code="invalid_grant"
        )
    )

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(get_supabase_client)
    app.dependency_overrides[get_supabase_client] = mock_get_supabase_override

    try:
        response = await async_client.post("/auth/users/login", json=test_login_data)

        assert (
            response.status_code == status.HTTP_401_UNAUTHORIZED
        ), f"Response: {response.text}"
        response_data = response.json()
        assert response_data["detail"] == "Invalid login credentials"

    finally:
        if original_get_supabase:
            app.dependency_overrides[get_supabase_client] = original_get_supabase
        else:
            if get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[get_supabase_client]


# test_login_user_not_found
@pytest.mark.asyncio
async def test_login_user_not_found(async_client: AsyncClient, monkeypatch):
    test_login_data = {
        "email": "nonexistent_user@example.com",
        "password": "anyPassword123",
    }

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.sign_in_with_password = AsyncMock(
        side_effect=AuthApiError(
            "Invalid login credentials", status=400, code="invalid_grant"
        )
    )

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(get_supabase_client)
    app.dependency_overrides[get_supabase_client] = mock_get_supabase_override

    try:
        response = await async_client.post("/auth/users/login", json=test_login_data)

        assert (
            response.status_code == status.HTTP_401_UNAUTHORIZED
        ), f"Response: {response.text}"
        response_data = response.json()
        assert response_data["detail"] == "Invalid login credentials"

    finally:
        if original_get_supabase:
            app.dependency_overrides[get_supabase_client] = original_get_supabase
        else:
            if get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[get_supabase_client]


# test_login_user_email_not_confirmed
@pytest.mark.asyncio
async def test_login_user_email_not_confirmed(async_client: AsyncClient, monkeypatch):
    user_id = uuid4()
    test_login_data = {
        "email": f"unconfirmed_{user_id.hex[:6]}@example.com",
        "password": "aSecurePassword123",
    }

    mock_supabase_auth = AsyncMock()
    mock_response_unconfirmed = HttpxResponse(
        status_code=400,
        json={"error": "access_denied", "error_description": "Email not confirmed"},
    )
    mock_supabase_auth.sign_in_with_password = AsyncMock(
        side_effect=AuthApiError(
            message="Email not confirmed",
            status=mock_response_unconfirmed.status_code,
            code="access_denied",
        )
    )

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(get_supabase_client)
    app.dependency_overrides[get_supabase_client] = mock_get_supabase_override

    try:
        monkeypatch.setattr(
            app_config_settings, "supabase_email_confirmation_required", True
        )

        response = await async_client.post("/auth/users/login", json=test_login_data)

        assert (
            response.status_code == status.HTTP_401_UNAUTHORIZED
        ), f"Response: {response.text}"
        response_data = response.json()
        assert (
            response_data["detail"] == "Email not confirmed. Please check your inbox."
        )

    finally:
        if original_get_supabase:
            app.dependency_overrides[get_supabase_client] = original_get_supabase
        else:
            if get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[get_supabase_client]


# test_login_magic_link_successful_request
@pytest.mark.asyncio
async def test_login_magic_link_successful_request(
    async_client: AsyncClient, monkeypatch
):
    test_email = "magic_user@example.com"
    test_login_data = {"email": test_email}

    mock_supabase_auth = AsyncMock()
    mock_otp_response = MagicMock()
    mock_supabase_auth.sign_in_with_otp = AsyncMock(return_value=mock_otp_response)

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(get_supabase_client)
    app.dependency_overrides[get_supabase_client] = mock_get_supabase_override

    try:
        response = await async_client.post(
            "/auth/users/login/magiclink", json=test_login_data
        )

        assert response.status_code == status.HTTP_200_OK, f"Response: {response.text}"
        response_data = response.json()
        assert (
            response_data["message"]
            == f"Magic link sent to {test_email}. Please check your inbox."
        )
        mock_supabase_auth.sign_in_with_otp.assert_called_once_with(
            {"email": test_email, "options": {}}
        )

    finally:
        if original_get_supabase:
            app.dependency_overrides[get_supabase_client] = original_get_supabase
        else:
            if get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[get_supabase_client]


# test_login_magic_link_invalid_email_format
@pytest.mark.asyncio
async def test_login_magic_link_invalid_email_format(
    async_client: AsyncClient,
):
    test_login_data = {"email": "notanemail"}

    response = await async_client.post(
        "/auth/users/login/magiclink", json=test_login_data
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    response_data = response.json()
    assert "detail" in response_data
    assert any(
        field_error["type"] == "value_error" and field_error["loc"] == ["body", "email"]
        for field_error in response_data["detail"]
    )


# test_login_magic_link_supabase_api_error
@pytest.mark.asyncio
async def test_login_magic_link_supabase_api_error(
    async_client: AsyncClient, monkeypatch
):
    test_email = "error_user@example.com"
    test_login_data = {"email": test_email}

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.sign_in_with_otp = AsyncMock(
        side_effect=AuthApiError(
            message="Supabase rate limit exceeded",
            status=429,
            code="rate_limit_exceeded",
        )
    )

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(get_supabase_client)
    app.dependency_overrides[get_supabase_client] = mock_get_supabase_override

    try:
        response = await async_client.post(
            "/auth/users/login/magiclink", json=test_login_data
        )

        assert (
            response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        ), f"Response: {response.text}"
        response_data = response.json()
        assert (
            response_data["detail"]
            == "Failed to send magic link: Supabase rate limit exceeded"
        )

    finally:
        if original_get_supabase:
            app.dependency_overrides[get_supabase_client] = original_get_supabase
        else:
            if get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[get_supabase_client]
