import pytest
import uuid
from datetime import datetime
from httpx import AsyncClient
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.main import app
from auth_service.models.role import Role
from auth_service.dependencies.user_deps import get_current_supabase_user
from auth_service.schemas.user_schemas import SupabaseUser


@pytest.mark.asyncio
async def test_create_role_success(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession
):
    """Test successfully creating a new role."""
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
        # 2. Create a new role
        role_data = {
            "name": "test_role",
            "description": "Test role for integration tests"
        }
        
        response = await async_client.post(
            "/auth/admin/roles",
            json=role_data,
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 3. Verify the response
        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert response_data["name"] == role_data["name"]
        assert response_data["description"] == role_data["description"]
        assert "id" in response_data
        assert "created_at" in response_data
        assert "updated_at" in response_data
        
        # 4. Verify database state
        role_id = uuid.UUID(response_data["id"])
        db_role = await db_session_for_crud.get(Role, role_id)
        assert db_role is not None
        assert db_role.name == role_data["name"]
        assert db_role.description == role_data["description"]
    finally:
        # Cleanup: Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_create_role_duplicate_name(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession
):
    """Test creating a role with a duplicate name."""
    # 1. Setup: Create a role and a mock admin user
    existing_role = Role(name="existing_role", description="Existing role for testing")
    db_session_for_crud.add(existing_role)
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
        # 2. Attempt to create a role with the same name
        role_data = {
            "name": "existing_role",  # Same name as existing role
            "description": "This should fail"
        }
        
        response = await async_client.post(
            "/auth/admin/roles",
            json=role_data,
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
async def test_create_role_unauthorized(
    async_client: AsyncClient
):
    """Test creating a role without admin privileges."""
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
        # 2. Attempt to create a new role
        role_data = {
            "name": "unauthorized_role",
            "description": "This should fail due to permissions"
        }
        
        response = await async_client.post(
            "/auth/admin/roles",
            json=role_data,
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
async def test_list_roles(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession
):
    """Test listing roles."""
    # 1. Setup: Create test roles and a mock admin user
    for i in range(5):
        role = Role(name=f"list_test_role_{i}", description=f"Test role {i} for list operation")
        db_session_for_crud.add(role)
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
        # 2. List roles
        response = await async_client.get(
            "/auth/admin/roles",
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 3. Verify the response
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert "items" in response_data
        assert "count" in response_data
        assert response_data["count"] >= 5  # At least our 5 test roles
        
        # Check if our test roles are in the response
        role_names = [role["name"] for role in response_data["items"]]
        for i in range(5):
            assert f"list_test_role_{i}" in role_names
    finally:
        # Cleanup: Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_get_role(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession
):
    """Test retrieving a single role by ID."""
    # 1. Setup: Create a test role and a mock admin user
    role = Role(name="get_test_role", description="Test role for get operation")
    db_session_for_crud.add(role)
    await db_session_for_crud.commit()
    await db_session_for_crud.refresh(role)  # To get the ID
    
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
        # 2. Get the role by ID
        response = await async_client.get(
            f"/auth/admin/roles/{role.id}",
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 3. Verify the response
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["id"] == str(role.id)
        assert response_data["name"] == role.name
        assert response_data["description"] == role.description
    finally:
        # Cleanup: Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_update_role(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession
):
    """Test updating a role."""
    # 1. Setup: Create a test role and a mock admin user
    role = Role(name="update_test_role", description="Original description")
    db_session_for_crud.add(role)
    await db_session_for_crud.commit()
    await db_session_for_crud.refresh(role)  # To get the ID
    
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
        # 2. Update the role
        update_data = {
            "name": "updated_role_name",
            "description": "Updated description"
        }
        
        response = await async_client.put(
            f"/auth/admin/roles/{role.id}",
            json=update_data,
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 3. Verify the response
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["id"] == str(role.id)
        assert response_data["name"] == update_data["name"]
        assert response_data["description"] == update_data["description"]
        
        # 4. Verify database state
        await db_session_for_crud.refresh(role)
        assert role.name == update_data["name"]
        assert role.description == update_data["description"]
    finally:
        # Cleanup: Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_delete_role(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession
):
    """Test deleting a role."""
    # 1. Setup: Create a test role and a mock admin user
    role = Role(name="delete_test_role", description="Test role for deletion")
    db_session_for_crud.add(role)
    await db_session_for_crud.commit()
    await db_session_for_crud.refresh(role)  # To get the ID
    
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
        # 2. Delete the role
        response = await async_client.delete(
            f"/auth/admin/roles/{role.id}",
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 3. Verify the response
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert "successfully deleted" in response_data["message"].lower()
        
        # 4. Verify database state
        deleted_role = await db_session_for_crud.get(Role, role.id)
        assert deleted_role is None
    finally:
        # Cleanup: Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]
