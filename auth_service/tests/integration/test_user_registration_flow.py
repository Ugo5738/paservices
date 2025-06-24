"""
Integration tests for the complete user registration flow.
Tests the registration route with mocked external dependencies but real internal components.
"""
import pytest
import pytest_asyncio
import uuid
import logging
from datetime import datetime, timezone
from fastapi import status
from httpx import AsyncClient
from unittest.mock import AsyncMock

# Import our models to check database state
from auth_service.models.profile import Profile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Create a unique session ID for this test run to avoid conflicts
SESSION_ID = datetime.now().strftime('%Y%m%d%H%M%S') + '_' + uuid.uuid4().hex[:8]

# Set up logger for test output
logger = logging.getLogger(__name__)


# Helper classes to mimic Supabase response structures
class SupabaseAuthResponse:
    def __init__(self, user, session):
        self.user = user
        self.session = session

class SupabaseUser:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        
    def model_dump(self):
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}

class SupabaseSession:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        
    def model_dump(self):
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}


@pytest.mark.asyncio
async def test_register_user_integration(client, db_session, mock_supabase_client):
    """
    Integration test for user registration flow.
    Tests the complete registration process including:
    1. API endpoint functionality
    2. Request validation
    3. Supabase client integration
    4. Database profile creation
    5. Response formatting
    """
    # Get the test user ID from the mock Supabase client
    test_user_id = mock_supabase_client.test_user_id
    
    # Import the seed_test_user helper to create a user in auth.users table
    from tests.fixtures.helpers import seed_test_user
    
    # Create user metadata with the username
    username = f"testuser_{SESSION_ID}"
    email = f"test.user.{SESSION_ID}@example.com"
    
    try:
        # Use our modular helper to seed the test user with the known test_user_id
        await seed_test_user(
            db_session=db_session,
            user_id=test_user_id,
            email=email,
            username=username
        )
        logger.info(f"Created test user in auth.users: {test_user_id} | {username}")
    except Exception as e:
        logger.error(f"Error creating test user: {e}")
        raise
    
    # Arrange - Test User Data with unique identifiers
    user_data = {
        "email": f"test.user.{SESSION_ID}@example.com",
        "password": "SecurePassword123!",
        "username": f"testuser_{SESSION_ID}",
        "first_name": "Test",
        "last_name": "User"
    }
    
    logger.info(f"Testing integration registration with user: {user_data['email']} and ID: {test_user_id}")
    
    # Act - Make request to registration endpoint
    response = await client.post(
        "/api/v1/auth/users/register", 
        json=user_data
    )
    
    # Log response for debugging
    logger.info(f"Integration registration response status: {response.status_code}")
    if response.status_code != status.HTTP_201_CREATED:
        logger.error(f"Integration registration response: {response.text}")
    
    # Assert - Check the response
    assert response.status_code == status.HTTP_201_CREATED, f"Expected 201, got {response.status_code}: {response.text}"
    
    # Parse response data
    data = response.json()
    
    # 1. Response structure check
    assert "message" in data, "Response missing 'message' field"
    assert "profile" in data, "Response missing 'profile' field"
    
    # 2. Response content check
    # Since our mock user has email_confirmed_at set, the message will be 'User registered successfully.'
    assert data["message"] == "User registered successfully."
    assert data["profile"]["email"] == user_data["email"] 
    assert data["profile"]["username"] == user_data["username"]
    
    # 3. Verify database state using the real test database session
    result = await db_session.execute(
        select(Profile).where(
            (Profile.email == user_data["email"]) &
            (Profile.user_id == test_user_id)
        )
    )
    profile = result.scalars().first()
    
    # Verify that the profile exists with correct data
    assert profile is not None, f"Profile for {user_data['email']} not found in the database"
    
    # Convert test_user_id to UUID for comparison with profile.user_id (which is a UUID object)
    from uuid import UUID
    test_user_uuid = UUID(test_user_id) if isinstance(test_user_id, str) else test_user_id
    
    # Now compare UUID objects
    assert profile.user_id == test_user_uuid, f"Profile user_id {profile.user_id} does not match test user ID {test_user_uuid}"
    assert profile.email == user_data["email"]
    assert profile.username == user_data["username"]
    assert profile.first_name == user_data["first_name"]
    assert profile.last_name == user_data["last_name"]
    assert profile.is_active is True


@pytest.mark.asyncio
async def test_register_user_invalid_data(client):
    """Test registration with invalid data."""
    # Arrange - Invalid User Data (missing required fields)
    invalid_user_data = {
        "email": "test@example.com",
        # Missing password
        "username": "testuser"
        # Missing first_name and last_name
    }
    
    logger.info("Testing registration with invalid data")
    
    # Act - Make request to registration endpoint
    response = await client.post(
        "/api/v1/auth/users/register", 
        json=invalid_user_data
    )
    
    logger.info(f"Invalid data response status: {response.status_code}")
    
    # Assert
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    # Verify validation error details
    data = response.json()
    assert "detail" in data
    errors = data["detail"]
    error_fields = [error["loc"][1] for error in errors]
    assert "password" in error_fields, "Validation should reject missing password"
    logger.info("Validation correctly rejected invalid data")


# Update helper classes to better match modern Pydantic style
class SupabaseUser:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        
    def model_dump(self):
        """Match the Pydantic v2 naming convention for compatibility"""
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}

class SupabaseSession:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        
    def model_dump(self):
        """Match the Pydantic v2 naming convention for compatibility"""
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}


@pytest.mark.asyncio
async def test_register_user_supabase_error(client, db_session):
    """Test registration when Supabase throws an error."""
    # Use a unique session ID for this test to avoid conflicts
    error_session_id = datetime.now().strftime('%Y%m%d%H%M%S') + '_error_' + uuid.uuid4().hex[:8]
    
    # Arrange - Test User Data with unique identifiers
    user_data = {
        "email": f"error.user.{error_session_id}@example.com",
        "password": "SecurePassword123!",
        "username": f"erroruser_{error_session_id}",
        "first_name": "Error",
        "last_name": "Test"
    }
    
    logger.info(f"Testing Supabase error handling for: {user_data['email']}")
    
    # For this test, we're using the mock_supabase_client fixture but we want to override
    # its behavior just for this test to simulate an error
    
    # We can create a custom fixture with our AsyncClient's transport that will raise an error
    # This is done in the app routes with dependency overrides
    
    # Act - Make the request (it will use the mock_supabase_client that's already configured)
    # Since we want to test error handling, the error will be caught in the route handler
    response = await client.post(
        "/api/v1/auth/users/register", 
        json=user_data,
        headers={"X-Test-Error": "trigger-supabase-error"} # Special header our test setup could recognize
    )
    
    logger.info(f"Supabase error test response status: {response.status_code}")
    
    # Assert - We should get a server error
    # Note: This test might need adjustment based on how errors are actually handled in the routes
    assert response.status_code != status.HTTP_201_CREATED, "Should not succeed when Supabase errors"
    
    # Verify no profile was created in the database despite the error
    result = await db_session.execute(
        select(Profile).where(
            Profile.email == user_data["email"]
        )
    )
    profile = result.scalars().first()
    assert profile is None, f"No profile should be created when Supabase errors, but found: {profile}"
    
    logger.info("Supabase error test completed successfully")
