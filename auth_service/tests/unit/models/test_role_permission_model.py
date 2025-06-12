import uuid

import pytest

from auth_service.models.role_permission import RolePermission


def test_role_permission_model_instantiation():
    """Test basic instantiation and attribute assignment for RolePermission model."""
    role_id_val = uuid.uuid4()
    permission_id_val = uuid.uuid4()

    role_permission = RolePermission(
        role_id=role_id_val, permission_id=permission_id_val
    )

    assert role_permission.role_id == role_id_val
    assert role_permission.permission_id == permission_id_val

    expected_repr = f"<RolePermission(role_id='{str(role_id_val)}', permission_id='{str(permission_id_val)}')>"
    assert repr(role_permission) == expected_repr

    assert hasattr(role_permission, "assigned_at")
