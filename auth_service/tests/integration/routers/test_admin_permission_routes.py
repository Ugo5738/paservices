import pytest
import uuid
from datetime import datetime
from httpx import AsyncClient
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.main import app
from auth_service.models.permission import Permission
from auth_service.dependencies.user_deps import get_current_supabase_user
from auth_service.schemas.user_schemas import SupabaseUser


@pytest.mark.asyncio
async def test_create_permission_success(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession
):
    """Test successfully creating a new permission."""
    # 1. Setup: Create a mock admin user
    mock_admin_email = "admin_" + str(uuid.uuid4())[:8] + "@example.com"
    # Add current time for created_at and updated_at fields
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
        # 2. Create a new permission with a unique name
        unique_suffix = str(uuid.uuid4())[:8]
        permission_data = {
            "name": f"users:read:{unique_suffix}",
            "description": "Permission to read user data"
        }
        
        response = await async_client.post(
            "/auth/admin/permissions",
            json=permission_data,
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 3. Verify the response
        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert response_data["name"] == permission_data["name"]
        assert response_data["description"] == permission_data["description"]
        assert "id" in response_data
        assert "created_at" in response_data
        assert "updated_at" in response_data
        
        # 4. Verify database state
        permission_id = uuid.UUID(response_data["id"])
        db_permission = await db_session_for_crud.get(Permission, permission_id)
        assert db_permission is not None
        assert db_permission.name == permission_data["name"]
        assert db_permission.description == permission_data["description"]
    finally:
        # Cleanup: Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_create_permission_duplicate_name(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession
):
    """Test creating a permission with a duplicate name."""
    # 1. Setup: Create a permission and a mock admin user with unique name
    unique_suffix = str(uuid.uuid4())[:8]
    unique_perm_name = f"users:write:{unique_suffix}"
    existing_permission = Permission(name=unique_perm_name, description="Permission to write user data")
    db_session_for_crud.add(existing_permission)
    await db_session_for_crud.commit()
    
    mock_admin_email = "admin_" + str(uuid.uuid4())[:8] + "@example.com"
    # Add current time for created_at and updated_at fields
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
        # 2. Attempt to create a permission with the same name
        permission_data = {
            "name": unique_perm_name,  # Same name as existing permission
            "description": "This should fail"
        }
        
        response = await async_client.post(
            "/auth/admin/permissions",
            json=permission_data,
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 3. Verify the response
        assert response.status_code == status.HTTP_409_CONFLICT
        response_data = response.json()
        assert "already exists" in response_data["detail"].lower()
    finally:
        # Cleanup: Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_create_permission_unauthorized(
    async_client: AsyncClient
):
    """Test creating a permission without admin privileges."""
    # 1. Setup: Create a mock non-admin user
    mock_user_email = "user_" + str(uuid.uuid4())[:8] + "@example.com"
    current_time = datetime.now()
    
    mock_supa_user = SupabaseUser(
        id=uuid.uuid4(),
        email=mock_user_email,
        aud="authenticated",
        role="authenticated",
        created_at=current_time,
        updated_at=current_time,
        user_metadata={"roles": ["user"]}  # Not an admin
    )
    
    # Override the dependency
    async def mock_get_user_override() -> SupabaseUser:
        return mock_supa_user
    
    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = mock_get_user_override
    
    try:
        # 2. Attempt to create a new permission
        permission_data = {
            "name": "unauthorized:action",
            "description": "This should fail due to permissions"
        }
        
        response = await async_client.post(
            "/auth/admin/permissions",
            json=permission_data,
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 3. Verify the response
        assert response.status_code == status.HTTP_403_FORBIDDEN
        response_data = response.json()
        assert "admin" in response_data["detail"].lower()
    finally:
        # Cleanup: Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_list_permissions(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession
):
    """Test listing permissions."""
    # 1. Setup: Create test permissions and a mock admin user
    for i in range(5):
        permission = Permission(name=f"test:permission{i}", description=f"Test permission {i} for list operation")
        db_session_for_crud.add(permission)
    await db_session_for_crud.commit()
    
    mock_admin_email = "admin_" + str(uuid.uuid4())[:8] + "@example.com"
    # Add current time for created_at and updated_at fields
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
        # 2. List permissions
        response = await async_client.get(
            "/auth/admin/permissions",
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 3. Verify the response
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert "items" in response_data
        assert "count" in response_data
        assert response_data["count"] >= 5  # At least our 5 test permissions
        
        # Check if our test permissions are in the response
        permission_names = [permission["name"] for permission in response_data["items"]]
        for i in range(5):
            assert f"test:permission{i}" in permission_names
    finally:
        # Cleanup: Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_get_permission(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession
):
    """Test retrieving a single permission by ID."""
    # 1. Setup: Create a test permission and a mock admin user
    permission = Permission(name="test:get", description="Test permission for get operation")
    db_session_for_crud.add(permission)
    await db_session_for_crud.commit()
    await db_session_for_crud.refresh(permission)  # To get the ID
    
    mock_admin_email = "admin_" + str(uuid.uuid4())[:8] + "@example.com"
    # Add current time for created_at and updated_at fields
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
        # 2. Get the permission by ID
        response = await async_client.get(
            f"/auth/admin/permissions/{permission.id}",
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 3. Verify the response
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["id"] == str(permission.id)
        assert response_data["name"] == permission.name
        assert response_data["description"] == permission.description
    finally:
        # Cleanup: Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_update_permission(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession
):
    """Test updating a permission."""
    # 1. Setup: Create a test permission and a mock admin user
    permission = Permission(name="test:update", description="Original description")
    db_session_for_crud.add(permission)
    await db_session_for_crud.commit()
    await db_session_for_crud.refresh(permission)  # To get the ID
    
    mock_admin_email = "admin_" + str(uuid.uuid4())[:8] + "@example.com"
    # Add current time for created_at and updated_at fields
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
        # 2. Update the permission
        update_data = {
            "name": "test:updated",
            "description": "Updated description"
        }
        
        response = await async_client.put(
            f"/auth/admin/permissions/{permission.id}",
            json=update_data,
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 3. Verify the response
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["id"] == str(permission.id)
        assert response_data["name"] == update_data["name"]
        assert response_data["description"] == update_data["description"]
        
        # 4. Verify database state
        await db_session_for_crud.refresh(permission)
        assert permission.name == update_data["name"]
        assert permission.description == update_data["description"]
    finally:
        # Cleanup: Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_delete_permission(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession
):
    """Test deleting a permission."""
    # 1. Setup: Create a test permission and a mock admin user
    permission = Permission(name="test:delete", description="Test permission for deletion")
    db_session_for_crud.add(permission)
    await db_session_for_crud.commit()
    await db_session_for_crud.refresh(permission)  # To get the ID
    
    mock_admin_email = "admin_" + str(uuid.uuid4())[:8] + "@example.com"
    # Add current time for created_at and updated_at fields
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
        # 2. Delete the permission
        response = await async_client.delete(
            f"/auth/admin/permissions/{permission.id}",
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 3. Verify the response
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert "successfully deleted" in response_data["message"].lower()
        
        # 4. Verify database state
        deleted_permission = await db_session_for_crud.get(Permission, permission.id)
        assert deleted_permission is None
    finally:
        # Cleanup: Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]
