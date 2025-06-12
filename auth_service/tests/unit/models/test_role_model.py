import uuid

import pytest

from auth_service.models.role import Role


def test_role_model_instantiation():
    """Test basic instantiation and attribute assignment for Role model."""
    role_id_val = uuid.uuid4()
    name_val = "admin_role"
    description_val = "Administrator Role"

    role = Role(id=role_id_val, name=name_val, description=description_val)

    assert role.id == role_id_val
    assert role.name == name_val
    assert role.description == description_val

    expected_repr = f"<Role(id='{str(role_id_val)}', name='{name_val}')>"
    assert repr(role) == expected_repr

    assert hasattr(role, "created_at")
    assert hasattr(role, "updated_at")
