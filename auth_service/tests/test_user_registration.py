import pytest
import logging
import uuid
from datetime import datetime
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

# Import models for database verification
from auth_service.models.profile import Profile

# Import helper functions from fixtures module
from tests.fixtures.helpers import seed_test_user

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Generate a unique session ID for this test run
# This ensures unique user data across test runs
SESSION_ID = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio


async def test_register_user_success(client: AsyncClient, db_session: AsyncSession, mock_supabase_client):
    """
    Tests successful user registration.
    Verifies:
    1. The API returns a 201 Created status.
    2. The response contains the correct profile information and a success message.
    3. A new Profile record is created in the database with the correct data.
    """
    # Get the test user ID from the mock Supabase client
    test_user_id = mock_supabase_client.test_user_id
    
    # Create a test user in the database to satisfy foreign key constraints
    # This simulates a user being created in Auth DB by Supabase
    await seed_test_user(
        db_session=db_session,
        user_id=test_user_id,
        email=f"test.user.{SESSION_ID}@example.com",
        username=f"testuser_{SESSION_ID}"
    )
    
    # Arrange: Define test user data with a unique email to avoid conflicts
    user_data = {
        "email": f"test.user.{SESSION_ID}@example.com",
        "password": "a-very-secure-password123",
        "username": f"testuser_{SESSION_ID}",
        "first_name": "Test",
        "last_name": "User",
    }
    
    logger.info(f"Testing registration with user: {user_data['email']} and ID: {test_user_id}")

    # Act: Make the API call to the registration endpoint
    response = await client.post("/api/v1/auth/users/register", json=user_data)
    
    # Log response for debugging
    logger.info(f"Registration response status: {response.status_code}")
    if response.status_code != status.HTTP_201_CREATED:
        logger.error(f"Response body: {response.text}")

    # Assert: Check the API response
    assert response.status_code == status.HTTP_201_CREATED, f"Expected 201 but got {response.status_code}: {response.text}"
    
    # Parse response data
    response_data = response.json()

    # Verify response content
    assert "message" in response_data, "Response missing 'message' field"
    assert "profile" in response_data, "Response missing 'profile' field"  
    # If the email is already confirmed, the message is 'User registered successfully.'
    # Otherwise, it would be 'User registration initiated. Please check your email to confirm your account.'
    assert response_data["message"] == "User registered successfully."
    assert response_data["profile"]["email"] == user_data["email"]
    assert response_data["profile"]["username"] == user_data["username"]

    # Verify database state using the test database session
    # Query the database directly to confirm the profile was created with correct user_id
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
    
    logger.info(f"Successfully verified profile in database: {profile.email} with user_id: {profile.user_id}")

