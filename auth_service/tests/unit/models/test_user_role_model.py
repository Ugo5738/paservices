import uuid

import pytest

from auth_service.models.user_role import UserRole


def test_user_role_model_instantiation():
    """Test basic instantiation and attribute assignment for UserRole model."""
    user_id_val = uuid.uuid4()
    role_id_val = uuid.uuid4()

    user_role = UserRole(user_id=user_id_val, role_id=role_id_val)

    assert user_role.user_id == user_id_val
    assert user_role.role_id == role_id_val

    expected_repr = (
        f"<UserRole(user_id='{str(user_id_val)}', role_id='{str(role_id_val)}')>"
    )
    assert repr(user_role) == expected_repr

    assert hasattr(user_role, "assigned_at")
