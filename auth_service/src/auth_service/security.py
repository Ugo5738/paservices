# src/auth_service/security.py
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import secrets # For generating client secrets
from jose import JWTError, jwt
from passlib.context import CryptContext

from auth_service.config import settings  # Import settings

# It's recommended to create a CryptContext instance once and reuse it.
# Configure it for bcrypt.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_client_secret(n_bytes: int = 32) -> str:
    """
    Generates a cryptographically strong URL-safe text string for client secrets.
    Default length is 32 bytes, resulting in a ~43 character string.
    """
    return secrets.token_urlsafe(n_bytes)


def hash_secret(secret: str) -> str:
    """
    Hashes a secret string using bcrypt.
    """
    return pwd_context.hash(secret)


def verify_client_secret(plain_secret: str, hashed_secret: str) -> bool:
    """
    Verifies a plain secret against a hashed secret.
    Returns True if the secret matches, False otherwise.
    """
    return pwd_context.verify(plain_secret, hashed_secret)


def create_m2m_access_token(
    client_id: str,
    roles: List[str],
    permissions: List[str],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Creates an M2M access token.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.m2m_jwt_access_token_expire_minutes)

    to_encode: Dict[str, Any] = {
        "sub": client_id,
        "exp": expire,
        "iat": now,
        "iss": settings.m2m_jwt_issuer,
        "aud": settings.m2m_jwt_audience,
        "roles": roles,
        "permissions": permissions,
        "token_type": "m2m_access",  # Custom claim to identify token type
    }
    encoded_jwt = jwt.encode(
        to_encode, settings.m2m_jwt_secret_key, algorithm=settings.m2m_jwt_algorithm
    )
    return encoded_jwt


def decode_m2m_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodes an M2M access token.
    Returns the token payload if valid, None otherwise.
    """
    try:
        payload = jwt.decode(
            token,
            settings.m2m_jwt_secret_key,
            algorithms=[settings.m2m_jwt_algorithm],
            audience=settings.m2m_jwt_audience,
            issuer=settings.m2m_jwt_issuer,
            options={
                "verify_signature": True,
                "verify_aud": True,
                "verify_iss": True,
                "verify_exp": True,
            },
        )
        # Ensure it's an M2M token
        if payload.get("token_type") != "m2m_access":
            return None  # Or raise a specific exception
        return payload
    except JWTError:  # Catches various JWT errors (expired, invalid signature, etc.)
        return None
