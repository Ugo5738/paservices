# Standard library imports
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

# Third-party imports
import pytest
from fastapi import HTTPException, status
from gotrue.errors import AuthApiError
from gotrue.types import UserAttributes  # For password update payload
from httpx import AsyncClient
from tests.test_helpers import create_mock_supa_user  # Absolute import from project root

from auth_service.dependencies.user_deps import (
    get_current_supabase_user as real_get_current_supabase_user,
)

# Application-specific imports
from auth_service.main import app  # Required for dependency overrides
from auth_service.supabase_client import get_supabase_client as real_get_supabase_client

# Note: `create_mock_supa_session` is not used in these password tests directly,
# but keeping test_helpers consistent.


@pytest.mark.asyncio
async def test_password_reset_request_successful(
    async_client: AsyncClient, monkeypatch
):
    test_email = f"reset_success_{uuid4().hex[:6]}@example.com"
    request_data = {"email": test_email}

    # Mock settings with expected redirect URL
    mock_settings = MagicMock()
    mock_settings.PASSWORD_RESET_REDIRECT_URL = "http://localhost:3000/auth/update-password"
    
    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.reset_password_for_email = AsyncMock(
        return_value=None
    )  # Supabase returns None on success

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance
        
    async def mock_get_app_settings_override():
        return mock_settings

    from auth_service.dependencies import get_app_settings
    
    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    original_get_settings = app.dependency_overrides.get(get_app_settings)
    
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override
    app.dependency_overrides[get_app_settings] = mock_get_app_settings_override
    
    try:
        response = await async_client.post(
            "/auth/users/password/reset", json=request_data
        )

        assert response.status_code == status.HTTP_200_OK, f"Response: {response.text}"
        response_data = response.json()
        assert (
            response_data["message"]
            == "If an account with this email exists, a password reset link has been sent."
        )
        mock_supabase_auth.reset_password_for_email.assert_called_once_with(
            email=test_email,
            options={"redirect_to": mock_settings.PASSWORD_RESET_REDIRECT_URL},
        )

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]
                
        if original_get_settings:
            app.dependency_overrides[get_app_settings] = original_get_settings
        else:
            if get_app_settings in app.dependency_overrides:
                del app.dependency_overrides[get_app_settings]


@pytest.mark.asyncio
async def test_password_reset_request_email_not_found(
    async_client: AsyncClient, monkeypatch
):
    test_email = f"reset_notfound_{uuid4().hex[:6]}@example.com"
    request_data = {"email": test_email}

    # Mock settings with expected redirect URL
    mock_settings = MagicMock()
    mock_settings.PASSWORD_RESET_REDIRECT_URL = "http://localhost:3000/auth/update-password"
    
    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.reset_password_for_email = AsyncMock(return_value=None)

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance
        
    async def mock_get_app_settings_override():
        return mock_settings

    from auth_service.dependencies import get_app_settings
    
    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    original_get_settings = app.dependency_overrides.get(get_app_settings)
    
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override
    app.dependency_overrides[get_app_settings] = mock_get_app_settings_override
    
    try:
        response = await async_client.post(
            "/auth/users/password/reset", json=request_data
        )

        assert response.status_code == status.HTTP_200_OK, f"Response: {response.text}"
        response_data = response.json()
        assert (
            response_data["message"]
            == "If an account with this email exists, a password reset link has been sent."
        )
        mock_supabase_auth.reset_password_for_email.assert_called_once_with(
            email=test_email,
            options={"redirect_to": mock_settings.PASSWORD_RESET_REDIRECT_URL},
        )

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]
                
        if original_get_settings:
            app.dependency_overrides[get_app_settings] = original_get_settings
        else:
            if get_app_settings in app.dependency_overrides:
                del app.dependency_overrides[get_app_settings]


@pytest.mark.asyncio
async def test_password_reset_request_invalid_email_format(
    async_client: AsyncClient, monkeypatch
):
    request_data = {"email": "invalid-email"}
    response = await async_client.post("/auth/users/password/reset", json=request_data)

    assert (
        response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    ), f"Response: {response.text}"
    response_data = response.json()
    assert "value is not a valid email address" in response_data["detail"][0]["msg"]


@pytest.mark.asyncio
async def test_password_reset_request_supabase_api_error_rate_limit(
    async_client: AsyncClient, monkeypatch
):
    test_email = f"reset_rate_limit_{uuid4().hex[:6]}@example.com"
    request_data = {"email": test_email}

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.reset_password_for_email = AsyncMock(
        side_effect=AuthApiError(
            message="Rate limit exceeded", status=429, code="rate_limit_exceeded"
        )
    )

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override
    try:
        response = await async_client.post(
            "/auth/users/password/reset", json=request_data
        )

        assert (
            response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        ), f"Response: {response.text}"
        response_data = response.json()
        assert (
            response_data["detail"]
            == "Password reset request failed: Rate limit exceeded"
        )

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]


@pytest.mark.asyncio
async def test_password_reset_request_supabase_api_error_generic(
    async_client: AsyncClient, monkeypatch
):
    test_email = f"reset_generic_error_{uuid4().hex[:6]}@example.com"
    request_data = {"email": test_email}

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.reset_password_for_email = AsyncMock(
        side_effect=AuthApiError(
            message="Some generic Supabase error", status=500, code="generic_error"
        )
    )

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override
    try:
        response = await async_client.post(
            "/auth/users/password/reset", json=request_data
        )

        assert (
            response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        ), f"Response: {response.text}"
        response_data = response.json()
        assert (
            response_data["detail"]
            == "Password reset request failed: Some generic Supabase error"
        )

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]


@pytest.mark.asyncio
async def test_password_update_successful(async_client: AsyncClient, monkeypatch):
    """
    Test successful password update for an authenticated user.
    """
    mock_user_id = uuid4()
    mock_current_user = create_mock_supa_user(
        id_val=mock_user_id, email="testuser@example.com"
    )
    new_password = "NewSecurePassword123!"

    # Mock the get_current_supabase_user dependency
    async def mock_get_current_user_override():
        return mock_current_user

    # Mock Supabase client's auth.update_user method
    mock_updated_supa_user_response = MagicMock()
    mock_updated_supa_user_response.user = create_mock_supa_user(
        id_val=mock_user_id, email="testuser@example.com"
    )

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.update_user = AsyncMock(
        return_value=mock_updated_supa_user_response
    )

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    original_get_current_user = app.dependency_overrides.get(
        real_get_current_supabase_user
    )

    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override
    app.dependency_overrides[real_get_current_supabase_user] = (
        mock_get_current_user_override
    )

    try:
        response = await async_client.post(
            "/auth/users/password/update",
            json={"new_password": new_password},
            headers={"Authorization": f"Bearer mock_access_token_for_{mock_user_id}"},
        )

        assert response.status_code == status.HTTP_200_OK, f"Response: {response.text}"
        response_data = response.json()
        assert response_data["message"] == "Password updated successfully."

        mock_supabase_auth.update_user.assert_called_once()

        call_args = mock_supabase_auth.update_user.call_args
        assert call_args is not None, "update_user was not called with any arguments"

        assert "attributes" in call_args.kwargs
        user_attributes_arg = call_args.kwargs["attributes"]
        assert isinstance(user_attributes_arg, dict), "UserAttributes should be a dict"
        assert (
            "password" in user_attributes_arg
        ), "Password key missing in UserAttributes"
        assert user_attributes_arg["password"] == new_password

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:  # pragma: no cover
                del app.dependency_overrides[real_get_supabase_client]

        if original_get_current_user:
            app.dependency_overrides[real_get_current_supabase_user] = (
                original_get_current_user
            )
        else:
            if (
                real_get_current_supabase_user in app.dependency_overrides
            ):  # pragma: no cover
                del app.dependency_overrides[real_get_current_supabase_user]


@pytest.mark.asyncio
async def test_password_update_weak_password(async_client: AsyncClient, monkeypatch):
    """
    Test password update attempt with a weak password.
    Simulates Supabase rejecting the password due to strength policies.
    """
    mock_user_id = uuid4()
    mock_current_user = create_mock_supa_user(
        id_val=mock_user_id, email="testuser@example.com"
    )
    weak_password = "weak"

    async def mock_get_current_user_override():
        return mock_current_user

    mock_supabase_auth = AsyncMock()
    weak_password_error_message = "Password should be stronger."
    mock_supabase_auth.update_user = AsyncMock(
        side_effect=AuthApiError(
            message=weak_password_error_message,
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="weak_password",
        )
    )

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    original_get_current_user = app.dependency_overrides.get(
        real_get_current_supabase_user
    )

    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override
    app.dependency_overrides[real_get_current_supabase_user] = (
        mock_get_current_user_override
    )

    try:
        response = await async_client.post(
            "/auth/users/password/update",
            json={"new_password": weak_password},
            headers={"Authorization": f"Bearer mock_access_token_for_{mock_user_id}"},
        )

        assert (
            response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        ), f"Response: {response.text}"
        response_data = response.json()
        assert isinstance(response_data["detail"], list)
        assert len(response_data["detail"]) == 1
        detail_error = response_data["detail"][0]
        assert detail_error["type"] == "string_too_short"
        assert detail_error["loc"] == ["body", "new_password"]
        assert "ctx" in detail_error and detail_error["ctx"]["min_length"] == 8
        assert detail_error["input"] == weak_password
        assert "String should have at least 8 characters" in detail_error["msg"]

        mock_supabase_auth.update_user.assert_not_called()

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:  # pragma: no cover
                del app.dependency_overrides[real_get_supabase_client]

        if original_get_current_user:
            app.dependency_overrides[real_get_current_supabase_user] = (
                original_get_current_user
            )
        else:
            if (
                real_get_current_supabase_user in app.dependency_overrides
            ):  # pragma: no cover
                del app.dependency_overrides[real_get_current_supabase_user]


@pytest.mark.asyncio
async def test_password_update_invalid_token(async_client: AsyncClient, monkeypatch):
    """
    Test password update attempt with an invalid/expired authentication token.
    """
    new_password = "NewSecurePassword123!"
    expected_error_detail = "Invalid authentication credentials"

    async def mock_get_current_user_auth_error():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=expected_error_detail
        )

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.update_user = AsyncMock()

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    original_get_current_user = app.dependency_overrides.get(
        real_get_current_supabase_user
    )

    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override
    app.dependency_overrides[real_get_current_supabase_user] = (
        mock_get_current_user_auth_error
    )

    try:
        response = await async_client.post(
            "/auth/users/password/update",
            json={"new_password": new_password},
            headers={"Authorization": "Bearer an_invalid_or_expired_token"},
        )

        assert (
            response.status_code == status.HTTP_401_UNAUTHORIZED
        ), f"Response: {response.text}"
        response_data = response.json()
        assert response_data["detail"] == expected_error_detail

        mock_supabase_auth.update_user.assert_not_called()

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:  # pragma: no cover
                del app.dependency_overrides[real_get_supabase_client]

        if original_get_current_user:
            app.dependency_overrides[real_get_current_supabase_user] = (
                original_get_current_user
            )
        else:
            if (
                real_get_current_supabase_user in app.dependency_overrides
            ):  # pragma: no cover
                del app.dependency_overrides[real_get_current_supabase_user]
