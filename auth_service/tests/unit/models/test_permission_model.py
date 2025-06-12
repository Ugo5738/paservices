import uuid

import pytest

from auth_service.models.permission import Permission


def test_permission_model_instantiation():
    """Test basic instantiation and attribute assignment for Permission model."""
    permission_id_val = uuid.uuid4()
    name_val = "users:create"
    description_val = "Permission to create users"

    permission = Permission(
        id=permission_id_val, name=name_val, description=description_val
    )

    assert permission.id == permission_id_val
    assert permission.name == name_val
    assert permission.description == description_val

    expected_repr = f"<Permission(id='{str(permission_id_val)}', name='{name_val}')>"
    assert repr(permission) == expected_repr

    assert hasattr(permission, "created_at")
    assert hasattr(permission, "updated_at")
