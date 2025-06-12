import pytest
from unittest.mock import AsyncMock, patch
import sys
from auth_service.supabase_client import get_supabase_client, init_supabase_client, close_supabase_client

@pytest.mark.asyncio
async def test_supabase_client_initialization(monkeypatch):
    """Test that Supabase client is initialized with correct URL and key."""
    # Force reset the global Supabase client before testing
    import auth_service.supabase_client
    auth_service.supabase_client._global_async_supabase_client = None
    
    # Monkeypatch settings
    class DummySettings:
        supabase_url = "http://test_url.example.com"
        supabase_anon_key = "test_key"
        supabase_service_role_key = "test_service_key"
        environment = "testing"
        
        def is_production(self):
            return False

    # Create a mock Supabase client with required properties
    mock_client = AsyncMock()
    
    # Mock the create_async_supabase_client function
    async def mock_create_client(*args, **kwargs):
        # Verify that the URL and key are passed correctly to the client creation function
        assert args[0] == "http://test_url.example.com", "URL is incorrect"
        assert args[1] == "test_key", "Key is incorrect"
        return mock_client
    
    # Replace the settings and client creation function
    monkeypatch.setattr("auth_service.config.settings", DummySettings())
    monkeypatch.setattr("auth_service.supabase_client.create_async_supabase_client", mock_create_client)
    
    # Initialize the client with our mocked dependencies
    await init_supabase_client()
    
    # Get the client and verify it's our mock
    client = get_supabase_client()
    assert client is not None
    
    # In a test environment, get_supabase_client doesn't raise exceptions if client is None
    # so we need to directly verify it's our mock
    assert client is mock_client, "Client instance is not the same as the mock"
    
    # Clean up after test
    await close_supabase_client()
