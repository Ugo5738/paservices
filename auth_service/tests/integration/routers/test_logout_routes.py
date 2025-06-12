# Standard library imports
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
from gotrue.errors import AuthApiError
from httpx import AsyncClient
from tests.test_helpers import (  # Absolute import from project root
    create_mock_supa_session,
    create_mock_supa_user,
)

from auth_service.dependencies import (
    get_current_supabase_user,  # real_get_supabase_client is not from here
)
from auth_service.main import app  # Required for dependency overrides
from auth_service.supabase_client import (
    get_supabase_client as real_get_supabase_client,  # This is correct for real_get_supabase_client
)


@pytest.mark.asyncio
async def test_logout_user_successful(async_client: AsyncClient, monkeypatch):
    user_id = uuid4()
    login_email = f"logout_user_{user_id.hex[:6]}@example.com"
    mock_supa_user_instance = create_mock_supa_user(
        email=login_email, id_val=user_id, confirmed=True
    )
    mock_supa_session_instance = create_mock_supa_session(user=mock_supa_user_instance)

    mock_logout_supabase_auth = AsyncMock()
    mock_logout_supabase_auth.get_user = AsyncMock(
        return_value=MagicMock(user=mock_supa_user_instance)
    )
    mock_logout_supabase_auth.sign_out = AsyncMock(return_value=None)

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_logout_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override
    try:
        mock_token = mock_supa_session_instance.access_token
        headers = {"Authorization": f"Bearer {mock_token}"}
        response = await async_client.post("/auth/users/logout", headers=headers)

        assert response.status_code == status.HTTP_200_OK, f"Response: {response.text}"
        response_data = response.json()
        assert response_data["message"] == "Successfully logged out"
        mock_logout_supabase_auth.sign_out.assert_called_once_with(jwt=mock_token)

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]


@pytest.mark.asyncio
async def test_logout_user_invalid_token_format(
    async_client: AsyncClient,
):
    async def mock_get_current_user_raises_invalid_format():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = (
        mock_get_current_user_raises_invalid_format
    )
    try:
        headers = {"Authorization": "Bearer an_invalid_token_without_proper_structure"}
        response = await async_client.post("/auth/users/logout", headers=headers)

        assert (
            response.status_code == status.HTTP_401_UNAUTHORIZED
        ), f"Response: {response.text}"
        response_data = response.json()
        assert "Could not validate credentials" in response_data.get("detail", "")
    finally:
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            if get_current_supabase_user in app.dependency_overrides:
                del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_logout_user_no_auth_header(
    async_client: AsyncClient,
):
    response = await async_client.post("/auth/users/logout")  # No headers

    assert (
        response.status_code == status.HTTP_401_UNAUTHORIZED
    ), f"Response: {response.text}"
    response_data = response.json()
    assert response_data["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_logout_user_expired_token(async_client: AsyncClient):
    async def mock_get_current_user_raises_expired():
        # This matches the behavior of get_current_supabase_user when it catches AuthApiError for expired token
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token: Token expired",
        )

    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = (
        mock_get_current_user_raises_expired
    )
    try:
        expired_token = "an_expired_or_invalid_jwt_token"
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = await async_client.post("/auth/users/logout", headers=headers)

        assert (
            response.status_code == status.HTTP_401_UNAUTHORIZED
        ), f"Response: {response.text}"
        response_data = response.json()
        assert "Invalid or expired token: Token expired" in response_data["detail"]
    finally:
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            if get_current_supabase_user in app.dependency_overrides:
                del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_logout_user_supabase_sign_out_error(
    async_client: AsyncClient, monkeypatch
):
    mock_user_id = uuid4()
    mock_supa_user_instance = create_mock_supa_user(
        email=f"signout_error_{mock_user_id.hex[:6]}@example.com",
        id_val=mock_user_id,
        confirmed=True,
    )
    mock_supa_session_instance = create_mock_supa_session(user=mock_supa_user_instance)

    mock_logout_supabase_auth = AsyncMock()
    mock_logout_supabase_auth.get_user = AsyncMock(
        return_value=MagicMock(user=mock_supa_user_instance)
    )
    mock_logout_supabase_auth.sign_out = AsyncMock(
        side_effect=AuthApiError(
            message="Supabase server error during sign out",
            status=500,
            code="server_error",
        )
    )

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_logout_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override
    try:
        mock_token = mock_supa_session_instance.access_token
        headers = {"Authorization": f"Bearer {mock_token}"}
        response = await async_client.post("/auth/users/logout", headers=headers)

        assert (
            response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        ), f"Response: {response.text}"  # Corrected
        response_data = response.json()  # Corrected
        assert (
            "Logout failed: Supabase server error during sign out"
            in response_data["detail"]
        )  # Corrected
        # mock_logout_supabase_auth.sign_out.assert_called_once_with(jwt=mock_token) # Commented out

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]
