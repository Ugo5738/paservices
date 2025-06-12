from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.models import Profile
from auth_service.models.profile import Profile

# Functions to test are currently in user_auth_routes, adjust if refactored
from auth_service.routers.user_auth_routes import (
    create_profile_in_db,
    get_profile_by_user_id_from_db,
)
from auth_service.schemas.user_schemas import ProfileCreate


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_create_profile_successfully(db_session_for_crud: AsyncSession):
    user_id = uuid4()
    username = f"testuser_{user_id.hex[:8]}"

    # Insert dummy user to satisfy FK constraint
    dummy_email_for_auth_user = f"dummy_{user_id.hex[:8]}@example.com"

    # Use a fresh transaction for the user insert
    await db_session_for_crud.execute(
        text(
            "INSERT INTO auth.users (id, email, encrypted_password, role) VALUES (:id, :email, 'dummy_password', 'authenticated') ON CONFLICT (id) DO NOTHING;"
        ),
        {"id": user_id, "email": dummy_email_for_auth_user},
    )
    await db_session_for_crud.commit()

    # Create a new session for the profile creation to avoid transaction conflicts
    profile_data_to_create = ProfileCreate(
        user_id=user_id,
        email=dummy_email_for_auth_user,  # Add email field
        username=username,
        first_name="Test",
        last_name="User",
    )

    # Create the profile in a separate transaction
    created_profile = await create_profile_in_db(
        db_session=db_session_for_crud,
        profile_data=profile_data_to_create,
        user_id=user_id,
    )

    assert created_profile is not None
    assert created_profile.user_id == user_id
    assert created_profile.username == profile_data_to_create.username
    assert created_profile.first_name == profile_data_to_create.first_name
    assert created_profile.last_name == profile_data_to_create.last_name
    assert created_profile.is_active is True

    # Verify it's in the DB by fetching it
    fetched_profile = await get_profile_by_user_id_from_db(db_session_for_crud, user_id)
    assert fetched_profile is not None
    assert fetched_profile.user_id == user_id
    assert fetched_profile.username == profile_data_to_create.username


@pytest.mark.asyncio
async def test_get_profile_by_user_id_found(db_session_for_crud: AsyncSession):
    user_id = uuid4()
    username = f"gettest_{user_id.hex[:8]}"

    # Insert dummy user to satisfy FK constraint
    dummy_email_for_auth_user = f"dummy_{user_id.hex[:8]}@example.com"
    await db_session_for_crud.execute(
        text(
            "INSERT INTO auth.users (id, email, encrypted_password, role) VALUES (:id, :email, 'dummy_password', 'authenticated') ON CONFLICT (id) DO NOTHING;"
        ),
        {"id": user_id, "email": dummy_email_for_auth_user},
    )
    await db_session_for_crud.commit()

    profile_data_to_create = ProfileCreate(
        user_id=user_id,
        email=dummy_email_for_auth_user,  # Add email field
        username=username,
    )

    # First, create a profile to fetch
    created_profile = await create_profile_in_db(
        db_session_for_crud, profile_data_to_create, user_id
    )

    fetched_profile = await get_profile_by_user_id_from_db(db_session_for_crud, user_id)

    assert fetched_profile is not None
    assert fetched_profile.user_id == user_id
    assert fetched_profile.username == profile_data_to_create.username

    # Cleanup - delete the created profile
    await db_session_for_crud.delete(created_profile)
    await db_session_for_crud.commit()


@pytest.mark.asyncio
async def test_get_profile_by_user_id_not_found(db_session_for_crud: AsyncSession):
    non_existent_user_id = uuid4()
    fetched_profile = await get_profile_by_user_id_from_db(
        db_session_for_crud, non_existent_user_id
    )
    assert fetched_profile is None
