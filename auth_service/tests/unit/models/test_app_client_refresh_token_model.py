import uuid
from datetime import datetime, timezone

import pytest

from auth_service.models.app_client_refresh_token import AppClientRefreshToken


def test_app_client_refresh_token_model_instantiation():
    """Test basic instantiation and attribute assignment for AppClientRefreshToken model."""
    token_id_val = uuid.uuid4()
    app_client_id_val = uuid.uuid4()
    token_hash_val = "hashed_refresh_token"
    expires_at_val = datetime.now(timezone.utc)
    revoked_at_val = None  # Initially not revoked

    refresh_token = AppClientRefreshToken(
        id=token_id_val,
        app_client_id=app_client_id_val,
        token_hash=token_hash_val,
        expires_at=expires_at_val,
        revoked_at=revoked_at_val,
    )

    assert refresh_token.id == token_id_val
    assert refresh_token.app_client_id == app_client_id_val
    assert refresh_token.token_hash == token_hash_val
    assert refresh_token.expires_at == expires_at_val
    assert refresh_token.revoked_at == revoked_at_val

    expected_repr = f"<AppClientRefreshToken(id='{str(token_id_val)}', app_client_id='{str(app_client_id_val)}', revoked='{False}')>"
    assert repr(refresh_token) == expected_repr

    assert hasattr(refresh_token, "created_at")

    # Test with revoked_at set
    revoked_time = datetime.now(timezone.utc)
    refresh_token_revoked = AppClientRefreshToken(
        id=uuid.uuid4(),
        app_client_id=app_client_id_val,
        token_hash="another_hash",
        expires_at=expires_at_val,
        revoked_at=revoked_time,
    )
    expected_repr_revoked = f"<AppClientRefreshToken(id='{str(refresh_token_revoked.id)}', app_client_id='{str(app_client_id_val)}', revoked='{True}')>"
    assert repr(refresh_token_revoked) == expected_repr_revoked
