import pytest
import pytest_asyncio
from datetime import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from auth_service.dependencies.user_deps import require_admin_user
from auth_service.schemas.user_schemas import SupabaseUser


# Helper function to create users with specific metadata
async def create_test_user(metadata_roles=None, app_metadata_roles=None, app_metadata_permissions=None):
    """Create a test user with specified metadata roles and JWT claims"""
    current_time = datetime.now()
    
    # Default values if None
    metadata_roles = metadata_roles or []
    app_metadata_roles = app_metadata_roles or []
    app_metadata_permissions = app_metadata_permissions or []
    
    return SupabaseUser(
        id=uuid.uuid4(),
        email="test@example.com",
        aud="authenticated",
        role="authenticated",
        created_at=current_time,
        updated_at=current_time,
        user_metadata={"roles": metadata_roles},
        app_metadata={
            "roles": app_metadata_roles,
            "permissions": app_metadata_permissions
        }
    )


@pytest.mark.asyncio
async def test_require_admin_user_with_legacy_admin_role():
    """Test that a user with the legacy 'admin' role in user_metadata passes"""
    # Arrange
    user = await create_test_user(metadata_roles=["admin"])
    
    # Act
    result = await require_admin_user(user)
    
    # Assert
    assert result == user


@pytest.mark.asyncio
async def test_require_admin_user_with_jwt_admin_role():
    """Test that a user with 'admin' role in JWT roles passes"""
    # Arrange
    user = await create_test_user(app_metadata_roles=["admin"])
    
    # Act
    result = await require_admin_user(user)
    
    # Assert
    assert result == user


@pytest.mark.asyncio
async def test_require_admin_user_with_admin_permission():
    """Test that a user with 'role:admin_manage' permission passes"""
    # Arrange
    user = await create_test_user(app_metadata_permissions=["role:admin_manage"])
    
    # Act
    result = await require_admin_user(user)
    
    # Assert
    assert result == user


@pytest.mark.asyncio
async def test_require_admin_user_with_multiple_admin_privileges():
    """Test that a user with multiple admin privileges passes"""
    # Arrange
    user = await create_test_user(
        metadata_roles=["admin"],
        app_metadata_roles=["admin", "super_admin"],
        app_metadata_permissions=["role:admin_manage"]
    )
    
    # Act
    result = await require_admin_user(user)
    
    # Assert
    assert result == user


@pytest.mark.asyncio
async def test_require_admin_user_with_no_admin_privileges():
    """Test that a user without admin privileges gets a 403 error"""
    # Arrange
    user = await create_test_user(
        metadata_roles=["user"],
        app_metadata_roles=["user"],
        app_metadata_permissions=["basic:read"]
    )
    
    # Act / Assert
    with pytest.raises(HTTPException) as exc_info:
        await require_admin_user(user)
    
    # Assert the correct status code and detail
    assert exc_info.value.status_code == 403
    assert "does not have admin privileges" in exc_info.value.detail


@pytest.mark.asyncio
async def test_require_admin_user_with_empty_metadata():
    """Test that a user with empty metadata gets a 403 error"""
    # Arrange
    current_time = datetime.now()
    user = SupabaseUser(
        id=uuid.uuid4(),
        email="empty@example.com",
        aud="authenticated",
        role="authenticated",
        created_at=current_time,
        updated_at=current_time,
        user_metadata={},
        app_metadata={}
    )
    
    # Act / Assert
    with pytest.raises(HTTPException) as exc_info:
        await require_admin_user(user)
    
    # Assert the correct status code and detail
    assert exc_info.value.status_code == 403
    assert "does not have admin privileges" in exc_info.value.detail
