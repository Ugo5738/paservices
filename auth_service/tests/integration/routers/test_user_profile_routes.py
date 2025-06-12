# Standard library imports
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

# Third-party imports
import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import text  # For raw SQL execution
from sqlalchemy.ext.asyncio import AsyncSession
from tests.test_helpers import create_mock_supa_user  # Test utility

# Application-specific imports
from auth_service.main import app
from auth_service.models.profile import Profile  # SQLAlchemy model
from auth_service.routers.user_auth_routes import (
    get_current_supabase_user,  # Dependency to mock
)
from auth_service.schemas.user_schemas import (  # Pydantic models
    ProfileResponse,
    UserProfileUpdateRequest,
)


@pytest.mark.asyncio
async def test_get_user_profile_me_successful(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession,
    monkeypatch,
):
    """Test successful retrieval of the current user's profile."""
    mock_user_id = uuid4()
    mock_email = f"user_{mock_user_id.hex[:8]}@example.com"
    mock_username = f"testuser_{mock_user_id.hex[:8]}"

    # 0. Create a dummy user in auth.users to satisfy FK constraint
    # This simulates a user already existing in Supabase auth
    await db_session_for_crud.execute(
        text(
            "INSERT INTO auth.users (id, email, encrypted_password, role, aud) "
            "VALUES (:id, :email, :password, 'authenticated', 'authenticated')"
        ),
        {
            "id": mock_user_id,
            "email": mock_email,
            "password": "dummy_password",  # Content doesn't matter for this test
        },
    )
    # No commit needed here if using db_session_for_crud which might auto-commit or part of a larger test transaction
    # However, it's safer to commit if this is the only operation that needs to be visible before the profile insert.
    # await db_session_for_crud.commit() # Let's try without explicit commit first, relying on subsequent commit.

    # 1. Create a mock Supabase user (as would be returned by the dependency)
    mock_supa_user = create_mock_supa_user(id_val=mock_user_id, email=mock_email)

    # 2. Create a profile in the database for this user
    profile_data = {
        "user_id": mock_user_id,
        "email": mock_email,
        "username": mock_username,
        "first_name": "Test",
        "last_name": "User",
        "is_active": True,
        # created_at and updated_at will be set by the DB
    }
    new_profile = Profile(**profile_data)
    db_session_for_crud.add(new_profile)
    await db_session_for_crud.commit()  # This commit should handle both the user and profile if not committed before
    await db_session_for_crud.refresh(new_profile)

    # 3. Mock the get_current_supabase_user dependency
    async def mock_get_current_user_override():
        return mock_supa_user

    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = mock_get_current_user_override

    try:
        # 4. Make the request to the endpoint
        response = await async_client.get(
            "/auth/users/me",
            headers={
                "Authorization": "Bearer faketoken"
            },  # Token is needed for dependency
        )

        # 5. Assertions
        assert response.status_code == status.HTTP_200_OK, response.text
        response_data = response.json()

        # Validate against Pydantic model (implicitly done by parsing)
        profile_response = ProfileResponse(**response_data)

        assert profile_response.user_id == mock_user_id
        assert profile_response.email == mock_email
        assert profile_response.username == mock_username
        assert profile_response.first_name == "Test"
        assert profile_response.last_name == "User"
        assert profile_response.is_active is True
        assert isinstance(profile_response.created_at, datetime)
        assert isinstance(profile_response.updated_at, datetime)
        # Check if datetimes are timezone-aware (assuming they should be)
        assert profile_response.created_at.tzinfo is not None
        assert profile_response.updated_at.tzinfo is not None

    finally:
        # Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_get_user_profile_me_profile_not_found(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession,  # db_session needed to ensure no profile exists
    monkeypatch,
):
    """Test profile retrieval when authenticated user has no local profile (edge case)."""
    mock_user_id = uuid4()
    mock_email = f"no_profile_user_{mock_user_id.hex[:8]}@example.com"

    # 1. Create a mock Supabase user
    mock_supa_user = create_mock_supa_user(id_val=mock_user_id, email=mock_email)

    # 2. Ensure NO profile exists in the database for this user_id.
    # (No action needed as db_session_for_crud is clean for this test unless a profile was created)

    # 3. Mock the get_current_supabase_user dependency
    async def mock_get_current_user_override():
        return mock_supa_user

    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = mock_get_current_user_override

    try:
        # 4. Make the request
        response = await async_client.get(
            "/auth/users/me", headers={"Authorization": "Bearer faketoken"}
        )

        # 5. Assertions
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
        response_data = response.json()
        assert "Profile not found for user" in response_data["detail"]
        assert str(mock_user_id) in response_data["detail"]

    finally:
        # Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_get_user_profile_me_unauthenticated(
    async_client: AsyncClient,
):
    """Test profile retrieval when user is not authenticated."""
    # 1. Make the request without an Authorization header
    response = await async_client.get("/auth/users/me")

    # 2. Assertions
    # FastAPI's OAuth2PasswordBearer returns 401 if token is missing/invalid
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text
    response_data = response.json()
    assert response_data["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_update_user_profile_me_successful_full_update(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession,
    monkeypatch,
):
    """Test successful full update of the current user's profile."""
    mock_user_id = uuid4()
    initial_email = f"user_{mock_user_id.hex[:8]}@example.com"
    initial_username = f"initial_user_{mock_user_id.hex[:8]}"
    initial_first_name = "InitialFirst"
    initial_last_name = "InitialLast"

    # 1. Create a dummy user in auth.users
    await db_session_for_crud.execute(
        text(
            "INSERT INTO auth.users (id, email, encrypted_password, role, aud) "
            "VALUES (:id, :email, :password, 'authenticated', 'authenticated')"
        ),
        {
            "id": mock_user_id,
            "email": initial_email,
            "password": "dummy_password",
        },
    )

    # 2. Create an initial profile in the database
    initial_profile_data = {
        "user_id": mock_user_id,
        "email": initial_email,  # Email is part of the profile and should remain unchanged
        "username": initial_username,
        "first_name": initial_first_name,
        "last_name": initial_last_name,
        "is_active": True,
    }
    profile_orm = Profile(**initial_profile_data)
    db_session_for_crud.add(profile_orm)
    await db_session_for_crud.commit()
    await db_session_for_crud.refresh(profile_orm)

    # 3. Mock the get_current_supabase_user dependency
    mock_supa_user = create_mock_supa_user(id_val=mock_user_id, email=initial_email)

    async def mock_get_current_user_override():
        return mock_supa_user

    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = mock_get_current_user_override

    # 4. Prepare update data
    update_payload = UserProfileUpdateRequest(
        username="updated_username",
        first_name="UpdatedFirst",
        last_name="UpdatedLast",
    )

    try:
        # 5. Make the PUT request
        response = await async_client.put(
            "/auth/users/me",
            headers={"Authorization": "Bearer faketoken"},
            json=update_payload.model_dump(
                exclude_unset=True
            ),  # Important: send only fields to update
        )

        # 6. Assertions on the response
        assert response.status_code == status.HTTP_200_OK, response.text
        response_data = response.json()
        updated_profile_response = ProfileResponse(**response_data)

        assert updated_profile_response.user_id == mock_user_id
        assert (
            updated_profile_response.email == initial_email
        )  # Email should not change
        assert updated_profile_response.username == update_payload.username
        assert updated_profile_response.first_name == update_payload.first_name
        assert updated_profile_response.last_name == update_payload.last_name
        assert updated_profile_response.is_active is True
        assert (
            updated_profile_response.updated_at >= profile_orm.updated_at
        )  # Check timestamp updated

        # 7. Assertions on the database
        await db_session_for_crud.refresh(profile_orm)  # Refresh ORM model from DB
        assert profile_orm.username == update_payload.username
        assert profile_orm.first_name == update_payload.first_name
        assert profile_orm.last_name == update_payload.last_name
        assert profile_orm.email == initial_email  # Verify email unchanged in DB
        assert (
            profile_orm.updated_at == updated_profile_response.updated_at
        )  # Timestamps should match

    finally:
        # Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_update_user_profile_me_successful_partial_update_username(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession,
    monkeypatch,
):
    """Test successful partial update of the current user's profile (username only)."""
    mock_user_id = uuid4()
    initial_email = f"user_partial_{mock_user_id.hex[:8]}@example.com"
    initial_username = f"initial_partial_user_{mock_user_id.hex[:8]}"
    initial_first_name = "PartialFirst"
    initial_last_name = "PartialLast"

    # 1. Create a dummy user in auth.users
    await db_session_for_crud.execute(
        text(
            "INSERT INTO auth.users (id, email, encrypted_password, role, aud) "
            "VALUES (:id, :email, :password, 'authenticated', 'authenticated')"
        ),
        {
            "id": mock_user_id,
            "email": initial_email,
            "password": "dummy_password",
        },
    )

    # 2. Create an initial profile
    initial_profile_data = {
        "user_id": mock_user_id,
        "email": initial_email,
        "username": initial_username,
        "first_name": initial_first_name,
        "last_name": initial_last_name,
        "is_active": True,
    }
    profile_orm = Profile(**initial_profile_data)
    db_session_for_crud.add(profile_orm)
    await db_session_for_crud.commit()
    await db_session_for_crud.refresh(profile_orm)
    original_updated_at = profile_orm.updated_at

    # 3. Mock authentication
    mock_supa_user = create_mock_supa_user(id_val=mock_user_id, email=initial_email)

    async def mock_get_current_user_override():
        return mock_supa_user

    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = mock_get_current_user_override

    # 4. Prepare update data (only username)
    updated_username = "updated_partial_username"
    update_payload = UserProfileUpdateRequest(username=updated_username)

    try:
        # 5. Make the PUT request
        response = await async_client.put(
            "/auth/users/me",
            headers={"Authorization": "Bearer faketoken"},
            json=update_payload.model_dump(exclude_unset=True),
        )

        # 6. Assertions on the response
        assert response.status_code == status.HTTP_200_OK, response.text
        response_data = response.json()
        updated_profile_response = ProfileResponse(**response_data)

        assert updated_profile_response.username == updated_username
        assert updated_profile_response.first_name == initial_first_name  # Unchanged
        assert updated_profile_response.last_name == initial_last_name  # Unchanged
        assert updated_profile_response.email == initial_email  # Unchanged
        assert updated_profile_response.user_id == mock_user_id
        assert updated_profile_response.is_active is True
        assert updated_profile_response.updated_at >= original_updated_at

        # 7. Assertions on the database
        await db_session_for_crud.refresh(profile_orm)
        assert profile_orm.username == updated_username
        assert profile_orm.first_name == initial_first_name
        assert profile_orm.last_name == initial_last_name
        assert profile_orm.email == initial_email
        assert profile_orm.updated_at == updated_profile_response.updated_at

    finally:
        # Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_update_user_profile_me_conflict_username_exists(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession,
    monkeypatch,
):
    """Test updating profile to a username that already exists for another user."""
    # 1. Create User A (the one making the request)
    user_a_id = uuid4()
    user_a_email = f"user_a_{user_a_id.hex[:8]}@example.com"
    user_a_initial_username = f"user_a_initial_{user_a_id.hex[:8]}"

    await db_session_for_crud.execute(
        text(
            "INSERT INTO auth.users (id, email, encrypted_password, role, aud) VALUES (:id, :email, 'password', 'authenticated', 'authenticated')"
        ),
        {"id": user_a_id, "email": user_a_email},
    )
    profile_a_orm = Profile(
        user_id=user_a_id,
        email=user_a_email,
        username=user_a_initial_username,
        first_name="UserAFirst",
        last_name="UserALast",
        is_active=True,
    )
    db_session_for_crud.add(profile_a_orm)

    # 2. Create User B (the one whose username User A wants to take)
    user_b_id = uuid4()
    user_b_email = f"user_b_{user_b_id.hex[:8]}@example.com"
    existing_username_for_b = "already_taken_username"

    await db_session_for_crud.execute(
        text(
            "INSERT INTO auth.users (id, email, encrypted_password, role, aud) VALUES (:id, :email, 'password', 'authenticated', 'authenticated')"
        ),
        {"id": user_b_id, "email": user_b_email},
    )
    profile_b_orm = Profile(
        user_id=user_b_id,
        email=user_b_email,
        username=existing_username_for_b,
        first_name="UserBFirst",
        last_name="UserBLast",
        is_active=True,
    )
    db_session_for_crud.add(profile_b_orm)

    await db_session_for_crud.commit()
    await db_session_for_crud.refresh(profile_a_orm)
    await db_session_for_crud.refresh(profile_b_orm)
    user_a_original_updated_at = profile_a_orm.updated_at

    # 3. Mock authentication for User A
    mock_supa_user_a = create_mock_supa_user(id_val=user_a_id, email=user_a_email)

    async def mock_get_current_user_override():
        return mock_supa_user_a

    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = mock_get_current_user_override

    # 4. Prepare update data for User A to take User B's username
    update_payload = UserProfileUpdateRequest(username=existing_username_for_b)

    try:
        # 5. Make the PUT request
        response = await async_client.put(
            "/auth/users/me",
            headers={"Authorization": "Bearer faketoken"},
            json=update_payload.model_dump(exclude_unset=True),
        )

        # 6. Assertions on the response
        assert response.status_code == status.HTTP_409_CONFLICT, response.text
        response_data = response.json()
        assert "detail" in response_data
        assert (
            f"Username '{existing_username_for_b}' already exists."
            in response_data["detail"]
        )

        # 7. Assertions on User A's database record (should be unchanged)
        await db_session_for_crud.refresh(profile_a_orm)
        assert profile_a_orm.username == user_a_initial_username  # Username unchanged
        assert (
            profile_a_orm.updated_at == user_a_original_updated_at
        )  # Timestamp unchanged

    finally:
        # Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]
