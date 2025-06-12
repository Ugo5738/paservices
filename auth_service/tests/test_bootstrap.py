import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select

from auth_service.bootstrap import (
    bootstrap_admin_and_rbac,
    create_core_roles,
    create_core_permissions,
    assign_permissions_to_roles,
    create_admin_user,
    assign_admin_role_to_user,
    create_admin_profile
)
from auth_service.models.role import Role
from auth_service.models.permission import Permission
from auth_service.models.role_permission import RolePermission
from auth_service.models.user_role import UserRole


@pytest.mark.asyncio
async def test_create_core_roles(db_session_for_crud):
    # Test creating core roles
    role_ids = await create_core_roles(db_session_for_crud)
    
    # Verify that we have the expected roles
    assert "admin" in role_ids
    assert "user" in role_ids
    assert "service" in role_ids
    
    # Verify roles are in the database
    result = await db_session_for_crud.execute(select(Role))
    roles = result.scalars().all()
    assert len(roles) >= 3  # At least the core roles should exist
    
    # Verify idempotency - running again shouldn't create duplicates
    role_ids_2 = await create_core_roles(db_session_for_crud)
    result = await db_session_for_crud.execute(select(Role))
    roles_after = result.scalars().all()
    assert len(roles) == len(roles_after)  # Should be the same count


@pytest.mark.asyncio
async def test_create_core_permissions(db_session_for_crud):
    # Test creating core permissions
    perm_ids = await create_core_permissions(db_session_for_crud)
    
    # Verify that we have the expected permissions
    assert "users:read" in perm_ids
    assert "users:write" in perm_ids
    assert "role:admin_manage" in perm_ids
    
    # Verify permissions are in the database
    result = await db_session_for_crud.execute(select(Permission))
    perms = result.scalars().all()
    assert len(perms) >= 7  # At least the core permissions should exist


@pytest.mark.asyncio
async def test_assign_permissions_to_roles(db_session_for_crud):
    # First create roles and permissions
    role_ids = await create_core_roles(db_session_for_crud)
    perm_ids = await create_core_permissions(db_session_for_crud)
    
    # Test assigning permissions to roles
    await assign_permissions_to_roles(db_session_for_crud, role_ids, perm_ids)
    
    # Verify admin role has all permissions
    admin_role_id = role_ids["admin"]
    result = await db_session_for_crud.execute(
        select(RolePermission).where(RolePermission.role_id == admin_role_id)
    )
    admin_perms = result.scalars().all()
    assert len(admin_perms) == 7  # Admin should have all 7 core permissions
    
    # Verify user role has only users:read permission
    user_role_id = role_ids["user"]
    result = await db_session_for_crud.execute(
        select(RolePermission).where(RolePermission.role_id == user_role_id)
    )
    user_perms = result.scalars().all()
    assert len(user_perms) == 1  # User should have only 1 permission


@pytest.mark.asyncio
async def test_create_admin_user():
    # Import the actual function and schema
    from auth_service.schemas.user_schemas import SupabaseUser
    from gotrue.errors import AuthApiError
    
    # Create a concrete user UUID and test data
    user_id = uuid.uuid4()
    test_email = "admin@example.com"
    test_password = "password123"
    
    # Create an async context manager mock for the Supabase client
    class MockSupabaseContextManager:
        async def __aenter__(self):
            # Return self instead of client so we expose our own auth attribute
            return self
            
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
            
        def __init__(self, mock_client):
            self.client = mock_client
            # Important: Expose the auth attribute from the mock_client
            self.auth = mock_client.auth
    
    # Create our mock Supabase client with the necessary structure
    mock_supabase = AsyncMock()
    
    # Create user data that matches real response structure
    user_data = {
        "id": user_id,
        "email": test_email,
        "aud": "authenticated",
        "role": "authenticated",
        "phone": None,
        "email_confirmed_at": "2023-01-01T00:00:00Z",
        "phone_confirmed_at": None,
        "last_sign_in_at": None,
        "app_metadata": {},
        "user_metadata": {"roles": ["admin"]},
        "identities": [],
        "created_at": "2023-01-01T00:00:00Z",
        "updated_at": "2023-01-01T00:00:00Z"
    }
    
    # Setup the mock user object with the appropriate structure
    mock_user = type('User', (), user_data)
    
    # Setup the response structure
    mock_response = AsyncMock()
    mock_response.user = mock_user
    
    # Setup the auth admin client methods
    mock_supabase.auth.admin.create_user.return_value = mock_response
    
    # Mock the admin.list_users response for checking existing users
    # In the actual implementation, list_users returns an array directly, not an object with users property
    mock_supabase.auth.admin.list_users.return_value = []
    
    # Setup our context manager that will be returned by get_supabase_admin_client
    mock_context = MockSupabaseContextManager(mock_supabase)
    
    # Patch get_supabase_admin_client to return our context manager
    with patch('auth_service.bootstrap.get_supabase_admin_client', return_value=mock_context):
        # Call the actual function with test values
        admin_user = await create_admin_user(test_email, test_password)
        
        # Verify admin user was created and returned correctly
        assert admin_user is not None, "Admin user should not be None"
        assert admin_user.email == test_email, "Admin email does not match"
        assert admin_user.id == user_id, "Admin ID does not match"
        
        # Verify Supabase client was called with correct parameters
        mock_supabase.auth.admin.create_user.assert_called_once()
        create_user_args = mock_supabase.auth.admin.create_user.call_args[0][0]
        assert create_user_args["email"] == test_email
        assert create_user_args["password"] == test_password
        assert create_user_args["email_confirm"] is True


@pytest.mark.asyncio
async def test_bootstrap_admin_and_rbac():
    # Mock dependencies
    mock_db = AsyncMock()
    
    test_admin_email = "admin@example.com"
    test_admin_password = "password123"
    user_id = str(uuid.uuid4())
    admin_role_id = uuid.uuid4()
    
    # Create a properly structured user object that will pass validation
    user_data = {
        "id": user_id,
        "email": test_admin_email,
        "aud": "authenticated",
        "role": "authenticated",
        "phone": None,
        "email_confirmed_at": "2023-01-01T00:00:00Z",
        "phone_confirmed_at": None,
        "last_sign_in_at": None,
        "app_metadata": {},
        "user_metadata": {},
        "identities": [],
        "created_at": "2023-01-01T00:00:00Z",
        "updated_at": "2023-01-01T00:00:00Z"
    }
    # Create an object with attributes from the dictionary
    mock_user = type('User', (), user_data)
    
    # Mock successful execution of all sub-functions
    with patch('auth_service.bootstrap.create_core_roles') as mock_create_roles, \
         patch('auth_service.bootstrap.create_core_permissions') as mock_create_perms, \
         patch('auth_service.bootstrap.assign_permissions_to_roles') as mock_assign, \
         patch('auth_service.bootstrap.create_admin_user') as mock_create_admin, \
         patch('auth_service.bootstrap.create_admin_profile') as mock_create_profile, \
         patch('auth_service.bootstrap.assign_admin_role_to_user') as mock_assign_role, \
         patch('auth_service.bootstrap.get_supabase_admin_client'), \
         patch('auth_service.bootstrap.app_settings.initial_admin_email', test_admin_email), \
         patch('auth_service.bootstrap.app_settings.initial_admin_password', test_admin_password):
        
        # Configure mocks
        mock_create_roles.return_value = {"admin": admin_role_id, "user": uuid.uuid4()}
        mock_create_perms.return_value = {"users:read": uuid.uuid4()}
        mock_assign.return_value = None
        
        # Return our properly structured mock user
        mock_create_admin.return_value = mock_user
        
        mock_create_profile.return_value = True
        mock_assign_role.return_value = None
        
        # Test bootstrap process
        success = await bootstrap_admin_and_rbac(mock_db)
        
        # Verify bootstrap was successful
        assert success is True
        
        # Verify all functions were called
        mock_create_roles.assert_called_once_with(mock_db)
        mock_create_perms.assert_called_once_with(mock_db)
        mock_assign.assert_called_once()
        mock_create_admin.assert_called_once_with(test_admin_email, test_admin_password)
        mock_create_profile.assert_called_once_with(mock_db, mock_user)
        mock_assign_role.assert_called_once_with(mock_db, user_id, admin_role_id)
