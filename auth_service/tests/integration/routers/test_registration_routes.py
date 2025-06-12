# Standard library imports
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

# Third-party imports
import pytest
from fastapi import status
from gotrue.errors import AuthApiError
from httpx import AsyncClient
from sqlalchemy import func as sql_func
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Test utilities
from tests.test_helpers import create_mock_supa_session, create_mock_supa_user

from auth_service.config import settings as app_config_settings

# Application-specific imports
from auth_service.main import app
from auth_service.models import Profile
from auth_service.routers.user_auth_routes import get_profile_by_user_id_from_db
from auth_service.supabase_client import get_supabase_client as real_get_supabase_client


@pytest.mark.asyncio
async def test_register_user_successful_email_confirmation_required(
    async_client: AsyncClient, db_session_for_crud: AsyncSession, monkeypatch
):
    user_id = uuid4()
    user_email = f"testconfirm_{user_id.hex[:8]}@example.com"
    user_password = "ValidPassword123!"
    user_username = f"testuserconfirm_{user_id.hex[:8]}"
    user_first_name = "Test"
    user_last_name = "UserConfirm"

    mock_user_data = create_mock_supa_user(
        email=user_email,
        id_val=user_id,
        confirmed=False,  # email_confirmed_at will be None
    )
    mock_session_data = create_mock_supa_session(user=mock_user_data)

    await db_session_for_crud.execute(
        text(
            "INSERT INTO auth.users (id, email, encrypted_password, role) VALUES (:id, :email, 'dummy_password', 'authenticated') ON CONFLICT (id) DO NOTHING;"
        ),
        {"id": user_id, "email": user_email},
    )
    await db_session_for_crud.commit()

    resolved_signup_response = MagicMock()
    resolved_signup_response.user = mock_user_data
    resolved_signup_response.session = mock_session_data

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.sign_up = AsyncMock(return_value=resolved_signup_response)

    async def mock_get_supabase_override():
        mock_supabase_client = AsyncMock()
        mock_supabase_client.auth = mock_supabase_auth
        return mock_supabase_client

    monkeypatch.setattr(
        app_config_settings, "supabase_email_confirmation_required", True
    )
    monkeypatch.setattr(app_config_settings, "supabase_auto_confirm_new_users", False)

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override
    try:
        request_payload = {
            "email": user_email,
            "password": user_password,
            "username": user_username,
            "first_name": user_first_name,
            "last_name": user_last_name,
        }
        response = await async_client.post("/auth/users/register", json=request_payload)

        assert (
            response.status_code == status.HTTP_201_CREATED
        ), f"Response: {response.text}"
        response_data = response.json()
        assert (
            "user registration initiated. please check your email to confirm your account."
            in response_data["message"].lower()
        )
        assert response_data["session"]["user"]["id"] == str(user_id)
        assert response_data["session"]["user"]["email"] == user_email
        assert response_data["session"]["user"].get("email_confirmed_at") is None

        assert "profile" in response_data
        profile_info = response_data["profile"]
        assert profile_info["user_id"] == str(user_id)
        assert profile_info["username"] == user_username
        assert profile_info["email"] == user_email
        assert profile_info["first_name"] == user_first_name
        assert profile_info["last_name"] == user_last_name
        assert profile_info["is_active"] is True

        expected_user_metadata = {
            "username": user_username,
            "first_name": user_first_name,
            "last_name": user_last_name,
        }
        mock_supabase_auth.sign_up.assert_called_once_with(
            {
                "email": user_email,
                "password": user_password,
                "options": {"data": expected_user_metadata},
            }
        )
        db_profile = await get_profile_by_user_id_from_db(
            db_session=db_session_for_crud,
            user_id=UUID(response_data["session"]["user"]["id"]),
        )
        assert db_profile is not None
        assert db_profile.username == user_username
        assert db_profile.is_active is True
    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]


@pytest.mark.asyncio
async def test_register_user_successful_auto_confirmed(
    async_client: AsyncClient, db_session_for_crud: AsyncSession, monkeypatch
):
    user_id = uuid4()
    user_email = f"autoconf_{user_id.hex[:8]}@example.com"
    user_password = "ValidPassword123!"
    user_username = f"autoconfuser_{user_id.hex[:8]}"
    user_first_name = "Auto"
    user_last_name = "Confirm"

    mock_user_data = create_mock_supa_user(
        email=user_email, id_val=user_id, confirmed=True
    )
    mock_session_data = create_mock_supa_session(user=mock_user_data)

    await db_session_for_crud.execute(
        text(
            "INSERT INTO auth.users (id, email, encrypted_password, role) VALUES (:id, :email, 'dummy_password', 'authenticated') ON CONFLICT (id) DO NOTHING;"
        ),
        {"id": user_id, "email": user_email},
    )
    await db_session_for_crud.commit()

    resolved_signup_response = MagicMock()
    resolved_signup_response.user = mock_user_data
    resolved_signup_response.session = mock_session_data

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.sign_up = AsyncMock(return_value=resolved_signup_response)

    async def mock_get_supabase_override():
        mock_supabase_client = AsyncMock()
        mock_supabase_client.auth = mock_supabase_auth
        return mock_supabase_client

    monkeypatch.setattr(
        app_config_settings, "supabase_email_confirmation_required", False
    )
    monkeypatch.setattr(app_config_settings, "supabase_auto_confirm_new_users", True)

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override
    try:
        request_payload = {
            "email": user_email,
            "password": user_password,
            "username": user_username,
            "first_name": user_first_name,
            "last_name": user_last_name,
        }
        response = await async_client.post("/auth/users/register", json=request_payload)

        assert (
            response.status_code == status.HTTP_201_CREATED
        ), f"Response: {response.text}"
        response_data = response.json()
        assert response_data["message"] == "User registered successfully."
        assert response_data["session"]["user"]["id"] == str(user_id)
        assert response_data["session"]["user"]["email"] == user_email
        assert response_data["session"]["user"].get("email_confirmed_at") is not None
        assert "access_token" in response_data["session"]

        assert "profile" in response_data
        profile_info = response_data["profile"]
        assert profile_info["user_id"] == str(user_id)
        assert profile_info["username"] == user_username
        assert profile_info["email"] == user_email
        assert profile_info["first_name"] == user_first_name
        assert profile_info["last_name"] == user_last_name
        assert profile_info["is_active"] is True

        expected_user_metadata = {
            "username": user_username,
            "first_name": user_first_name,
            "last_name": user_last_name,
        }
        mock_supabase_auth.sign_up.assert_called_once_with(
            {
                "email": user_email,
                "password": user_password,
                "options": {"data": expected_user_metadata},
            }
        )
        db_profile = await get_profile_by_user_id_from_db(
            db_session=db_session_for_crud,
            user_id=UUID(response_data["session"]["user"]["id"]),
        )
        assert db_profile is not None
        assert db_profile.username == user_username
    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]


@pytest.mark.asyncio
async def test_register_user_email_already_exists(
    async_client: AsyncClient, monkeypatch
):
    user_email = f"existing_{uuid4().hex[:8]}@example.com"
    mock_supabase_api_error = AuthApiError(
        message="User already registered", status=400, code="user_already_exists"
    )

    async def mock_get_supabase_override_email_exists():
        mock_supabase_client = AsyncMock()
        mock_supabase_client.auth.sign_up = AsyncMock(
            side_effect=mock_supabase_api_error
        )
        return mock_supabase_client

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = (
        mock_get_supabase_override_email_exists
    )
    try:
        response = await async_client.post(
            "/auth/users/register",
            json={
                "email": user_email,
                "password": "ValidPass123!",
                "username": "existinguser",
                "first_name": "Existing",
                "last_name": "User",
            },
        )
        assert (
            response.status_code == status.HTTP_409_CONFLICT
        ), f"Response: {response.text}"
        response_data = response.json()
        assert "User with this email already exists" in response_data["detail"]
    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]


@pytest.mark.asyncio
async def test_register_user_invalid_password_format(async_client: AsyncClient):
    user_email = f"weakpass_{uuid4().hex[:8]}@example.com"
    response = await async_client.post(
        "/auth/users/register",
        json={
            "email": user_email,
            "password": "short",
            "username": "weakpassuser",
            "first_name": "Weak",
            "last_name": "Password",
        },
    )
    assert (
        response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    ), f"Response: {response.text}"
    error_details = response.json()["detail"]
    assert isinstance(error_details, list)
    assert len(error_details) > 0
    password_error_found = False
    for error in error_details:
        if (
            isinstance(error, dict)
            and error.get("type") == "string_too_short"
            and isinstance(error.get("loc"), list)
            and len(error.get("loc")) > 1
            and error["loc"][0] == "body"
            and error["loc"][1] == "password"
        ):
            password_error_found = True
            assert "String should have at least 8 characters" in error.get("msg", "")
            break
    assert password_error_found, "Pydantic password length validation error not found."


@pytest.mark.asyncio
async def test_register_user_supabase_service_unavailable(
    async_client: AsyncClient, monkeypatch
):
    async def mock_get_supabase_override_service_unavailable():
        mock_supabase_client = AsyncMock()
        mock_auth_object = MagicMock()

        async def mock_sign_up_generic_error_func(*args, **kwargs):
            raise Exception("Supabase critical network failure")

        mock_auth_object.sign_up = mock_sign_up_generic_error_func
        mock_supabase_client.auth = mock_auth_object
        return mock_supabase_client

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = (
        mock_get_supabase_override_service_unavailable
    )
    try:
        response = await async_client.post(
            "/auth/users/register",
            json={
                "email": f"unavailable_{uuid4().hex[:8]}@example.com",
                "password": "ValidPassword123!",
                "username": "unavailableuser",
                "first_name": "Service",
                "last_name": "Down",
            },
        )
        assert (
            response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        ), f"Response: {response.text}"
        assert (
            "An unexpected error occurred during user registration."
            in response.json()["detail"]
        )
    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]
