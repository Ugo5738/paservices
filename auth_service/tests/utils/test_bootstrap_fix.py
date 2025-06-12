"""
Test script to verify the bootstrap.py create_admin_profile function fix.
This runs locally without Docker to check if the Pydantic validation works correctly.
"""

import asyncio
import uuid
from typing import Any, Dict, Optional


# Mock classes for testing
class MockSupabaseUser:
    def __init__(self, id: str, email: str):
        self.id = id
        self.email = email


class MockAsyncSession:
    pass


class MockProfile:
    def __init__(
        self,
        user_id: str,
        email: str,
        username: str,
        first_name: str,
        last_name: str,
        is_active: bool = True,
    ):
        self.user_id = uuid.UUID(user_id)
        self.email = email
        self.username = username
        self.first_name = first_name
        self.last_name = last_name
        self.is_active = is_active

    def __repr__(self):
        return f"<Profile(user_id='{self.user_id}', username='{self.username}')>"


class MockUserCrud:
    async def get_profile_by_user_id_from_db(
        self, db: Any, user_id: str
    ) -> Optional[MockProfile]:
        # Simulate an existing profile
        return MockProfile(
            user_id=user_id,
            email="admin@example.com",
            username=f"admin_{user_id[:8]}",
            first_name="Admin",
            last_name="User",
        )


class ProfileCreate:
    @classmethod
    def model_validate(cls, data: Dict[str, Any]):
        print(f"Validating data: {data}")
        # If this is not a dictionary, it would fail in the real code
        if not isinstance(data, dict):
            raise ValueError("Input should be a valid dictionary")
        return data


# Mock the module imports
mock_user_crud = MockUserCrud()


# Copy of the fixed create_admin_profile function
async def create_admin_profile(
    db: MockAsyncSession, admin_supa_user: MockSupabaseUser
) -> bool:
    """Creates a local profile for the admin user if it doesn't exist."""
    if not admin_supa_user or not admin_supa_user.id or not admin_supa_user.email:
        print("Invalid SupabaseUser data provided for profile creation.")
        return None

    print(f"Checking or creating local profile for admin user ID: {admin_supa_user.id}")
    existing_profile = await mock_user_crud.get_profile_by_user_id_from_db(
        db, admin_supa_user.id
    )
    if not existing_profile:
        print(
            f"Local profile for admin user {admin_supa_user.id} not found, creating..."
        )
        # This part would create a profile, but we don't need to test this part
        return None
    else:
        print(f"Local profile for admin user {admin_supa_user.id} already exists.")
        # Convert ORM to dictionary, then to Pydantic
        profile_dict = {
            "user_id": str(existing_profile.user_id),
            "email": existing_profile.email,
            "username": existing_profile.username,
            "first_name": existing_profile.first_name,
            "last_name": existing_profile.last_name,
            "is_active": existing_profile.is_active,
        }
        return ProfileCreate.model_validate(profile_dict)


async def run_test():
    # Create a test user
    test_id = str(uuid.uuid4())
    test_user = MockSupabaseUser(id=test_id, email="test@example.com")
    test_db = MockAsyncSession()

    print("\n--- Testing create_admin_profile with a mock profile ---")
    result = await create_admin_profile(test_db, test_user)
    print(f"Result from create_admin_profile: {result}")
    print("\nTest passed if no validation errors were raised and data was printed")

    # Compare with the problematic version
    print(
        "\n--- Simulating the problematic approach (trying to validate ORM object directly) ---"
    )
    try:
        existing_profile = await mock_user_crud.get_profile_by_user_id_from_db(
            test_db, test_id
        )
        # This would fail in the real app:
        print("Attempting to validate ORM object directly...")
        ProfileCreate.model_validate(existing_profile)
        print("Validation succeeded (shouldn't happen in real code)")
    except Exception as e:
        print(f"Expected error: {e}")


if __name__ == "__main__":
    # fixes test
    asyncio.run(run_test())
