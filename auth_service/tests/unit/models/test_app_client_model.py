import uuid

import pytest

from auth_service.models.app_client import AppClient


def test_app_client_model_instantiation():
    """Test basic instantiation and attribute assignment for AppClient model."""
    client_id_val = uuid.uuid4()
    client_name_val = "test_client"
    client_secret_hash_val = "hashed_secret"
    description_val = "A test client"
    is_active_val = True

    app_client = AppClient(
        id=client_id_val,
        client_name=client_name_val,
        client_secret_hash=client_secret_hash_val,
        description=description_val,
        is_active=is_active_val,
    )

    assert app_client.id == client_id_val
    assert app_client.client_name == client_name_val
    assert app_client.client_secret_hash == client_secret_hash_val
    assert app_client.description == description_val
    assert app_client.is_active == is_active_val

    expected_repr = (
        f"<AppClient(id='{str(client_id_val)}', client_name='{client_name_val}')>"
    )
    assert repr(app_client) == expected_repr

    assert hasattr(app_client, "created_at")
    assert hasattr(app_client, "updated_at")
