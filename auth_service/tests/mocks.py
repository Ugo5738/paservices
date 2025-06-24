"""
Mock classes and functions for tests.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock

from auth_service.models.profile import Profile

class MockSupabaseUser:
    """Mock Supabase User that matches the expected schema."""
    
    def __init__(self, user_id=None):
        self.id = user_id or str(uuid.uuid4())
        self.aud = "authenticated"
        self.role = "authenticated"
        self.email = "test.user@example.com"
        self.phone = "+1234567890"
        self.email_confirmed_at = None  # Set to None to trigger the email confirmation message
        self.phone_confirmed_at = None
        self.confirmed_at = None  # Also set this to None to be consistent
        self.last_sign_in_at = datetime.now(timezone.utc).isoformat()
        self.app_metadata = {"provider": "email"}
        self.user_metadata = {
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User"
        }
        self.identities = []
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = datetime.now(timezone.utc).isoformat()

class MockSupabaseSession:
    """Mock Supabase Session that matches the expected schema."""
    
    def __init__(self, user=None):
        self.access_token = "mock-access-token.with.three.parts"
        self.token_type = "bearer"
        self.expires_in = 3600
        self.expires_at = datetime.now(timezone.utc) + timedelta(seconds=3600)
        self.refresh_token = "mock-refresh-token"
        self.user = user or MockSupabaseUser()

class MockSupabaseResponse:
    """Mock Supabase Auth Response containing user and session."""
    
    def __init__(self):
        user_id = str(uuid.uuid4())
        self.user = MockSupabaseUser(user_id)
        self.session = MockSupabaseSession(self.user)
        
class MockCrud:
    """Mock CRUD operations for testing."""
    
    @staticmethod
    async def create_profile_in_db(*args, **kwargs):
        """
        Mock creating a profile in the database.
        Returns a mock Profile object with predefined values.
        """
        # Create a profile object with proper attributes
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)
        
        class MockProfile:
            def __init__(self):
                # Handle the user_id correctly whether it's a string or UUID
                user_id_value = kwargs.get('profile_in').user_id
                self.user_id = user_id_value if isinstance(user_id_value, uuid.UUID) else uuid.UUID(user_id_value)
                self.email = kwargs.get('profile_in').email
                self.username = kwargs.get('profile_in').username
                self.first_name = kwargs.get('profile_in').first_name
                self.last_name = kwargs.get('profile_in').last_name
                self.is_active = True
                self.created_at = created_at
                self.updated_at = updated_at
            
            def model_dump(self) -> Dict[str, Any]:
                """Convert profile to dict representation"""
                return {
                    "user_id": str(self.user_id),
                    "email": self.email,
                    "username": self.username,
                    "first_name": self.first_name,
                    "last_name": self.last_name,
                    "is_active": self.is_active,
                    "created_at": self.created_at.isoformat(),
                    "updated_at": self.updated_at.isoformat()
                }
        
        return MockProfile()
