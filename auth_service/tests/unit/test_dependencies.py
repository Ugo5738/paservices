# tests/unit/test_dependencies.py
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, status
from gotrue.types import (
    User as SupabaseUser,  # Aligns with get_current_supabase_user return type
)

from auth_service.dependencies import get_current_supabase_user, require_admin_user


# Mock SupabaseUser data for testing
@pytest.fixture
def mock_admin_user() -> SupabaseUser:
    return SupabaseUser(
        id="user-admin-id",
        email="admin@example.com",
        aud="authenticated",
        role="authenticated",  # Supabase 'role' field, not custom roles
        user_metadata={"roles": ["admin", "editor"]},
        app_metadata={},
        identities=[],
        created_at="2023-01-01T00:00:00Z",
        updated_at="2023-01-01T00:00:00Z",
    )


@pytest.fixture
def mock_non_admin_user() -> SupabaseUser:
    return SupabaseUser(
        id="user-non-admin-id",
        email="user@example.com",
        aud="authenticated",
        role="authenticated",
        user_metadata={"roles": ["editor"]},
        app_metadata={},
        identities=[],
        created_at="2023-01-01T00:00:00Z",
        updated_at="2023-01-01T00:00:00Z",
    )


@pytest.fixture
def mock_user_no_roles() -> SupabaseUser:
    return SupabaseUser(
        id="user-no-roles-id",
        email="noroles@example.com",
        aud="authenticated",
        role="authenticated",
        user_metadata={},
        app_metadata={},
        identities=[],
        created_at="2023-01-01T00:00:00Z",
        updated_at="2023-01-01T00:00:00Z",
    )


@pytest.fixture
def mock_user_empty_roles_list() -> SupabaseUser:
    return SupabaseUser(
        id="user-empty-roles-id",
        email="emptyroles@example.com",
        aud="authenticated",
        role="authenticated",
        user_metadata={"roles": []},
        app_metadata={},
        identities=[],
        created_at="2023-01-01T00:00:00Z",
        updated_at="2023-01-01T00:00:00Z",
    )


@pytest.mark.asyncio
async def test_require_admin_user_is_admin(mock_admin_user: SupabaseUser):
    """Test that an admin user passes the dependency check."""
    # Mock the get_current_supabase_user dependency to return our admin user
    mock_dependency = AsyncMock(return_value=mock_admin_user)

    # Simulate how FastAPI would resolve the dependency
    # We directly call our dependency function with the mocked user
    # In a real FastAPI app, `Depends` handles this.
    # For unit testing the logic of `require_admin_user` itself, we can call it.
    # We need to ensure that the `get_current_supabase_user` it depends on is mocked.
    # This requires a bit of patching if we want to test `require_admin_user` as a black box.

    # Let's assume `require_admin_user` is called with `current_user` already resolved.
    # This is simpler for testing the logic within `require_admin_user`.
    try:
        result_user = await require_admin_user(current_user=mock_admin_user)
        assert result_user == mock_admin_user
    except HTTPException:
        pytest.fail(
            "require_admin_user raised HTTPException unexpectedly for admin user"
        )


@pytest.mark.asyncio
async def test_require_admin_user_not_admin(mock_non_admin_user: SupabaseUser):
    """Test that a non-admin user raises HTTPException."""
    with pytest.raises(HTTPException) as exc_info:
        await require_admin_user(current_user=mock_non_admin_user)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == "User does not have admin privileges"


@pytest.mark.asyncio
async def test_require_admin_user_no_roles_metadata(mock_user_no_roles: SupabaseUser):
    """Test user with no 'roles' key in user_metadata raises HTTPException."""
    with pytest.raises(HTTPException) as exc_info:
        await require_admin_user(current_user=mock_user_no_roles)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == "User does not have admin privileges"


@pytest.mark.asyncio
async def test_require_admin_user_empty_roles_list(
    mock_user_empty_roles_list: SupabaseUser,
):
    """Test user with an empty 'roles' list in user_metadata raises HTTPException."""
    with pytest.raises(HTTPException) as exc_info:
        await require_admin_user(current_user=mock_user_empty_roles_list)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == "User does not have admin privileges"


# Example of how you might test a route using this dependency (conceptual)
# This would typically be an integration test, but shows how the dependency is mocked.
# from fastapi import FastAPI
# from fastapi.testclient import TestClient

# app_test = FastAPI()

# @app_test.get("/admin-only")
# async def admin_only_route(user: SupabaseUser = Depends(require_admin_user)):
#     return {"message": f"Welcome admin {user.email}"}

# def test_admin_route_with_admin_user(mock_admin_user):
#     app_test.dependency_overrides[get_current_supabase_user] = lambda: mock_admin_user
#     client = TestClient(app_test)
#     response = client.get("/admin-only")
#     assert response.status_code == 200
#     assert response.json() == {"message": f"Welcome admin {mock_admin_user.email}"}
#     app_test.dependency_overrides = {} # Clear overrides

# def test_admin_route_with_non_admin_user(mock_non_admin_user):
#     app_test.dependency_overrides[get_current_supabase_user] = lambda: mock_non_admin_user
#     client = TestClient(app_test)
#     response = client.get("/admin-only")
#     assert response.status_code == 403
#     app_test.dependency_overrides = {} # Clear overrides
