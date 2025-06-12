import pytest
import pytest_asyncio
import uuid
from datetime import datetime
from httpx import AsyncClient
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, and_

from auth_service.main import app
from auth_service.models.role import Role
from auth_service.models.app_client import AppClient
from auth_service.models.app_client_role import AppClientRole
from auth_service.dependencies.user_deps import get_current_supabase_user
from auth_service.schemas.user_schemas import SupabaseUser
from auth_service.schemas.common_schemas import MessageResponse
from auth_service.db import get_db
from auth_service.security import hash_secret

# Fixed test client IDs to use consistently across tests
TEST_CLIENT_ID_1 = uuid.UUID('10000000-0000-0000-0000-000000000001')
TEST_CLIENT_ID_2 = uuid.UUID('10000000-0000-0000-0000-000000000002')


@pytest_asyncio.fixture
async def disable_fk_constraints(db_session_for_crud):
    """Temporarily disable foreign key constraints for testing"""
    # Note: This is PostgreSQL syntax. For MySQL use SET FOREIGN_KEY_CHECKS=0
    await db_session_for_crud.execute(text("SET session_replication_role = 'replica'"))
    yield db_session_for_crud
    # Re-enable constraints
    await db_session_for_crud.execute(text("SET session_replication_role = 'origin'"))


@pytest_asyncio.fixture
async def mock_admin_user():
    """Creates a mock admin user for testing"""
    mock_admin_email = f"admin_{uuid.uuid4().hex[:8]}@example.com"
    current_time = datetime.now()
    
    return SupabaseUser(
        id=uuid.uuid4(),
        email=mock_admin_email,
        aud="authenticated",
        role="authenticated",
        created_at=current_time,
        updated_at=current_time,
        user_metadata={"roles": ["admin"]}
    )


@pytest.fixture
def setup_admin_dependency(mock_admin_user):
    """Sets up and tears down the admin user dependency override"""
    # Store original dependency
    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    
    # Override with mock admin user
    app.dependency_overrides[get_current_supabase_user] = lambda: mock_admin_user
    
    yield
    
    # Restore original dependency
    if original_dependency:
        app.dependency_overrides[get_current_supabase_user] = original_dependency
    else:
        del app.dependency_overrides[get_current_supabase_user]


@pytest_asyncio.fixture
async def create_test_client(disable_fk_constraints):
    """Create a test app client for testing"""
    db = disable_fk_constraints
    
    # Create test app client 1
    client1 = AppClient(
        id=TEST_CLIENT_ID_1,
        client_name="Test Client 1",
        client_secret_hash=hash_secret("test_secret_1"),
        description="Test client 1 for role assignments",
        allowed_callback_urls=["https://test1.example.com/callback"],
        is_active=True
    )
    db.add(client1)
    
    # Create test app client 2
    client2 = AppClient(
        id=TEST_CLIENT_ID_2,
        client_name="Test Client 2",
        client_secret_hash=hash_secret("test_secret_2"),
        description="Test client 2 for role assignments",
        allowed_callback_urls=["https://test2.example.com/callback"],
        is_active=True
    )
    db.add(client2)
    
    await db.commit()
    
    return [client1, client2]


@pytest.mark.asyncio
async def test_assign_role_to_client_success(
    async_client: AsyncClient,
    disable_fk_constraints: AsyncSession,
    setup_admin_dependency,
    mock_admin_user: SupabaseUser,
    create_test_client
):
    """Test successfully assigning a role to an app client."""
    db = disable_fk_constraints
    
    # 1. Create test role
    role = Role(name="test_assign_client_role", description="Test role for client assignment")
    db.add(role)
    await db.commit()
    await db.refresh(role)
    
    # 2. Test assigning role to client
    assignment_data = {
        "role_id": str(role.id)
    }
    
    response = await async_client.post(
        f"/auth/admin/clients/{TEST_CLIENT_ID_1}/roles",
        json=assignment_data,
        headers={"Authorization": "Bearer faketoken"}
    )
    
    # 3. Verify response
    assert response.status_code == status.HTTP_201_CREATED
    response_data = response.json()
    assert response_data["app_client_id"] == str(TEST_CLIENT_ID_1)
    assert response_data["role_id"] == str(role.id)
    assert "assigned_at" in response_data
    
    # 4. Verify database state
    query = select(AppClientRole).where(
        and_(
            AppClientRole.app_client_id == TEST_CLIENT_ID_1,
            AppClientRole.role_id == role.id
        )
    )
    result = await db.execute(query)
    client_role = result.scalar_one_or_none()
    assert client_role is not None, "Client-role assignment not found in database"


@pytest.mark.asyncio
async def test_assign_role_to_client_already_assigned(
    async_client: AsyncClient,
    disable_fk_constraints: AsyncSession,
    setup_admin_dependency,
    mock_admin_user: SupabaseUser,
    create_test_client
):
    """Test assigning a role to a client when it's already assigned."""
    db = disable_fk_constraints
    
    # 1. Create test role
    role = Role(name="test_already_assigned_role", description="Test role for already assigned")
    db.add(role)
    await db.commit()
    await db.refresh(role)
    
    # 2. Create the client-role assignment
    client_role = AppClientRole(app_client_id=TEST_CLIENT_ID_1, role_id=role.id)
    db.add(client_role)
    await db.commit()
    
    # 3. Try to assign the same role again
    assignment_data = {
        "role_id": str(role.id)
    }
    
    response = await async_client.post(
        f"/auth/admin/clients/{TEST_CLIENT_ID_1}/roles",
        json=assignment_data,
        headers={"Authorization": "Bearer faketoken"}
    )
    
    # 4. Verify response (should be conflict)
    assert response.status_code == status.HTTP_409_CONFLICT
    response_data = response.json()
    assert "already assigned" in response_data["detail"].lower()


@pytest.mark.asyncio
async def test_assign_nonexistent_role_to_client(
    async_client: AsyncClient,
    disable_fk_constraints: AsyncSession,
    setup_admin_dependency,
    mock_admin_user: SupabaseUser,
    create_test_client
):
    """Test assigning a non-existent role to a client."""
    # Generate a random UUID that doesn't exist in the database
    non_existent_role_id = uuid.uuid4()
    
    # Test assigning non-existent role
    assignment_data = {
        "role_id": str(non_existent_role_id)
    }
    
    response = await async_client.post(
        f"/auth/admin/clients/{TEST_CLIENT_ID_1}/roles",
        json=assignment_data,
        headers={"Authorization": "Bearer faketoken"}
    )
    
    # Verify response (should be not found)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    response_data = response.json()
    assert "not found" in response_data["detail"].lower()


@pytest.mark.asyncio
async def test_assign_role_to_nonexistent_client(
    async_client: AsyncClient,
    disable_fk_constraints: AsyncSession,
    setup_admin_dependency,
    mock_admin_user: SupabaseUser
):
    """Test assigning a role to a non-existent client."""
    db = disable_fk_constraints
    
    # 1. Create test role
    role = Role(name="test_client_not_found", description="Test role for client not found")
    db.add(role)
    await db.commit()
    await db.refresh(role)
    
    # Generate a random UUID that doesn't exist in the database
    non_existent_client_id = uuid.uuid4()
    
    # Test assigning role to non-existent client
    assignment_data = {
        "role_id": str(role.id)
    }
    
    response = await async_client.post(
        f"/auth/admin/clients/{non_existent_client_id}/roles",
        json=assignment_data,
        headers={"Authorization": "Bearer faketoken"}
    )
    
    # Verify response (should be not found)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    response_data = response.json()
    assert "not found" in response_data["detail"].lower()


@pytest.mark.asyncio
async def test_list_client_roles(
    async_client: AsyncClient,
    disable_fk_constraints: AsyncSession,
    setup_admin_dependency,
    mock_admin_user: SupabaseUser,
    create_test_client
):
    """Test listing roles assigned to a client."""
    db = disable_fk_constraints
    
    # 1. Create test roles
    roles = []
    for i in range(3):
        role = Role(name=f"test_list_client_role_{i}", description=f"Test role {i} for listing")
        db.add(role)
        roles.append(role)
    
    await db.commit()
    
    # Get the roles with their IDs
    query = select(Role).where(Role.name.like("test_list_client_role_%"))
    result = await db.execute(query)
    roles = result.scalars().all()
    
    # 2. Assign roles to the client
    for role in roles:
        client_role = AppClientRole(app_client_id=TEST_CLIENT_ID_1, role_id=role.id)
        db.add(client_role)
    
    await db.commit()
    
    # 3. List roles for the client
    response = await async_client.get(
        f"/auth/admin/clients/{TEST_CLIENT_ID_1}/roles",
        headers={"Authorization": "Bearer faketoken"}
    )
    
    # 4. Verify response
    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    assert "items" in response_data
    assert "count" in response_data
    assert response_data["count"] == 3
    assert len(response_data["items"]) == 3
    
    # Verify the role IDs match
    role_ids = [item["role_id"] for item in response_data["items"]]
    for role in roles:
        assert str(role.id) in role_ids


@pytest.mark.asyncio
async def test_list_client_roles_empty(
    async_client: AsyncClient,
    disable_fk_constraints: AsyncSession,
    setup_admin_dependency,
    mock_admin_user: SupabaseUser,
    create_test_client
):
    """Test listing roles for a client with no assigned roles."""
    # List roles for a client that has no roles assigned
    response = await async_client.get(
        f"/auth/admin/clients/{TEST_CLIENT_ID_2}/roles",
        headers={"Authorization": "Bearer faketoken"}
    )
    
    # Verify response (should be empty list)
    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    assert response_data["count"] == 0
    assert len(response_data["items"]) == 0


@pytest.mark.asyncio
async def test_remove_role_from_client(
    async_client: AsyncClient,
    disable_fk_constraints: AsyncSession,
    setup_admin_dependency,
    mock_admin_user: SupabaseUser,
    create_test_client
):
    """Test removing a role from a client."""
    db = disable_fk_constraints
    
    # 1. Create test role
    role = Role(name="test_remove_client_role", description="Test role for client removal")
    db.add(role)
    await db.commit()
    await db.refresh(role)
    
    # 2. Create the client-role assignment
    client_role = AppClientRole(app_client_id=TEST_CLIENT_ID_1, role_id=role.id)
    db.add(client_role)
    await db.commit()
    
    # 3. Remove role from client
    response = await async_client.delete(
        f"/auth/admin/clients/{TEST_CLIENT_ID_1}/roles/{role.id}",
        headers={"Authorization": "Bearer faketoken"}
    )
    
    # 4. Verify response
    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    assert "successfully removed" in response_data["message"].lower()
    
    # 5. Verify database state
    query = select(AppClientRole).where(
        and_(
            AppClientRole.app_client_id == TEST_CLIENT_ID_1,
            AppClientRole.role_id == role.id
        )
    )
    result = await db.execute(query)
    client_role = result.scalar_one_or_none()
    assert client_role is None, "Client-role assignment still exists in database"


@pytest.mark.asyncio
async def test_remove_role_not_assigned_to_client(
    async_client: AsyncClient,
    disable_fk_constraints: AsyncSession,
    setup_admin_dependency,
    mock_admin_user: SupabaseUser,
    create_test_client
):
    """Test removing a role that is not assigned to a client."""
    db = disable_fk_constraints
    
    # 1. Create test role (not assigned)
    role = Role(name="test_remove_unassigned_client", description="Test role for client unassigned removal")
    db.add(role)
    await db.commit()
    await db.refresh(role)
    
    # 2. Try to remove an unassigned role
    response = await async_client.delete(
        f"/auth/admin/clients/{TEST_CLIENT_ID_1}/roles/{role.id}",
        headers={"Authorization": "Bearer faketoken"}
    )
    
    # 3. Verify response (should be not found)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    response_data = response.json()
    assert "not assigned" in response_data["detail"].lower()
