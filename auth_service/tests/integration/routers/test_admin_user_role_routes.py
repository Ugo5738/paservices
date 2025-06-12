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
from auth_service.models.user_role import UserRole
from auth_service.dependencies.user_deps import get_current_supabase_user
from auth_service.schemas.user_schemas import SupabaseUser
from auth_service.schemas.common_schemas import MessageResponse
from auth_service.db import get_db

# Fixed test user IDs to use consistently across tests
TEST_USER_ID_1 = uuid.UUID('00000000-0000-0000-0000-000000000001')
TEST_USER_ID_2 = uuid.UUID('00000000-0000-0000-0000-000000000002')


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


@pytest.mark.asyncio
async def test_assign_role_to_user_success(
    async_client: AsyncClient,
    disable_fk_constraints: AsyncSession,
    setup_admin_dependency,
    mock_admin_user: SupabaseUser
):
    """Test successfully assigning a role to a user."""
    db = disable_fk_constraints
    
    # 1. Create test role
    role = Role(name="test_assign_user_role", description="Test role for user assignment")
    db.add(role)
    await db.commit()
    await db.refresh(role)
    
    # 2. Test assigning role to user (using the fixed test ID)
    assignment_data = {
        "role_id": str(role.id)
    }
    
    response = await async_client.post(
        f"/auth/admin/users/{TEST_USER_ID_1}/roles",
        json=assignment_data,
        headers={"Authorization": "Bearer faketoken"}
    )
    
    # 3. Verify response
    assert response.status_code == status.HTTP_201_CREATED
    response_data = response.json()
    assert response_data["user_id"] == str(TEST_USER_ID_1)
    assert response_data["role_id"] == str(role.id)
    assert "assigned_at" in response_data
    
    # 4. Verify database state
    query = select(UserRole).where(
        and_(
            UserRole.user_id == TEST_USER_ID_1,
            UserRole.role_id == role.id
        )
    )
    result = await db.execute(query)
    user_role = result.scalar_one_or_none()
    assert user_role is not None, "User-role assignment not found in database"


@pytest.mark.asyncio
async def test_assign_role_to_user_already_assigned(
    async_client: AsyncClient,
    disable_fk_constraints: AsyncSession,
    setup_admin_dependency,
    mock_admin_user: SupabaseUser
):
    """Test assigning a role to a user when it's already assigned."""
    db = disable_fk_constraints
    
    # 1. Create test role
    role = Role(name="test_already_assigned_role", description="Test role for duplicate assignment")
    db.add(role)
    await db.commit()
    await db.refresh(role)
    
    # 2. Create the user-role assignment first
    user_role = UserRole(user_id=TEST_USER_ID_1, role_id=role.id)
    db.add(user_role)
    await db.commit()
    
    # 3. Try to assign the same role again
    assignment_data = {
        "role_id": str(role.id)
    }
    
    response = await async_client.post(
        f"/auth/admin/users/{TEST_USER_ID_1}/roles",
        json=assignment_data,
        headers={"Authorization": "Bearer faketoken"}
    )
    
    # 4. Verify response (should be conflict)
    assert response.status_code == status.HTTP_409_CONFLICT
    response_data = response.json()
    assert "already assigned" in response_data["detail"].lower()


@pytest.mark.asyncio
async def test_assign_nonexistent_role_to_user(
    async_client: AsyncClient,
    disable_fk_constraints: AsyncSession,
    setup_admin_dependency,
    mock_admin_user: SupabaseUser
):
    """Test assigning a non-existent role to a user."""
    # 1. Generate a non-existent role ID
    non_existent_role_id = uuid.uuid4()
    
    # 2. Try to assign non-existent role to user
    assignment_data = {
        "role_id": str(non_existent_role_id)
    }
    
    response = await async_client.post(
        f"/auth/admin/users/{TEST_USER_ID_1}/roles",
        json=assignment_data,
        headers={"Authorization": "Bearer faketoken"}
    )
    
    # 3. Verify response (should be not found)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    response_data = response.json()
    assert "not found" in response_data["detail"].lower()


@pytest.mark.asyncio
async def test_list_user_roles(
    async_client: AsyncClient,
    disable_fk_constraints: AsyncSession,
    setup_admin_dependency,
    mock_admin_user: SupabaseUser
):
    """Test listing roles assigned to a user."""
    db = disable_fk_constraints
    
    # 1. Create multiple test roles
    roles = []
    for i in range(3):
        role = Role(name=f"test_list_role_{i}", description=f"Test role {i} for listing")
        db.add(role)
    
    await db.commit()
    
    # Get the roles with their IDs
    query = select(Role).where(Role.name.like("test_list_role_%"))
    result = await db.execute(query)
    roles = result.scalars().all()
    
    # 2. Assign roles to the user
    for role in roles:
        user_role = UserRole(user_id=TEST_USER_ID_1, role_id=role.id)
        db.add(user_role)
    
    await db.commit()
    
    # 3. List roles for the user
    response = await async_client.get(
        f"/auth/admin/users/{TEST_USER_ID_1}/roles",
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
async def test_list_user_roles_empty(
    async_client: AsyncClient,
    disable_fk_constraints: AsyncSession,
    setup_admin_dependency,
    mock_admin_user: SupabaseUser
):
    """Test listing roles for a user with no assigned roles."""
    # List roles for a user that has no roles assigned
    response = await async_client.get(
        f"/auth/admin/users/{TEST_USER_ID_2}/roles",
        headers={"Authorization": "Bearer faketoken"}
    )
    
    # Verify response (should be empty list)
    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    assert response_data["count"] == 0
    assert len(response_data["items"]) == 0


@pytest.mark.asyncio
async def test_remove_role_from_user(
    async_client: AsyncClient,
    disable_fk_constraints: AsyncSession,
    setup_admin_dependency,
    mock_admin_user: SupabaseUser
):
    """Test removing a role from a user."""
    db = disable_fk_constraints
    
    # 1. Create test role
    role = Role(name="test_remove_role", description="Test role for removal")
    db.add(role)
    await db.commit()
    await db.refresh(role)
    
    # 2. Create the user-role assignment
    user_role = UserRole(user_id=TEST_USER_ID_1, role_id=role.id)
    db.add(user_role)
    await db.commit()
    
    # 3. Remove role from user
    response = await async_client.delete(
        f"/auth/admin/users/{TEST_USER_ID_1}/roles/{role.id}",
        headers={"Authorization": "Bearer faketoken"}
    )
    
    # 4. Verify response
    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    assert "successfully removed" in response_data["message"].lower()
    
    # 5. Verify database state
    query = select(UserRole).where(
        and_(
            UserRole.user_id == TEST_USER_ID_1,
            UserRole.role_id == role.id
        )
    )
    result = await db.execute(query)
    user_role = result.scalar_one_or_none()
    assert user_role is None, "User-role assignment still exists in database"


@pytest.mark.asyncio
async def test_remove_role_not_assigned_to_user(
    async_client: AsyncClient,
    disable_fk_constraints: AsyncSession,
    setup_admin_dependency,
    mock_admin_user: SupabaseUser
):
    """Test removing a role that is not assigned to a user."""
    db = disable_fk_constraints
    
    # 1. Create test role (not assigned)
    role = Role(name="test_remove_unassigned", description="Test role for unassigned removal")
    db.add(role)
    await db.commit()
    await db.refresh(role)
    
    # 2. Try to remove an unassigned role
    response = await async_client.delete(
        f"/auth/admin/users/{TEST_USER_ID_1}/roles/{role.id}",
        headers={"Authorization": "Bearer faketoken"}
    )
    
    # 3. Verify response (should be not found)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    response_data = response.json()
    assert "not assigned" in response_data["detail"].lower()
