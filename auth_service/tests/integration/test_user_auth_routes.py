from datetime import datetime, timezone
from unittest.mock import ANY, AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, status
from gotrue.errors import AuthApiError  # Corrected import for login error tests
from gotrue.types import UserAttributes  # For password update payload
from httpx import AsyncClient
from httpx import Response as HttpxResponse  # Added Response for AuthApiError mocking
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.config import settings as app_config_settings  # For monkeypatching
from auth_service.dependencies.user_deps import (
    get_current_supabase_user as real_get_current_supabase_user,  # Placeholder for actual dependency
)
from auth_service.main import app  # To access app.dependency_overrides
from auth_service.models.profile import Profile  # For spec in MagicMock
from auth_service.routers import user_auth_routes  # Added import
from auth_service.schemas.user_schemas import (  # Added for login, magic link, logout, password reset, and OAuth tests
    MagicLinkLoginRequest,
    MagicLinkSentResponse,
    OAuthProvider,
    OAuthRedirectResponse,
    PasswordResetRequest,
    PasswordUpdateRequest,
    ProfileResponse,
    SupabaseSession,
    SupabaseUser,
    UserLoginRequest,
)
from auth_service.supabase_client import get_supabase_client as real_get_supabase_client

from ..test_helpers import (
    create_default_mock_settings,
    create_mock_supa_session,
    create_mock_supa_user,
)

# --- OAuth Login Initiation Tests ---


@pytest.mark.asyncio
async def test_oauth_login_initiate_google_ok(async_client: AsyncClient, monkeypatch):
    """
    Test successful OAuth login initiation for Google.
    Ensures the endpoint returns a valid authorization URL.
    """
    provider = OAuthProvider.GOOGLE
    expected_auth_url = f"https://supabase.example.com/auth/v1/authorize?provider={provider.value}&redirect_to=http://localhost:3000/auth/callback"

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.sign_in_with_oauth = AsyncMock(
        return_value=MagicMock(
            url=expected_auth_url, state="mocked_oauth_state_value"
        )  # Provide state from the beginning
    )

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override

    mock_app_settings = create_default_mock_settings()
    mock_app_settings.OAUTH_REDIRECT_URI = "http://localhost:3000/auth/callback"
    mock_app_settings.OAUTH_STATE_COOKIE_NAME = (
        "test_pa_oauth_state"  # Use a distinct name for testing if desired
    )
    mock_app_settings.OAUTH_STATE_COOKIE_MAX_AGE_SECONDS = 300
    mock_app_settings.ENVIRONMENT = (
        "development"  # To match secure=False for cookie in dev
    )

    original_get_app_settings = app.dependency_overrides.get(
        user_auth_routes.get_app_settings
    )
    app.dependency_overrides[user_auth_routes.get_app_settings] = (
        lambda: mock_app_settings
    )

    try:
        # Make the request ONCE
        response = await async_client.get(
            f"/auth/users/login/{provider.value}", follow_redirects=False
        )

        assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT, response.text
        assert response.headers["location"] == expected_auth_url

        # Check for the state cookie
        assert mock_app_settings.OAUTH_STATE_COOKIE_NAME in response.cookies
        state_cookie_value = response.cookies[mock_app_settings.OAUTH_STATE_COOKIE_NAME]
        assert (
            state_cookie_value == "mocked_oauth_state_value"
        )  # Check against the state provided by the mock

        mock_supabase_auth.sign_in_with_oauth.assert_called_once_with(
            provider=provider.value,
            options={"redirect_to": "http://localhost:3000/auth/callback"},
        )
    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:  # pragma: no cover
                del app.dependency_overrides[real_get_supabase_client]
        if original_get_app_settings:
            app.dependency_overrides[user_auth_routes.get_app_settings] = (
                original_get_app_settings
            )
        else:
            if user_auth_routes.get_app_settings in app.dependency_overrides:
                del app.dependency_overrides[user_auth_routes.get_app_settings]


@pytest.mark.asyncio
async def test_oauth_login_initiate_unsupported_provider(
    async_client: AsyncClient, monkeypatch
):
    """
    Test OAuth login initiation with an unsupported provider.
    Ensures the endpoint returns a 400 Bad Request.
    """
    unsupported_provider = "faceboook"

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.sign_in_with_oauth = AsyncMock()  # Should not be called

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override

    try:
        response = await async_client.get(f"/auth/users/login/{unsupported_provider}")

        assert (
            response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        ), response.text
        response_data = response.json()
        # Detail assertion will be refined after seeing Pydantic's error message
        # assert "Unsupported OAuth provider" in response_data["detail"]
        # assert unsupported_provider in response_data["detail"]

        # Ensure Supabase sign_in_with_oauth was NOT called
        mock_supabase_auth.sign_in_with_oauth.assert_not_called()
    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:  # pragma: no cover
                del app.dependency_overrides[real_get_supabase_client]


# --- OAuth Callback Tests ---


@pytest.mark.asyncio
async def test_oauth_callback_google_successful_new_user(
    async_client: AsyncClient,
    monkeypatch,
    db_session_for_crud: AsyncSession,  # For profile creation
):
    """
    Test successful OAuth callback for a new user via Google.
    Ensures code is exchanged, session is returned, and a new profile is created.
    """
    provider = OAuthProvider.GOOGLE
    auth_code = "valid_auth_code_for_new_user"
    state = "random_state_string"
    mock_user_id = uuid4()
    mock_email = f"new_oauth_user_{mock_user_id.hex[:6]}@example.com"

    mock_supa_user = create_mock_supa_user(
        id_val=mock_user_id, email=mock_email, confirmed=True
    )
    mock_supa_session = create_mock_supa_session(user=mock_supa_user)

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.exchange_code_for_session = AsyncMock(
        return_value=mock_supa_session
    )
    mock_supabase_auth.get_user = AsyncMock(
        return_value=MagicMock(user=mock_supa_user)
    )  # Simulate user after exchange

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    # Mock CRUD operations via user_auth_routes.user_crud
    mock_get_profile_db = AsyncMock(return_value=None)
    monkeypatch.setattr(
        user_auth_routes.user_crud,
        "get_profile_by_user_id_from_db",
        mock_get_profile_db,
    )

    mock_newly_created_profile = MagicMock(
        spec=Profile
    )  # Simulate the ORM model instance
    mock_newly_created_profile.user_id = str(mock_user_id)
    mock_newly_created_profile.username = mock_supa_user.email.split("@")[0]
    mock_newly_created_profile.email = mock_supa_user.email
    mock_newly_created_profile.first_name = ""
    mock_newly_created_profile.last_name = ""
    mock_newly_created_profile.is_active = True
    mock_newly_created_profile.created_at = datetime.now(timezone.utc)
    mock_newly_created_profile.updated_at = datetime.now(timezone.utc)

    mock_create_profile_db = AsyncMock(return_value=mock_newly_created_profile)
    monkeypatch.setattr(
        user_auth_routes.user_crud, "create_profile_in_db", mock_create_profile_db
    )

    # Mock app_settings for cookie name
    mock_app_settings = create_default_mock_settings()
    mock_app_settings.OAUTH_STATE_COOKIE_NAME = "test_pa_oauth_state"
    mock_app_settings.ENVIRONMENT = "test"  # Define ENVIRONMENT for cookie secure flag
    original_get_app_settings = app.dependency_overrides.get(
        user_auth_routes.get_app_settings
    )
    app.dependency_overrides[user_auth_routes.get_app_settings] = (
        lambda: mock_app_settings
    )

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override

    try:
        response = await async_client.get(
            f"/auth/users/login/{provider.value}/callback?code={auth_code}&state={state}",
            cookies={
                mock_app_settings.OAUTH_STATE_COOKIE_NAME: state
            },  # Send the state cookie
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        response_data = response.json()
        assert response_data["access_token"] == mock_supa_session.access_token
        assert response_data["user"]["id"] == str(mock_user_id)

        mock_supabase_auth.exchange_code_for_session.assert_called_once_with(
            auth_code=auth_code
        )
        mock_get_profile_db.assert_called_once_with(
            db_session=db_session_for_crud, user_id=str(mock_user_id)
        )

        mock_create_profile_db.assert_called_once()
        args, kwargs = mock_create_profile_db.call_args
        assert isinstance(kwargs["profile_in"], user_auth_routes.ProfileCreate)
        assert kwargs["profile_in"].user_id == mock_user_id
        assert kwargs["profile_in"].email == mock_supa_user.email
        # Add more assertions for profile_in fields if necessary

        # Check cookie clearing
        found_cleared_cookie = False
        for header_name, header_value in response.headers.multi_items():
            if header_name.lower() == "set-cookie":
                if (
                    mock_app_settings.OAUTH_STATE_COOKIE_NAME in header_value
                    and "Max-Age=0" in header_value
                ):
                    found_cleared_cookie = True
                    break
        assert (
            found_cleared_cookie
        ), f"OAuth state cookie '{mock_app_settings.OAUTH_STATE_COOKIE_NAME}' not cleared."

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:  # pragma: no cover
                del app.dependency_overrides[real_get_supabase_client]
        if original_get_app_settings:
            app.dependency_overrides[user_auth_routes.get_app_settings] = (
                original_get_app_settings
            )
        else:
            if user_auth_routes.get_app_settings in app.dependency_overrides:
                del app.dependency_overrides[user_auth_routes.get_app_settings]


@pytest.mark.asyncio
async def test_oauth_callback_google_successful_existing_user(
    async_client: AsyncClient,
    monkeypatch,
    db_session_for_crud: AsyncSession,  # For profile check
):
    """
    Test successful OAuth callback for an existing user via Google.
    Ensures code is exchanged, session is returned, and profile creation is NOT called.
    """
    provider = OAuthProvider.GOOGLE
    auth_code = "valid_auth_code_for_existing_user"
    state = "random_state_string"
    mock_user_id = uuid4()
    mock_email = f"existing_oauth_user_{mock_user_id.hex[:6]}@example.com"

    mock_supa_user = create_mock_supa_user(
        id_val=mock_user_id, email=mock_email, confirmed=True
    )
    mock_supa_session = create_mock_supa_session(user=mock_supa_user)
    # Simulate an existing ORM Profile model instance
    mock_existing_profile_orm = MagicMock(spec=Profile)
    mock_existing_profile_orm.user_id = str(mock_user_id)
    mock_existing_profile_orm.username = f"user_{mock_user_id.hex[:6]}"
    mock_existing_profile_orm.email = mock_email
    mock_existing_profile_orm.is_active = True
    mock_existing_profile_orm.created_at = datetime.now(timezone.utc)
    mock_existing_profile_orm.updated_at = datetime.now(timezone.utc)

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.exchange_code_for_session = AsyncMock(
        return_value=mock_supa_session
    )
    # get_user is not directly called by the callback logic after exchange_code_for_session returns a session with a user object.
    # The user object is taken from supa_response.user

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    # Mock CRUD operations via user_auth_routes.user_crud
    mock_get_profile_db = AsyncMock(return_value=mock_existing_profile_orm)
    monkeypatch.setattr(
        user_auth_routes.user_crud,
        "get_profile_by_user_id_from_db",
        mock_get_profile_db,
    )

    mock_create_profile_db = AsyncMock()
    monkeypatch.setattr(
        user_auth_routes.user_crud, "create_profile_in_db", mock_create_profile_db
    )

    # Mock app_settings for cookie name
    mock_app_settings = create_default_mock_settings()
    mock_app_settings.OAUTH_STATE_COOKIE_NAME = "test_pa_oauth_state"
    mock_app_settings.ENVIRONMENT = "test"  # Define ENVIRONMENT for cookie secure flag
    original_get_app_settings = app.dependency_overrides.get(
        user_auth_routes.get_app_settings
    )
    app.dependency_overrides[user_auth_routes.get_app_settings] = (
        lambda: mock_app_settings
    )

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override

    try:
        response = await async_client.get(
            f"/auth/users/login/{provider.value}/callback?code={auth_code}&state={state}",
            cookies={
                mock_app_settings.OAUTH_STATE_COOKIE_NAME: state
            },  # Send the state cookie
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        response_data = response.json()
        assert response_data["access_token"] == mock_supa_session.access_token
        assert response_data["user"]["id"] == str(mock_user_id)

        mock_supabase_auth.exchange_code_for_session.assert_called_once_with(
            auth_code=auth_code
        )
        mock_get_profile_db.assert_called_once_with(
            db_session=db_session_for_crud, user_id=str(mock_user_id)
        )
        mock_create_profile_db.assert_not_called()

        # Check cookie clearing
        found_cleared_cookie = False
        for header_name, header_value in response.headers.multi_items():
            if header_name.lower() == "set-cookie":
                if (
                    mock_app_settings.OAUTH_STATE_COOKIE_NAME in header_value
                    and "Max-Age=0" in header_value
                ):
                    found_cleared_cookie = True
                    break
        assert (
            found_cleared_cookie
        ), f"OAuth state cookie '{mock_app_settings.OAUTH_STATE_COOKIE_NAME}' not cleared."

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:  # pragma: no cover
                del app.dependency_overrides[real_get_supabase_client]
        if original_get_app_settings:
            app.dependency_overrides[user_auth_routes.get_app_settings] = (
                original_get_app_settings
            )
        else:
            if user_auth_routes.get_app_settings in app.dependency_overrides:
                del app.dependency_overrides[user_auth_routes.get_app_settings]


@pytest.mark.asyncio
async def test_oauth_callback_google_provider_error(
    async_client: AsyncClient,
    monkeypatch,
    db_session_for_crud: AsyncSession,  # For profile creation
):
    """
    Test OAuth callback when the provider returns an error (e.g., user denied access).
    """
    provider = OAuthProvider.GOOGLE
    error_code = "access_denied"
    error_description = "User denied access to the application."
    state = "random_state_string"

    # No Supabase calls should be made if the provider itself returns an error to our callback URL
    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.exchange_code_for_session = AsyncMock()
    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override

    # Mock app_settings for cookie name
    mock_app_settings = create_default_mock_settings()
    mock_app_settings.OAUTH_STATE_COOKIE_NAME = "test_pa_oauth_state"
    mock_app_settings.ENVIRONMENT = "test"  # Define ENVIRONMENT for cookie secure flag
    original_get_app_settings = app.dependency_overrides.get(
        user_auth_routes.get_app_settings
    )
    app.dependency_overrides[user_auth_routes.get_app_settings] = (
        lambda: mock_app_settings
    )

    try:
        response = await async_client.get(
            f"/auth/users/login/{provider.value}/callback?error={error_code}&error_description={error_description}&state={state}",
            cookies={
                mock_app_settings.OAUTH_STATE_COOKIE_NAME: state
            },  # Send the state cookie
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
        response_data = response.json()
        assert error_code in response_data["detail"]
        assert error_description in response_data["detail"]
        mock_supabase_auth.exchange_code_for_session.assert_not_called()
    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:  # pragma: no cover
                del app.dependency_overrides[real_get_supabase_client]
        if original_get_app_settings:
            app.dependency_overrides[user_auth_routes.get_app_settings] = (
                original_get_app_settings
            )
        else:
            if user_auth_routes.get_app_settings in app.dependency_overrides:
                del app.dependency_overrides[user_auth_routes.get_app_settings]


@pytest.mark.asyncio
async def test_oauth_callback_google_invalid_code(
    async_client: AsyncClient, monkeypatch
):
    """
    Test OAuth callback with an invalid or expired authorization code.
    Supabase should fail to exchange the code for a session.
    """
    provider = OAuthProvider.GOOGLE
    invalid_auth_code = "invalid_or_expired_code"
    state = "random_state_string"

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.exchange_code_for_session = AsyncMock(
        side_effect=AuthApiError(
            message="Invalid grant: authorization code is invalid",
            status=400,
            code="invalid_grant",
        )
    )
    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override

    # Mock app_settings for cookie name
    mock_app_settings = create_default_mock_settings()
    mock_app_settings.OAUTH_STATE_COOKIE_NAME = "test_pa_oauth_state"
    mock_app_settings.ENVIRONMENT = "test"  # Define ENVIRONMENT for cookie secure flag
    original_get_app_settings = app.dependency_overrides.get(
        user_auth_routes.get_app_settings
    )
    app.dependency_overrides[user_auth_routes.get_app_settings] = (
        lambda: mock_app_settings
    )

    try:
        response = await async_client.get(
            f"/auth/users/login/{provider.value}/callback?code={invalid_auth_code}&state={state}",
            cookies={
                mock_app_settings.OAUTH_STATE_COOKIE_NAME: state
            },  # Send the state cookie
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
        response_data = response.json()
        assert "Invalid grant: authorization code is invalid" in response_data["detail"]
    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:  # pragma: no cover
                del app.dependency_overrides[real_get_supabase_client]


@pytest.mark.asyncio
async def test_oauth_callback_google_invalid_state(
    async_client: AsyncClient, monkeypatch  # Keep for potential future mocks
):
    """
    Test OAuth callback with an invalid state parameter.
    This assumes the endpoint validates 'state' against a stored value (e.g., in session/cookie).
    """
    provider = OAuthProvider.GOOGLE
    auth_code = "some_auth_code"
    invalid_state = "tampered_or_unexpected_state"
    # For this test, the endpoint's state validation logic needs to be in place.
    # We expect it to raise an HTTPException(400, "Invalid OAuth state") if validation fails.

    # Supabase calls should not be made if state validation fails early.
    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.exchange_code_for_session = AsyncMock()
    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override

    # How state is stored and retrieved (e.g., from session cookie) will determine
    # if more specific mocking is needed here for the endpoint's get_stored_oauth_state logic.
    # For now, we assume the endpoint's logic will directly compare and raise.

    try:
        response = await async_client.get(
            f"/auth/users/login/{provider.value}/callback?code={auth_code}&state={invalid_state}"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
        response_data = response.json()
        assert (
            "invalid oauth state" in response_data.get("detail", "").lower()
        )  # Check lowercase substring
        mock_supabase_auth.exchange_code_for_session.assert_not_called()
    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:  # pragma: no cover
                del app.dependency_overrides[real_get_supabase_client]
