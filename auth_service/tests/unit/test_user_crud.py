"""
Unit tests for user CRUD operations.
Tests database interactions using the real test database.
"""
import uuid
import pytest
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from auth_service.crud import user_crud
from auth_service.models.profile import Profile
from auth_service.schemas.user_schemas import ProfileCreate, ProfileUpdate

# Set up logger
logger = logging.getLogger(__name__)


class TestUserCrud:
    @pytest.mark.asyncio
    async def test_create_profile_in_db(self, db_session, mock_supabase_client):
        """Test creating a profile in the database using the real test database."""
        # First create a test user in auth.users for foreign key constraint
        test_user_id = mock_supabase_client.test_user_id
        test_id = str(uuid.uuid4())[:8]
        
        # Import required modules for seeding test user
        import json
        from sqlalchemy import text
        
        # Create unique user data for this test
        email = f"test_create_{test_id}@example.com"
        username = f"test_create_user_{test_id}"
        
        # Create user metadata
        user_meta_data = json.dumps({"username": username})
        app_meta_data = json.dumps({})
        
        # Seed the user in auth.users table
        try:
            # Insert the user record directly into auth.users table
            await db_session.execute(
                text(f"""
                INSERT INTO auth.users (
                    id, 
                    raw_user_meta_data,
                    raw_app_meta_data,
                    is_anonymous,
                    created_at, 
                    updated_at,
                    role
                )
                VALUES (
                    '{test_user_id}'::uuid,
                    '{user_meta_data}'::jsonb,
                    '{app_meta_data}'::jsonb,
                    false,
                    NOW(),
                    NOW(),
                    'authenticated'
                )
                ON CONFLICT (id) DO NOTHING
                """)
            )
            await db_session.commit()
            logger.info(f"Created test user in auth.users: {test_user_id} for profile creation test")
        except Exception as e:
            logger.error(f"Error creating test user: {e}")
            await db_session.rollback()
            raise
        
        # Create profile data
        profile_data = ProfileCreate(
            user_id=test_user_id,
            email=email,
            username=username,
            first_name="Test",
            last_name="Create"
        )
        
        # Act - Create profile using the real database
        result = await user_crud.create_profile_in_db(
            db_session=db_session,
            profile_in=profile_data
        )
        
        # Assert the profile was created correctly
        assert result is not None
        assert result.email == profile_data.email
        assert result.username == profile_data.username
        
        # Verify the profile exists in the database
        query_result = await db_session.execute(
            select(Profile).where(Profile.email == email)
        )
        db_profile = query_result.scalars().first()
        
        assert db_profile is not None
        assert db_profile.email == email
        assert db_profile.username == username
        assert db_profile.first_name == "Test"
        assert db_profile.last_name == "Create"
    
    @pytest.mark.asyncio
    async def test_get_profile_by_user_id(self, db_session):
        """Test retrieving a profile by user ID using the real test database."""
        # First create a test user and profile in the database
        test_id = str(uuid.uuid4())[:8]
        
        # Create unique user data for this test
        email = f"test_get_id_{test_id}@example.com"
        username = f"test_get_id_user_{test_id}"
        
        # Import the seed_test_user helper to create a user in auth.users table
        from tests.fixtures.helpers import seed_test_user
        
        # Create a test user in auth.users table first to satisfy foreign key constraint
        test_user_id = await seed_test_user(
            db_session=db_session,
            email=email,
            username=username
        )
        
        # Create a profile in the database that we will later retrieve
        profile_data = ProfileCreate(
            user_id=test_user_id,
            email=email,
            username=username,
            first_name="Test",
            last_name="GetById"
        )
        
        # Create the profile
        created_profile = await user_crud.create_profile_in_db(
            db_session=db_session,
            profile_in=profile_data
        )
        
        # Ensure the profile was created successfully
        assert created_profile is not None
        
        # Act - Retrieve the profile by user_id
        result = await user_crud.get_profile_by_user_id(
            db_session=db_session,
            user_id=test_user_id
        )
        
        # Assert the profile was retrieved correctly
        assert result is not None
        assert result.email == email
        assert result.username == username
        assert str(result.user_id) == test_user_id
    
    @pytest.mark.asyncio
    async def test_get_profile_by_email(self, db_session):
        """Test retrieving a profile by email using the real test database."""
        # First create a test user and profile in the database
        test_id = str(uuid.uuid4())[:8]
        
        # Create unique user data for this test
        email = f"test_get_email_{test_id}@example.com"
        username = f"test_get_email_user_{test_id}"
        
        # Import the seed_test_user helper to create a user in auth.users table
        from tests.fixtures.helpers import seed_test_user
        
        # Create a test user in auth.users table first to satisfy foreign key constraint
        test_user_id = await seed_test_user(
            db_session=db_session,
            email=email,
            username=username
        )
        
        # Create a profile in the database that we will later retrieve
        profile_data = ProfileCreate(
            user_id=test_user_id,
            email=email,
            username=username,
            first_name="Test",
            last_name="GetByEmail"
        )
        
        # Create the profile
        created_profile = await user_crud.create_profile_in_db(
            db_session=db_session,
            profile_in=profile_data
        )
        
        # Ensure the profile was created successfully
        assert created_profile is not None
        
        # Act - Retrieve the profile by email
        result = await user_crud.get_profile_by_email(
            db_session=db_session,
            email=email
        )
        
        # Assert the profile was retrieved correctly
        assert result is not None
        assert result.email == email
        assert result.username == username
        assert str(result.user_id) == test_user_id
    
    @pytest.mark.asyncio
    async def test_get_profile_by_email_not_found(self, db_session):
        """Test trying to get a profile by email that doesn't exist using the real test database."""
        # Generate a unique email that shouldn't exist in the database
        non_existent_email = f"doesnotexist_{uuid.uuid4()}@example.com"
        
        # Act - Try to retrieve a profile with the non-existent email
        result = await user_crud.get_profile_by_email(
            db_session=db_session,
            email=non_existent_email
        )
        
        # Assert no profile was found
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_profile_by_id_not_found(self, db_session):
        """Test trying to get a profile by ID that doesn't exist using the real test database."""
        # Generate a random UUID that shouldn't exist in the database
        non_existent_id = uuid.uuid4()
        
        # Act - Try to retrieve a profile with the non-existent ID
        result = await user_crud.get_profile_by_user_id(
            db_session=db_session,
            user_id=non_existent_id
        )
        
        # Assert no profile was found
        assert result is None
    
    @pytest.mark.asyncio
    async def test_update_profile(self, db_session):
        """Test updating a profile using the real test database."""
        # First create a test user and profile in the database
        test_id = str(uuid.uuid4())[:8]
        
        # Create unique user data for this test
        email = f"test_update_{test_id}@example.com"
        username = f"test_update_user_{test_id}"
        
        # Import the seed_test_user helper to create a user in auth.users table
        from tests.fixtures.helpers import seed_test_user
        
        # Create a test user in auth.users table first to satisfy foreign key constraint
        test_user_id = await seed_test_user(
            db_session=db_session,
            email=email,
            username=username
        )
        
        # Create a profile in the database that we will later update
        profile_data = ProfileCreate(
            user_id=test_user_id,
            email=email,
            username=username,
            first_name="Original",
            last_name="Name"
        )
        
        # Create the profile
        created_profile = await user_crud.create_profile_in_db(
            db_session=db_session,
            profile_in=profile_data
        )
        
        # Ensure the profile was created successfully
        assert created_profile is not None
        
        # Set up update data
        update_data = ProfileUpdate(
            first_name="Updated",
            last_name="Profile",
            email=f"updated_{test_id}@example.com"
        )
        
        # First get the profile object by user_id
        profile = await user_crud.get_profile_by_user_id(
            db_session=db_session,
            user_id=test_user_id
        )
        
        # Act - Update the profile
        result = await user_crud.update_profile(
            db_session=db_session,
            profile=profile,
            update_data=update_data.model_dump(exclude_unset=True)
        )
        
        # Assert the profile was updated correctly
        assert result is not None
        assert result.email == update_data.email
        assert result.first_name == update_data.first_name
        assert result.last_name == update_data.last_name
        # Username and user ID should remain the same
        assert result.username == username
        assert str(result.user_id) == test_user_id
        
        # Verify the profile was updated in the database
        query_result = await db_session.execute(
            select(Profile).where(Profile.user_id == test_user_id)
        )
        db_profile = query_result.scalars().first()
        
        assert db_profile is not None
        assert db_profile.email == update_data.email
        assert db_profile.first_name == update_data.first_name
        assert db_profile.last_name == update_data.last_name
    
    @pytest.mark.asyncio
    async def test_update_nonexistent_profile(self, db_session):
        """Test trying to update a profile that doesn't exist using the real test database."""
        # Generate a random UUID that shouldn't exist in the database
        non_existent_id = str(uuid.uuid4())
        
        # Set up update data
        update_data = ProfileUpdate(
            first_name="Updated",
            last_name="Profile",
            email="updated_nonexistent@example.com"
        )
        
        # First try to get the profile object by user_id (should be None)
        profile = await user_crud.get_profile_by_user_id(
            db_session=db_session,
            user_id=non_existent_id
        )
        
        # Act - Since profile is None, update should not be attempted
        result = None
        if profile:
            result = await user_crud.update_profile(
                db_session=db_session,
                profile=profile,
                update_data=update_data.model_dump(exclude_unset=True)
            )
        
        # Assert no profile was updated
        assert result is None
    
    @pytest.mark.asyncio
    async def test_deactivate_profile(self, db_session):
        """Test deactivating a profile using the real test database."""
        # First create a test user and profile in the database
        test_id = str(uuid.uuid4())[:8]
        
        # Create unique user data for this test
        email = f"test_deactivate_{test_id}@example.com"
        username = f"test_deactivate_user_{test_id}"
        
        # Import the seed_test_user helper to create a user in auth.users table
        from tests.fixtures.helpers import seed_test_user
        
        # Create a test user in auth.users table first to satisfy foreign key constraint
        test_user_id = await seed_test_user(
            db_session=db_session,
            email=email,
            username=username
        )
        
        # Create a profile in the database that we will later deactivate
        profile_data = ProfileCreate(
            user_id=test_user_id,
            email=email,
            username=username,
            first_name="To",
            last_name="Deactivate"
        )
        
        # Create the profile
        created_profile = await user_crud.create_profile_in_db(
            db_session=db_session,
            profile_in=profile_data
        )
        
        # Ensure the profile was created successfully and is active
        assert created_profile is not None
        assert created_profile.is_active == True
        
        # Act - Deactivate the profile
        result = await user_crud.deactivate_profile(
            db_session=db_session,
            user_id=test_user_id
        )
        
        # Assert the profile was deactivated correctly
        assert result is not None
        assert result.is_active == False
        # Other properties should remain unchanged
        assert str(result.user_id) == test_user_id
        assert result.email == email
        assert result.username == username
        
        # Verify the profile was deactivated in the database
        query_result = await db_session.execute(
            select(Profile).where(Profile.user_id == test_user_id)
        )
        db_profile = query_result.scalars().first()
        
        assert db_profile is not None
        assert db_profile.is_active == False
        assert db_profile.email == email
        
    @pytest.mark.asyncio
    async def test_deactivate_nonexistent_profile(self, db_session):
        """Test trying to deactivate a profile that doesn't exist using the real test database."""
        # Generate a random UUID that shouldn't exist in the database
        non_existent_id = uuid.uuid4()
        
        # Act - Try to deactivate a non-existent profile
        result = await user_crud.deactivate_profile(
            db_session=db_session,
            user_id=non_existent_id
        )
        
        # Assert no profile was deactivated
        assert result is None
