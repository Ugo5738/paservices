import pytest
import uuid
from datetime import datetime
from httpx import AsyncClient
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from auth_service.main import app
from auth_service.models.role import Role
from auth_service.models.permission import Permission
from auth_service.models.role_permission import RolePermission
from auth_service.dependencies.user_deps import get_current_supabase_user
from auth_service.schemas.user_schemas import SupabaseUser


@pytest.mark.asyncio
async def test_assign_permission_to_role_success(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession
):
    """Test successfully assigning a permission to a role."""
    # 1. Setup: Create test role, permission, and mock admin user
    role = Role(name="test_assign_role", description="Test role for permission assignment")
    permission = Permission(name="test:assign", description="Test permission for assignment")
    
    db_session_for_crud.add(role)
    db_session_for_crud.add(permission)
    await db_session_for_crud.commit()
    
    await db_session_for_crud.refresh(role)
    await db_session_for_crud.refresh(permission)
    
    # Create mock admin user
    mock_admin_email = "admin_" + str(uuid.uuid4())[:8] + "@example.com"
    current_time = datetime.now()
    
    mock_admin_supa_user = SupabaseUser(
        id=uuid.uuid4(),
        email=mock_admin_email,
        aud="authenticated",
        role="authenticated",
        created_at=current_time,
        updated_at=current_time,
        user_metadata={"roles": ["admin"]}
    )
    
    # Override the dependency
    async def mock_get_admin_user_override() -> SupabaseUser:
        return mock_admin_supa_user
    
    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = mock_get_admin_user_override
    
    try:
        # 2. Assign permission to role
        assignment_data = {
            "permission_id": str(permission.id)
        }
        
        response = await async_client.post(
            f"/auth/admin/roles/{role.id}/permissions",
            json=assignment_data,
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 3. Verify response
        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert response_data["role_id"] == str(role.id)
        assert response_data["permission_id"] == str(permission.id)
        assert "assigned_at" in response_data
        
        # 4. Verify database state
        query = text(f"SELECT * FROM role_permissions WHERE role_id = '{role.id}' AND permission_id = '{permission.id}'")
        result = await db_session_for_crud.execute(query)
        row = result.first()
        assert row is not None, "Role-permission assignment not found in database"
    finally:
        # Cleanup: Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_assign_permission_to_role_already_assigned(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession
):
    """Test assigning a permission to a role when it's already assigned."""
    # 1. Setup: Create test role, permission, role-permission assignment, and mock admin user
    role = Role(name="test_already_assigned_role", description="Test role for duplicate assignment")
    permission = Permission(name="test:already_assigned", description="Test permission for duplicate assignment")
    
    db_session_for_crud.add(role)
    db_session_for_crud.add(permission)
    await db_session_for_crud.commit()
    
    await db_session_for_crud.refresh(role)
    await db_session_for_crud.refresh(permission)
    
    # Create the role-permission assignment
    role_permission = RolePermission(role_id=role.id, permission_id=permission.id)
    db_session_for_crud.add(role_permission)
    await db_session_for_crud.commit()
    
    # Create mock admin user
    mock_admin_email = "admin_" + str(uuid.uuid4())[:8] + "@example.com"
    current_time = datetime.now()
    
    mock_admin_supa_user = SupabaseUser(
        id=uuid.uuid4(),
        email=mock_admin_email,
        aud="authenticated",
        role="authenticated",
        created_at=current_time,
        updated_at=current_time,
        user_metadata={"roles": ["admin"]}
    )
    
    # Override the dependency
    async def mock_get_admin_user_override() -> SupabaseUser:
        return mock_admin_supa_user
    
    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = mock_get_admin_user_override
    
    try:
        # 2. Try to assign the same permission again
        assignment_data = {
            "permission_id": str(permission.id)
        }
        
        response = await async_client.post(
            f"/auth/admin/roles/{role.id}/permissions",
            json=assignment_data,
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 3. Verify response (should be conflict)
        assert response.status_code == status.HTTP_409_CONFLICT
        response_data = response.json()
        assert "already assigned" in response_data["detail"].lower()
    finally:
        # Cleanup: Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_assign_permission_to_role_not_found(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession
):
    """Test assigning a permission to a non-existent role."""
    # 1. Setup: Create test permission and mock admin user
    permission = Permission(name="test:role_not_found", description="Test permission for non-existent role")
    
    db_session_for_crud.add(permission)
    await db_session_for_crud.commit()
    await db_session_for_crud.refresh(permission)
    
    # Generate a random UUID for non-existent role
    non_existent_role_id = uuid.uuid4()
    
    # Create mock admin user
    mock_admin_email = "admin_" + str(uuid.uuid4())[:8] + "@example.com"
    current_time = datetime.now()
    
    mock_admin_supa_user = SupabaseUser(
        id=uuid.uuid4(),
        email=mock_admin_email,
        aud="authenticated",
        role="authenticated",
        created_at=current_time,
        updated_at=current_time,
        user_metadata={"roles": ["admin"]}
    )
    
    # Override the dependency
    async def mock_get_admin_user_override() -> SupabaseUser:
        return mock_admin_supa_user
    
    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = mock_get_admin_user_override
    
    try:
        # 2. Try to assign permission to non-existent role
        assignment_data = {
            "permission_id": str(permission.id)
        }
        
        response = await async_client.post(
            f"/auth/admin/roles/{non_existent_role_id}/permissions",
            json=assignment_data,
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 3. Verify response (should be not found)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        response_data = response.json()
        assert "not found" in response_data["detail"].lower()
    finally:
        # Cleanup: Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_assign_permission_not_found_to_role(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession
):
    """Test assigning a non-existent permission to a role."""
    # 1. Setup: Create test role and mock admin user
    role = Role(name="test_permission_not_found", description="Test role for non-existent permission")
    
    db_session_for_crud.add(role)
    await db_session_for_crud.commit()
    await db_session_for_crud.refresh(role)
    
    # Generate a random UUID for non-existent permission
    non_existent_permission_id = uuid.uuid4()
    
    # Create mock admin user
    mock_admin_email = "admin_" + str(uuid.uuid4())[:8] + "@example.com"
    current_time = datetime.now()
    
    mock_admin_supa_user = SupabaseUser(
        id=uuid.uuid4(),
        email=mock_admin_email,
        aud="authenticated",
        role="authenticated",
        created_at=current_time,
        updated_at=current_time,
        user_metadata={"roles": ["admin"]}
    )
    
    # Override the dependency
    async def mock_get_admin_user_override() -> SupabaseUser:
        return mock_admin_supa_user
    
    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = mock_get_admin_user_override
    
    try:
        # 2. Try to assign non-existent permission to role
        assignment_data = {
            "permission_id": str(non_existent_permission_id)
        }
        
        response = await async_client.post(
            f"/auth/admin/roles/{role.id}/permissions",
            json=assignment_data,
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 3. Verify response (should be not found)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        response_data = response.json()
        assert "not found" in response_data["detail"].lower()
    finally:
        # Cleanup: Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_list_role_permissions(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession
):
    """Test listing permissions assigned to a role."""
    # 1. Setup: Create test role, permissions, role-permission assignments, and mock admin user
    role = Role(name="test_list_permissions_role", description="Test role for listing permissions")
    
    db_session_for_crud.add(role)
    await db_session_for_crud.commit()
    await db_session_for_crud.refresh(role)
    
    # Create multiple permissions and assign to the role
    permissions = []
    for i in range(3):
        permission = Permission(name=f"test:list{i}", description=f"Test permission {i} for listing")
        db_session_for_crud.add(permission)
    
    await db_session_for_crud.commit()
    
    # Get the permissions with their IDs
    query = text("SELECT * FROM permissions WHERE name LIKE 'test:list%'")
    result = await db_session_for_crud.execute(query)
    permissions = result.all()
    
    # Assign permissions to the role
    for permission in permissions:
        role_permission = RolePermission(role_id=role.id, permission_id=permission.id)
        db_session_for_crud.add(role_permission)
    
    await db_session_for_crud.commit()
    
    # Create mock admin user
    mock_admin_email = "admin_" + str(uuid.uuid4())[:8] + "@example.com"
    current_time = datetime.now()
    
    mock_admin_supa_user = SupabaseUser(
        id=uuid.uuid4(),
        email=mock_admin_email,
        aud="authenticated",
        role="authenticated",
        created_at=current_time,
        updated_at=current_time,
        user_metadata={"roles": ["admin"]}
    )
    
    # Override the dependency
    async def mock_get_admin_user_override() -> SupabaseUser:
        return mock_admin_supa_user
    
    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = mock_get_admin_user_override
    
    try:
        # 2. List permissions for the role
        response = await async_client.get(
            f"/auth/admin/roles/{role.id}/permissions",
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 3. Verify response
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert "items" in response_data
        assert "count" in response_data
        assert response_data["count"] == 3
        assert len(response_data["items"]) == 3
        
        # Verify the permission IDs match
        permission_ids = [item["permission_id"] for item in response_data["items"]]
        for permission in permissions:
            assert str(permission.id) in permission_ids
    finally:
        # Cleanup: Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_remove_permission_from_role(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession
):
    """Test removing a permission from a role."""
    # 1. Setup: Create test role, permission, role-permission assignment, and mock admin user
    role = Role(name="test_remove_permission_role", description="Test role for permission removal")
    permission = Permission(name="test:remove", description="Test permission for removal")
    
    db_session_for_crud.add(role)
    db_session_for_crud.add(permission)
    await db_session_for_crud.commit()
    
    await db_session_for_crud.refresh(role)
    await db_session_for_crud.refresh(permission)
    
    # Create the role-permission assignment
    role_permission = RolePermission(role_id=role.id, permission_id=permission.id)
    db_session_for_crud.add(role_permission)
    await db_session_for_crud.commit()
    
    # Create mock admin user
    mock_admin_email = "admin_" + str(uuid.uuid4())[:8] + "@example.com"
    current_time = datetime.now()
    
    mock_admin_supa_user = SupabaseUser(
        id=uuid.uuid4(),
        email=mock_admin_email,
        aud="authenticated",
        role="authenticated",
        created_at=current_time,
        updated_at=current_time,
        user_metadata={"roles": ["admin"]}
    )
    
    # Override the dependency
    async def mock_get_admin_user_override() -> SupabaseUser:
        return mock_admin_supa_user
    
    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = mock_get_admin_user_override
    
    try:
        # 2. Remove permission from role
        response = await async_client.delete(
            f"/auth/admin/roles/{role.id}/permissions/{permission.id}",
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 3. Verify response
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert "successfully removed" in response_data["message"].lower()
        
        # 4. Verify database state
        query = text(f"SELECT * FROM role_permissions WHERE role_id = '{role.id}' AND permission_id = '{permission.id}'")
        result = await db_session_for_crud.execute(query)
        row = result.first()
        assert row is None, "Role-permission assignment still exists in database"
    finally:
        # Cleanup: Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_remove_permission_not_assigned_to_role(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession
):
    """Test removing a permission that is not assigned to a role."""
    # 1. Setup: Create test role, permission (not assigned), and mock admin user
    role = Role(name="test_remove_nonexistent", description="Test role for non-existent permission removal")
    permission = Permission(name="test:not_assigned", description="Test permission not assigned")
    
    db_session_for_crud.add(role)
    db_session_for_crud.add(permission)
    await db_session_for_crud.commit()
    
    await db_session_for_crud.refresh(role)
    await db_session_for_crud.refresh(permission)
    
    # Create mock admin user
    mock_admin_email = "admin_" + str(uuid.uuid4())[:8] + "@example.com"
    current_time = datetime.now()
    
    mock_admin_supa_user = SupabaseUser(
        id=uuid.uuid4(),
        email=mock_admin_email,
        aud="authenticated",
        role="authenticated",
        created_at=current_time,
        updated_at=current_time,
        user_metadata={"roles": ["admin"]}
    )
    
    # Override the dependency
    async def mock_get_admin_user_override() -> SupabaseUser:
        return mock_admin_supa_user
    
    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = mock_get_admin_user_override
    
    try:
        # 2. Try to remove a permission that is not assigned
        response = await async_client.delete(
            f"/auth/admin/roles/{role.id}/permissions/{permission.id}",
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 3. Verify response (should be not found)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        response_data = response.json()
        assert "not assigned" in response_data["detail"].lower()
    finally:
        # Cleanup: Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]
