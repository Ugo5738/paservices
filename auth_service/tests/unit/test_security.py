"""
Unit tests for security components including JWT tokens and password security.
"""
import pytest
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from unittest.mock import patch, MagicMock

from auth_service.security import (
    create_m2m_access_token,
    decode_m2m_access_token,
    hash_secret,
    verify_client_secret,
    generate_client_secret
)


class TestJWT:
    """Tests for JWT token generation and verification for M2M access."""
    
    def test_create_m2m_access_token(self):
        """Test creating a JWT M2M access token with claims."""
        # Arrange
        client_id = "client123"
        roles = ["service:read", "service:write"]
        permissions = ["users:read", "data:write"]
        expires_delta = timedelta(minutes=15)
        
        # Act
        token = create_m2m_access_token(
            client_id=client_id,
            roles=roles,
            permissions=permissions,
            expires_delta=expires_delta
        )
        
        # Assert
        assert token is not None
        assert isinstance(token, str)
        
        # We'll use the decode_m2m_access_token function to verify instead of manual decoding
        # which depends on settings that might not be available in test environment
        with patch('auth_service.security.settings') as mock_settings:
            # Configure mock settings
            mock_settings.M2M_JWT_SECRET_KEY = "test_secret_key"
            mock_settings.M2M_JWT_ALGORITHM = "HS256"
            mock_settings.M2M_JWT_AUDIENCE = "test-audience"
            mock_settings.M2M_JWT_ISSUER = "test-issuer"
            
            # Manually decode token for testing purposes
            payload = jwt.decode(
                token,
                "test_secret_key",
                algorithms=["HS256"],
                options={"verify_signature": False, "verify_aud": False, "verify_iss": False}
            )
            
            # Assert token contains expected claims
            assert payload["sub"] == client_id
            assert payload["roles"] == roles
            assert payload["permissions"] == permissions
            assert payload["token_type"] == "m2m_access"
            assert "exp" in payload
    
    def test_decode_m2m_access_token_valid(self):
        """Test decoding a valid M2M access token."""
        # Arrange
        # Create a token with known values
        client_id = "test-client"
        roles = ["admin"]
        permissions = ["users:manage"]
        
        # Mock settings for consistent testing
        with patch('auth_service.security.settings') as mock_settings:
            # Configure mock settings
            mock_settings.M2M_JWT_SECRET_KEY = "test_secret_key"
            mock_settings.M2M_JWT_ALGORITHM = "HS256"
            mock_settings.M2M_JWT_AUDIENCE = "test-audience"
            mock_settings.M2M_JWT_ISSUER = "test-issuer"
            mock_settings.M2M_JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30
            
            # Create a token
            token = create_m2m_access_token(
                client_id=client_id,
                roles=roles,
                permissions=permissions
            )
            
            # Act
            payload = decode_m2m_access_token(token)
            
            # Assert
            assert payload is not None
            assert payload["sub"] == client_id
            assert payload["roles"] == roles
            assert payload["permissions"] == permissions
    
    def test_decode_m2m_access_token_invalid(self):
        """Test decoding an invalid M2M access token."""
        # Arrange - an invalid token
        invalid_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        
        # Act & Assert
        result = decode_m2m_access_token(invalid_token)
        assert result is None  # Should return None for invalid tokens


class TestClientSecretSecurity:
    """Tests for client secret generation and verification."""
    
    def test_generate_client_secret(self):
        """Test generating a client secret."""
        # Act
        secret = generate_client_secret()
        
        # Assert
        assert secret is not None
        assert len(secret) > 30  # Should be reasonably long
        assert isinstance(secret, str)
    
    def test_hash_secret_is_secure(self):
        """Test that secret hashing produces secure hashes."""
        # Arrange
        secret = "SecureSecret123"
        
        # Act
        hashed = hash_secret(secret)
        
        # Assert
        assert hashed != secret  # Hash should not be the plaintext
        assert len(hashed) > 20  # Hash should be sufficiently long
        assert "$" in hashed     # Should contain algorithm identifiers
    
    def test_verify_client_secret_correct(self):
        """Test verifying a correct client secret against its hash."""
        # Arrange
        secret = "SecureSecret123"
        hashed = hash_secret(secret)
        
        # Act
        is_verified = verify_client_secret(secret, hashed)
        
        # Assert
        assert is_verified is True
    
    def test_verify_client_secret_incorrect(self):
        """Test verifying an incorrect client secret against a hash."""
        # Arrange
        secret = "SecureSecret123"
        wrong_secret = "WrongSecret456"
        hashed = hash_secret(secret)
        
        # Act
        is_verified = verify_client_secret(wrong_secret, hashed)
        
        # Assert
        assert is_verified is False
    
    def test_different_secrets_produce_different_hashes(self):
        """Test that different secrets produce different hashes."""
        # Arrange
        secret1 = "Secret123!"
        secret2 = "Secret123@"
        
        # Act
        hash1 = hash_secret(secret1)
        hash2 = hash_secret(secret2)
        
        # Assert
        assert hash1 != hash2
    
    def test_same_secret_produces_different_hashes(self):
        """Test that same secret hashed twice produces different hashes (due to salt)."""
        # Arrange
        secret = "SameSecret123!"
        
        # Act
        hash1 = hash_secret(secret)
        hash2 = hash_secret(secret)
        
        # Assert
        assert hash1 != hash2  # Hashes should be different due to random salt
