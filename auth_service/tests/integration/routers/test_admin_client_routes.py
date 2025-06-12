import pytest
import uuid # For generating mock user IDs
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import status

from auth_service.main import app # To override dependency
from auth_service.dependencies.user_deps import get_current_supabase_user # Dependency to mock
from auth_service.schemas.app_client_schemas import (
    AppClientCreateRequest, 
    AppClientCreatedResponse,
    AppClientResponse,
    AppClientListResponse,
    AppClientUpdateRequest
)
from auth_service.schemas.user_schemas import SupabaseUser # For type hinting
from tests.test_helpers import create_mock_supa_user # To create mock users
from auth_service.models.app_client import AppClient # To query DB
from auth_service.models.role import Role # To create Role for test
from auth_service.security import verify_client_secret # To verify hashed secret


@pytest.mark.asyncio
async def test_create_app_client_success(
    async_client: AsyncClient, 
    db_session_for_crud: AsyncSession # Renamed from test_db_session for consistency
):
    """Test successful creation of an app client by an admin user."""
    # 1. Setup: Create the 'user_read_own' role in the DB if it doesn't exist
    role_name_to_assign = "user_read_own"
    role_to_assign = Role(name=role_name_to_assign, description="Test role for app client")
    db_session_for_crud.add(role_to_assign)
    await db_session_for_crud.commit()
    await db_session_for_crud.refresh(role_to_assign)

    client_create_data = AppClientCreateRequest(
        client_name="Test Client One",
        description="A test client for integration testing.",
        allowed_callback_urls=["http://localhost:8080/callback"],
        assigned_roles=[role_name_to_assign]
    )

    mock_admin_user_id = uuid.uuid4()
    mock_admin_email = f"admin_{mock_admin_user_id.hex[:6]}@example.com"
    mock_admin_supa_user = create_mock_supa_user(
        id_val=mock_admin_user_id, 
        email=mock_admin_email, 
        user_roles=["admin"]
    )

    async def mock_get_admin_user_override() -> SupabaseUser:
        return mock_admin_supa_user

    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = mock_get_admin_user_override

    try:
        response = await async_client.post(
            "/auth/admin/clients", 
            json=client_create_data.model_dump(), 
            headers={"Authorization": "Bearer faketoken"} # Dummy token
        )
    finally:
        # Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]

    assert response.status_code == status.HTTP_201_CREATED
    
    response_data = response.json()
    created_client = AppClientCreatedResponse(**response_data)

    assert created_client.client_name == client_create_data.client_name
    assert created_client.description == client_create_data.description
    assert created_client.allowed_callback_urls == client_create_data.allowed_callback_urls
    assert created_client.assigned_roles == client_create_data.assigned_roles
    assert "client_id" in response_data
    assert "client_secret" in response_data # Important: client_secret should be returned ONCE upon creation
    assert "created_at" in response_data
    assert "updated_at" in response_data
    assert created_client.client_secret and isinstance(created_client.client_secret, str)

    # 2. Database Assertions
    db_client = await db_session_for_crud.get(AppClient, created_client.client_id)
    assert db_client is not None
    assert db_client.client_name == client_create_data.client_name
    assert db_client.description == client_create_data.description
    assert db_client.allowed_callback_urls == client_create_data.allowed_callback_urls
    assert db_client.is_active is True
    assert verify_client_secret(created_client.client_secret, db_client.client_secret_hash)

    # Assert roles assignment
    await db_session_for_crud.refresh(db_client, attribute_names=['roles'])
    assert len(db_client.roles) == 1
    assert db_client.roles[0].name == role_name_to_assign

    # Cleanup is handled by db_session_for_crud's rollback
    
    # Return the created client ID for other tests to use
    return created_client.client_id


@pytest.mark.asyncio
async def test_create_app_client_duplicate_name(
    async_client: AsyncClient, 
    db_session_for_crud: AsyncSession
):
    """Test that creating an app client with a duplicate name fails."""
    # 1. Create a client first
    existing_client = AppClient(
        id=uuid.uuid4(),
        client_name="Existing Client",
        client_secret_hash="dummy_hash",  # Not testing authentication here
        description="This client already exists",
        allowed_callback_urls=["http://localhost:8080/callback"],
        is_active=True
    )
    db_session_for_crud.add(existing_client)
    await db_session_for_crud.commit()
    
    # 2. Try to create another client with the same name
    client_create_data = AppClientCreateRequest(
        client_name="Existing Client",  # Same name as existing client
        description="This should fail due to duplicate name",
        allowed_callback_urls=["http://localhost:8080/callback"],
        assigned_roles=[]
    )
    
    # 3. Mock admin user
    mock_admin_user_id = uuid.uuid4()
    mock_admin_email = f"admin_{mock_admin_user_id.hex[:6]}@example.com"
    mock_admin_supa_user = create_mock_supa_user(
        id_val=mock_admin_user_id, 
        email=mock_admin_email, 
        user_roles=["admin"]
    )
    
    async def mock_get_admin_user_override() -> SupabaseUser:
        return mock_admin_supa_user
    
    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = mock_get_admin_user_override
    
    try:
        response = await async_client.post(
            "/auth/admin/clients", 
            json=client_create_data.model_dump(), 
            headers={"Authorization": "Bearer faketoken"}
        )
    finally:
        # Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]
    
    # 4. Verify response
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_app_client_unauthorized(
    async_client: AsyncClient
):
    """Test that non-admin users cannot create app clients."""
    # 1. Prepare request data
    client_create_data = AppClientCreateRequest(
        client_name="Unauthorized Client",
        description="This should fail due to lack of admin rights",
        allowed_callback_urls=["http://localhost:8080/callback"],
        assigned_roles=[]
    )
    
    # 2. Mock regular (non-admin) user
    mock_user_id = uuid.uuid4()
    mock_email = f"user_{mock_user_id.hex[:6]}@example.com"
    mock_supa_user = create_mock_supa_user(
        id_val=mock_user_id, 
        email=mock_email, 
        user_roles=["user"]  # Regular user role, not admin
    )
    
    async def mock_get_user_override() -> SupabaseUser:
        return mock_supa_user
    
    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = mock_get_user_override
    
    try:
        response = await async_client.post(
            "/auth/admin/clients", 
            json=client_create_data.model_dump(), 
            headers={"Authorization": "Bearer faketoken"}
        )
    finally:
        # Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]
    
    # 3. Verify response
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_list_app_clients(
    async_client: AsyncClient, 
    db_session_for_crud: AsyncSession
):
    """Test listing app clients."""
    # 1. Create multiple clients for testing
    clients = []
    for i in range(3):
        client = AppClient(
            id=uuid.uuid4(),
            client_name=f"Test List Client {i}",
            client_secret_hash=f"dummy_hash_{i}",
            description=f"Test client for listing {i}",
            allowed_callback_urls=["http://localhost:8080/callback"],
            is_active=True
        )
        db_session_for_crud.add(client)
        clients.append(client)
    
    # Add an inactive client to test filtering
    inactive_client = AppClient(
        id=uuid.uuid4(),
        client_name="Inactive Client",
        client_secret_hash="inactive_hash",
        description="Inactive client for testing",
        allowed_callback_urls=["http://localhost:8080/callback"],
        is_active=False
    )
    db_session_for_crud.add(inactive_client)
    
    await db_session_for_crud.commit()
    
    # 2. Mock admin user
    mock_admin_user_id = uuid.uuid4()
    mock_admin_email = f"admin_{mock_admin_user_id.hex[:6]}@example.com"
    mock_admin_supa_user = create_mock_supa_user(
        id_val=mock_admin_user_id, 
        email=mock_admin_email, 
        user_roles=["admin"]
    )
    
    async def mock_get_admin_user_override() -> SupabaseUser:
        return mock_admin_supa_user
    
    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = mock_get_admin_user_override
    
    try:
        # 3. Test listing all clients
        response = await async_client.get(
            "/auth/admin/clients", 
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 4. Verify response for all clients
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert "clients" in response_data
        assert "count" in response_data
        assert len(response_data["clients"]) >= 4  # At least our 4 test clients
        
        # 5. Test listing only active clients
        response_active = await async_client.get(
            "/auth/admin/clients?is_active=true", 
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 6. Verify response for active clients
        assert response_active.status_code == status.HTTP_200_OK
        response_active_data = response_active.json()
        active_client_names = [client["client_name"] for client in response_active_data["clients"]]
        assert "Inactive Client" not in active_client_names
        
        # 7. Test listing only inactive clients
        response_inactive = await async_client.get(
            "/auth/admin/clients?is_active=false", 
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 8. Verify response for inactive clients
        assert response_inactive.status_code == status.HTTP_200_OK
        response_inactive_data = response_inactive.json()
        inactive_client_names = [client["client_name"] for client in response_inactive_data["clients"]]
        assert "Inactive Client" in inactive_client_names
        for i in range(3):
            assert f"Test List Client {i}" not in inactive_client_names
    
    finally:
        # Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_get_app_client(
    async_client: AsyncClient, 
    db_session_for_crud: AsyncSession
):
    """Test getting a specific app client."""
    # 1. Create a client for testing
    client_id = uuid.uuid4()
    client = AppClient(
        id=client_id,
        client_name="Test Get Client",
        client_secret_hash="dummy_hash",
        description="Test client for getting",
        allowed_callback_urls=["http://localhost:8080/callback"],
        is_active=True
    )
    db_session_for_crud.add(client)
    await db_session_for_crud.commit()
    
    # 2. Mock admin user
    mock_admin_user_id = uuid.uuid4()
    mock_admin_email = f"admin_{mock_admin_user_id.hex[:6]}@example.com"
    mock_admin_supa_user = create_mock_supa_user(
        id_val=mock_admin_user_id, 
        email=mock_admin_email, 
        user_roles=["admin"]
    )
    
    async def mock_get_admin_user_override() -> SupabaseUser:
        return mock_admin_supa_user
    
    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = mock_get_admin_user_override
    
    try:
        # 3. Test getting existing client
        response = await async_client.get(
            f"/auth/admin/clients/{client_id}", 
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 4. Verify response
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["client_id"] == str(client_id)
        assert response_data["client_name"] == "Test Get Client"
        assert response_data["description"] == "Test client for getting"
        assert response_data["allowed_callback_urls"] == ["http://localhost:8080/callback"]
        assert response_data["is_active"] is True
        
        # 5. Test getting non-existent client
        non_existent_id = uuid.uuid4()
        response_not_found = await async_client.get(
            f"/auth/admin/clients/{non_existent_id}", 
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 6. Verify not found response
        assert response_not_found.status_code == status.HTTP_404_NOT_FOUND
    
    finally:
        # Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_update_app_client(
    async_client: AsyncClient, 
    db_session_for_crud: AsyncSession
):
    """Test updating an app client."""
    # 1. Create a client for testing
    client_id = uuid.uuid4()
    client = AppClient(
        id=client_id,
        client_name="Test Update Client",
        client_secret_hash="dummy_hash",
        description="Original description",
        allowed_callback_urls=["http://localhost:8080/callback"],
        is_active=True
    )
    db_session_for_crud.add(client)
    await db_session_for_crud.commit()
    
    # 2. Mock admin user
    mock_admin_user_id = uuid.uuid4()
    mock_admin_email = f"admin_{mock_admin_user_id.hex[:6]}@example.com"
    mock_admin_supa_user = create_mock_supa_user(
        id_val=mock_admin_user_id, 
        email=mock_admin_email, 
        user_roles=["admin"]
    )
    
    async def mock_get_admin_user_override() -> SupabaseUser:
        return mock_admin_supa_user
    
    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = mock_get_admin_user_override
    
    try:
        # 3. Test updating client
        update_data = AppClientUpdateRequest(
            client_name="Updated Client Name",
            description="Updated description",
            allowed_callback_urls=["http://updated-url.com/callback"],
            is_active=True
        )
        
        response = await async_client.put(
            f"/auth/admin/clients/{client_id}", 
            json=update_data.model_dump(),
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 4. Verify response
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["client_id"] == str(client_id)
        assert response_data["client_name"] == "Updated Client Name"
        assert response_data["description"] == "Updated description"
        assert response_data["allowed_callback_urls"] == ["http://updated-url.com/callback"]
        assert response_data["is_active"] is True
        
        # 5. Verify database update
        await db_session_for_crud.refresh(client)
        assert client.client_name == "Updated Client Name"
        assert client.description == "Updated description"
        assert client.allowed_callback_urls == ["http://updated-url.com/callback"]
        assert client.is_active is True
        
        # 6. Test updating non-existent client
        non_existent_id = uuid.uuid4()
        response_not_found = await async_client.put(
            f"/auth/admin/clients/{non_existent_id}", 
            json=update_data.model_dump(),
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 7. Verify not found response
        assert response_not_found.status_code == status.HTTP_404_NOT_FOUND
    
    finally:
        # Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_delete_app_client(
    async_client: AsyncClient, 
    db_session_for_crud: AsyncSession
):
    """Test deleting an app client."""
    # 1. Create a client for testing
    client_id = uuid.uuid4()
    client = AppClient(
        id=client_id,
        client_name="Test Delete Client",
        client_secret_hash="dummy_hash",
        description="Test client for deletion",
        allowed_callback_urls=["http://localhost:8080/callback"],
        is_active=True
    )
    db_session_for_crud.add(client)
    await db_session_for_crud.commit()
    
    # 2. Mock admin user
    mock_admin_user_id = uuid.uuid4()
    mock_admin_email = f"admin_{mock_admin_user_id.hex[:6]}@example.com"
    mock_admin_supa_user = create_mock_supa_user(
        id_val=mock_admin_user_id, 
        email=mock_admin_email, 
        user_roles=["admin"]
    )
    
    async def mock_get_admin_user_override() -> SupabaseUser:
        return mock_admin_supa_user
    
    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = mock_get_admin_user_override
    
    try:
        # 3. Test deleting client
        response = await async_client.delete(
            f"/auth/admin/clients/{client_id}", 
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 4. Verify response
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert "successfully deleted" in response_data["message"].lower()
        
        # 5. Verify database deletion
        deleted_client = await db_session_for_crud.get(AppClient, client_id)
        assert deleted_client is None
        
        # 6. Test deleting non-existent client
        non_existent_id = uuid.uuid4()
        response_not_found = await async_client.delete(
            f"/auth/admin/clients/{non_existent_id}", 
            headers={"Authorization": "Bearer faketoken"}
        )
        
        # 7. Verify not found response
        assert response_not_found.status_code == status.HTTP_404_NOT_FOUND
    
    finally:
        # Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]
