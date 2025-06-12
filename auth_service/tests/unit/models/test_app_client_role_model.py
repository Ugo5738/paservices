import uuid

import pytest

from auth_service.models.app_client_role import AppClientRole


def test_app_client_role_model_instantiation():
    """Test basic instantiation and attribute assignment for AppClientRole model."""
    app_client_id_val = uuid.uuid4()
    role_id_val = uuid.uuid4()

    app_client_role = AppClientRole(
        app_client_id=app_client_id_val, role_id=role_id_val
    )

    assert app_client_role.app_client_id == app_client_id_val
    assert app_client_role.role_id == role_id_val

    expected_repr = f"<AppClientRole(app_client_id='{str(app_client_id_val)}', role_id='{str(role_id_val)}')>"
    assert repr(app_client_role) == expected_repr

    assert hasattr(app_client_role, "assigned_at")
