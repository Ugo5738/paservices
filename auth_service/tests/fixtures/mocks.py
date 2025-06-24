"""
Mock fixtures for testing.
Provides mock implementations of external dependencies like Supabase client.
"""
import pytest_asyncio
from unittest.mock import AsyncMock


class MockSupabaseResponse:
    """Mock response from Supabase authentication endpoints."""
    def __init__(self):
        # Create a user object that matches SupabaseUser schema with all required fields
        User = type('User', (), {
            'id': '11111111-1111-4111-a111-111111111111',
            'email': 'test@example.com',
            'app_metadata': {},
            'user_metadata': {'username': 'test_user'},
            'phone': '',
            'phone_confirmed_at': None, # Add phone_confirmed_at field
            'email_confirmed_at': '2025-06-19T00:00:00Z',
            'confirmed_at': '2025-06-19T00:00:00Z', # Add confirmed_at field
            'last_sign_in_at': '2025-06-19T00:00:00Z', # Add last_sign_in_at field
            'created_at': '2025-06-19T00:00:00Z',
            'updated_at': '2025-06-19T00:00:00Z',
            'identities': [], # Add identities field
            'aud': 'authenticated',
            'role': 'authenticated',
            'model_dump': lambda self: {
                'id': self.id,
                'email': self.email,
                'app_metadata': self.app_metadata,
                'user_metadata': self.user_metadata,
                'phone': self.phone,
                'phone_confirmed_at': self.phone_confirmed_at,
                'email_confirmed_at': self.email_confirmed_at,
                'confirmed_at': self.confirmed_at,
                'last_sign_in_at': self.last_sign_in_at,
                'created_at': self.created_at,
                'updated_at': self.updated_at,
                'identities': self.identities,
                'aud': self.aud,
                'role': self.role,
            }
        })
        self.user = User()
        
        # Create Session class with model_dump method to match Pydantic behavior
        # and include the user object as required by SupabaseSession schema
        Session = type('Session', (), {
            'access_token': 'mock_access_token',
            'refresh_token': 'mock_refresh_token',
            'expires_at': 9999999999,
            'token_type': 'bearer',
            'model_dump': lambda self: {
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'expires_at': self.expires_at,
                'token_type': self.token_type,
                'user': self.user.model_dump() if hasattr(self, 'user') else None
            }
        })
        session = Session()
        session.user = self.user  # Key change: add user to session
        self.session = session


@pytest_asyncio.fixture
async def mock_supabase_client():
    """
    Create a mock Supabase client for testing that responds to authentication methods.
    The client will return a consistent user ID that we can use to pre-create database
    records to satisfy foreign key constraints.
    """
    # Generate a fixed test user ID that will be consistent across the test
    test_user_id = "11111111-1111-4111-a111-111111111111"
    
    # Create a mock response with user and session data
    # Override the user ID in the mock response
    mock_auth_response = MockSupabaseResponse()
    mock_auth_response.user.id = test_user_id
    
    # Configure the auth methods to return our mock response
    mock_auth = AsyncMock()
    mock_auth.sign_up = AsyncMock(return_value=mock_auth_response)
    
    # Create a UserResponse class that has a user attribute to match expected structure
    UserResponse = type('UserResponse', (), {})
    user_response = UserResponse()
    user_response.user = mock_auth_response.user
    
    # Properly configure get_user to return a response with nested user attribute
    mock_auth.get_user = AsyncMock(return_value=user_response)
    
    # Create the main Supabase client mock
    mock_client = AsyncMock()
    mock_client.auth = mock_auth
    
    # Add the test user ID as an attribute so tests can access it
    mock_client.test_user_id = test_user_id
    
    # Add the user object to the mock client for direct access in tests
    mock_client.user = mock_auth_response.user
    
    print(f"\nUsing mock Supabase client with test user ID: {test_user_id}")
    
    return mock_client


class MockCrud:
    """Mock CRUD operations for when we need to bypass the database."""
    
    @staticmethod
    async def get_profile_by_user_id(*args, **kwargs):
        """Mock implementation of get_profile_by_user_id."""
        return None
    
    @staticmethod
    async def get_profile_by_email(*args, **kwargs):
        """Mock implementation of get_profile_by_email."""
        return None
    
    @staticmethod
    async def create_profile_in_db(*args, **kwargs):
        """Mock implementation of create_profile_in_db."""
        from auth_service.models.profile import Profile
        import uuid
        from datetime import datetime
        
        profile_in = kwargs.get('profile_in', None)
        if not profile_in:
            return None
            
        return Profile(
            user_id=profile_in.user_id if hasattr(profile_in, 'user_id') else uuid.uuid4(),
            email=profile_in.email if hasattr(profile_in, 'email') else "mock@example.com",
            username=profile_in.username if hasattr(profile_in, 'username') else "mock_user",
            first_name=profile_in.first_name if hasattr(profile_in, 'first_name') else "Mock",
            last_name=profile_in.last_name if hasattr(profile_in, 'last_name') else "User",
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
