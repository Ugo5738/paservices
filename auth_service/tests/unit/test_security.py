# tests/unit/test_security.py
import time
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt  # For crafting specific test tokens

from auth_service.config import settings
from auth_service.security import (
    create_m2m_access_token,
    decode_m2m_access_token,
    hash_secret,
    verify_client_secret, # This was correctly changed
)


def test_hash_secret_generates_valid_hash():
    """Test that hash_secret generates a non-empty string hash."""
    secret = "mytestsecret"
    hashed = hash_secret(secret)
    assert hashed is not None
    assert isinstance(hashed, str)
    assert len(hashed) > 0
    assert secret != hashed


def test_verify_secret_correct_password():
    """Test that verify_secret returns True for a correct password."""
    plain_secret = "mytestsecret"
    hashed_secret = hash_secret(plain_secret)
    assert verify_client_secret(plain_secret, hashed_secret) is True # Changed


def test_verify_secret_incorrect_password():
    """Test that verify_secret returns False for an incorrect password."""
    plain_secret = "mytestsecret"
    incorrect_secret = "wrongsecret"
    hashed_secret = hash_secret(plain_secret)
    assert verify_client_secret(incorrect_secret, hashed_secret) is False # Changed


def test_verify_secret_with_different_hashes():
    """Test that verify_secret works correctly even if hashes are different for the same password."""
    # bcrypt generates a different salt each time, so two hashes of the same password will be different
    secret = "samesupersecret"
    hash1 = hash_secret(secret)
    hash2 = hash_secret(secret)
    assert hash1 != hash2  # Hashes should be different due to different salts
    assert verify_client_secret(secret, hash1) is True # This was correctly changed
    assert verify_client_secret(secret, hash2) is True # This was correctly changed


def test_verify_secret_empty_password():
    """Test verify_secret with an empty password."""
    plain_secret = ""
    hashed_secret = hash_secret(plain_secret)
    assert verify_client_secret(plain_secret, hashed_secret) is True # Changed


def test_verify_secret_empty_password_incorrect():
    """Test verify_secret with an empty password and incorrect attempt."""
    plain_secret = ""
    incorrect_secret = "notempty"
    hashed_secret = hash_secret(plain_secret)
    assert verify_client_secret(incorrect_secret, hashed_secret) is False # Changed


# --- M2M JWT Tests ---

TEST_CLIENT_ID = "test_client_123"
TEST_ROLES = ["service_role", "data_processor"]
TEST_PERMISSIONS = ["read:data", "write:logs"]


def test_create_and_decode_m2m_access_token_success():
    """Test successful creation and decoding of an M2M access token."""
    token = create_m2m_access_token(
        client_id=TEST_CLIENT_ID, roles=TEST_ROLES, permissions=TEST_PERMISSIONS
    )
    assert token is not None
    assert isinstance(token, str)

    payload = decode_m2m_access_token(token)
    assert payload is not None
    assert payload["sub"] == TEST_CLIENT_ID
    assert payload["roles"] == TEST_ROLES
    assert payload["permissions"] == TEST_PERMISSIONS
    assert payload["iss"] == settings.m2m_jwt_issuer
    assert payload["aud"] == settings.m2m_jwt_audience
    assert payload["token_type"] == "m2m_access"
    assert "exp" in payload
    assert "iat" in payload
    assert payload["exp"] > payload["iat"]


def test_decode_m2m_access_token_expired():
    """Test decoding an expired M2M access token."""
    token = create_m2m_access_token(
        client_id=TEST_CLIENT_ID,
        roles=TEST_ROLES,
        permissions=TEST_PERMISSIONS,
        expires_delta=timedelta(seconds=-1),  # Token is already expired
    )
    payload = decode_m2m_access_token(token)
    assert payload is None


def test_decode_m2m_access_token_invalid_signature():
    """Test decoding an M2M access token with an invalid signature."""
    token = create_m2m_access_token(
        client_id=TEST_CLIENT_ID, roles=TEST_ROLES, permissions=TEST_PERMISSIONS
    )
    parts = token.split(".")
    if len(parts) == 3:
        # Tamper with the signature part
        tampered_signature = list(parts[2])
        original_char = tampered_signature[0]
        tampered_signature[0] = (
            chr(ord(original_char) + 1)
            if ord(original_char) < 255
            else chr(ord(original_char) - 1)
        )
        tampered_token = f"{parts[0]}.{parts[1]}.{''.join(tampered_signature)}"
        payload = decode_m2m_access_token(tampered_token)
        assert payload is None
    else:
        pytest.skip("Token format not as expected for tampering")


def test_decode_m2m_access_token_wrong_issuer():
    """Test decoding an M2M access token with a wrong issuer."""
    claims_wrong_issuer = {
        "sub": TEST_CLIENT_ID,
        "exp": datetime.now(timezone.utc)
        + timedelta(minutes=settings.m2m_jwt_access_token_expire_minutes),
        "iat": datetime.now(timezone.utc),
        "iss": "wrong_issuer",
        "aud": settings.m2m_jwt_audience,
        "roles": TEST_ROLES,
        "permissions": TEST_PERMISSIONS,
        "token_type": "m2m_access",
    }
    token_wrong_issuer = jwt.encode(
        claims_wrong_issuer,
        settings.m2m_jwt_secret_key,
        algorithm=settings.m2m_jwt_algorithm,
    )
    payload = decode_m2m_access_token(token_wrong_issuer)
    assert payload is None


def test_decode_m2m_access_token_wrong_audience():
    """Test decoding an M2M access token with a wrong audience."""
    claims_wrong_audience = {
        "sub": TEST_CLIENT_ID,
        "exp": datetime.now(timezone.utc)
        + timedelta(minutes=settings.m2m_jwt_access_token_expire_minutes),
        "iat": datetime.now(timezone.utc),
        "iss": settings.m2m_jwt_issuer,
        "aud": "wrong_audience",
        "roles": TEST_ROLES,
        "permissions": TEST_PERMISSIONS,
        "token_type": "m2m_access",
    }
    token_wrong_audience = jwt.encode(
        claims_wrong_audience,
        settings.m2m_jwt_secret_key,
        algorithm=settings.m2m_jwt_algorithm,
    )
    payload = decode_m2m_access_token(token_wrong_audience)
    assert payload is None


def test_decode_m2m_access_token_not_m2m_type():
    """Test decoding a token that is not of type 'm2m_access'."""
    claims_wrong_type = {
        "sub": TEST_CLIENT_ID,
        "exp": datetime.now(timezone.utc)
        + timedelta(minutes=settings.m2m_jwt_access_token_expire_minutes),
        "iat": datetime.now(timezone.utc),
        "iss": settings.m2m_jwt_issuer,
        "aud": settings.m2m_jwt_audience,
        "roles": TEST_ROLES,
        "permissions": TEST_PERMISSIONS,
        "token_type": "user_access_token",  # Incorrect type
    }
    token_wrong_type = jwt.encode(
        claims_wrong_type,
        settings.m2m_jwt_secret_key,
        algorithm=settings.m2m_jwt_algorithm,
    )
    payload = decode_m2m_access_token(token_wrong_type)
    assert payload is None


def test_decode_m2m_access_token_malformed():
    """Test decoding a malformed M2M access token."""
    payload = decode_m2m_access_token("this.is.not.a.valid.token")
    assert payload is None
    payload_2 = decode_m2m_access_token("justastringwithoutperiods")
    assert payload_2 is None
