# src/auth_service/security.py
import base64
import os
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional

from jose import jwt
from jose.exceptions import JWTError
from passlib.context import CryptContext

from .config import settings

# It's recommended to create a CryptContext instance once and reuse it.
# Configure it for bcrypt.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Construct absolute paths for the key files.
_PRIVATE_KEY_PATH = os.path.join(_BASE_DIR, "keys", "private.pem")
_PUBLIC_KEY_PATH = os.path.join(_BASE_DIR, "keys", "public.pem")


def _resolve_path(custom_path: Optional[str], default: str) -> str:
    if custom_path:
        return custom_path if os.path.isabs(custom_path) else os.path.join(_BASE_DIR, custom_path)
    return default


def _decode_if_base64(value: str) -> bytes:
    try:
        return base64.b64decode(value)
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError("Failed to decode base64 key content") from exc


@lru_cache
def _load_signing_key() -> bytes:
    algorithm = settings.M2M_JWT_ALGORITHM.upper()
    if algorithm.startswith("HS"):
        return settings.M2M_JWT_SECRET_KEY.encode("utf-8")

    if settings.M2M_JWT_PRIVATE_KEY:
        return settings.M2M_JWT_PRIVATE_KEY.encode("utf-8")
    if settings.M2M_JWT_PRIVATE_KEY_B64:
        return _decode_if_base64(settings.M2M_JWT_PRIVATE_KEY_B64)

    key_path = _resolve_path(settings.M2M_JWT_PRIVATE_KEY_PATH, _PRIVATE_KEY_PATH)
    try:
        with open(key_path, "rb") as f:
            return f.read()
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Auth service private key not found at '{key_path}'. "
            "Provide AUTH_SERVICE_M2M_JWT_PRIVATE_KEY(_B64) or a valid AUTH_SERVICE_M2M_JWT_PRIVATE_KEY_PATH."
        ) from exc


@lru_cache
def _load_verification_key() -> bytes:
    algorithm = settings.M2M_JWT_ALGORITHM.upper()
    if algorithm.startswith("HS"):
        return settings.M2M_JWT_SECRET_KEY.encode("utf-8")

    if settings.M2M_JWT_PUBLIC_KEY:
        return settings.M2M_JWT_PUBLIC_KEY.encode("utf-8")
    if settings.M2M_JWT_PUBLIC_KEY_B64:
        return _decode_if_base64(settings.M2M_JWT_PUBLIC_KEY_B64)

    key_path = _resolve_path(settings.M2M_JWT_PUBLIC_KEY_PATH, _PUBLIC_KEY_PATH)
    try:
        with open(key_path, "rb") as f:
            return f.read()
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Auth service public key not found at '{key_path}'. "
            "Provide AUTH_SERVICE_M2M_JWT_PUBLIC_KEY(_B64) or a valid AUTH_SERVICE_M2M_JWT_PUBLIC_KEY_PATH."
        ) from exc


def get_m2m_public_key() -> bytes:
    """
    Return the verification key bytes used for M2M JWT validation / JWKS exposure.
    """
    return _load_verification_key()


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
        expire = now + timedelta(minutes=settings.M2M_JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: Dict[str, Any] = {
        "sub": client_id,
        "exp": expire,
        "iat": now,
        "iss": settings.M2M_JWT_ISSUER,
        "aud": settings.M2M_JWT_AUDIENCE,
        "roles": roles,
        "permissions": permissions,
        "token_type": "m2m_access",  # Custom claim to identify token type
    }

    private_key = _load_signing_key()

    headers = {
        "alg": settings.M2M_JWT_ALGORITHM,
        "kid": settings.M2M_JWT_KID,
        "typ": "JWT",
    }

    encoded_jwt = jwt.encode(
        claims=payload,
        key=private_key,
        algorithm=settings.M2M_JWT_ALGORITHM,
        headers=headers,
    )
    return encoded_jwt


def decode_m2m_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodes an M2M access token.
    Returns the token payload if valid, None otherwise.
    """
    try:
        public_key = _load_verification_key()
        payload = jwt.decode(
            token,
            public_key,
            algorithms=[settings.M2M_JWT_ALGORITHM],
            audience=settings.M2M_JWT_AUDIENCE,
            issuer=settings.M2M_JWT_ISSUER,
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
