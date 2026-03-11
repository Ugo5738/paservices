"""
Security utilities for Data Capture Service.
"""

import time
from typing import Any, Dict, Optional

import httpx
import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwk, jwt as jose_jwt
from jose.exceptions import JWTError

from data_capture_service.config import settings
from data_capture_service.utils.logging_config import logger

security = HTTPBearer(auto_error=False)

_JWKS_CACHE: Dict[str, Any] | None = None
_JWKS_CACHE_EXPIRY: float = 0.0


def _auth_challenge_headers() -> Dict[str, str]:
    return {"WWW-Authenticate": "Bearer"}


def _resolve_jwks_url() -> str:
    if settings.AUTH_SERVICE_JWKS_URL:
        return settings.AUTH_SERVICE_JWKS_URL.rstrip("/")
    base = settings.AUTH_SERVICE_URL.rstrip("/")
    if not base.endswith("/auth"):
        base = f"{base}/auth"
    return f"{base}/.well-known/jwks.json"


async def _fetch_jwks() -> Dict[str, Any]:
    global _JWKS_CACHE, _JWKS_CACHE_EXPIRY
    now = time.time()
    if _JWKS_CACHE and now < _JWKS_CACHE_EXPIRY:
        return _JWKS_CACHE

    url = _resolve_jwks_url()
    logger.debug(f"Fetching JWKS from Auth Service: {url}")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            _JWKS_CACHE = resp.json()
            _JWKS_CACHE_EXPIRY = now + 300
            return _JWKS_CACHE
    except Exception as exc:
        logger.error(f"Failed to fetch JWKS: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to validate authentication token (JWKS fetch failed).",
            headers=_auth_challenge_headers(),
        )


def _find_jwk(jwks: Dict[str, Any], kid: Optional[str]) -> Dict[str, Any]:
    keys = jwks.get("keys") or []
    for key in keys:
        if key.get("kid") == kid:
            return key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token: unknown key identifier.",
        headers=_auth_challenge_headers(),
    )


def _build_public_key_from_jwk(jwk_dict: Dict[str, Any]):
    try:
        return jwk.construct(jwk_dict)
    except Exception as exc:
        logger.error(f"Failed to construct public key from JWK: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error while validating authentication token.",
            headers=_auth_challenge_headers(),
        )


async def _decode_rs_token(token: str, kid: Optional[str]) -> Dict[str, Any]:
    jwks = await _fetch_jwks()
    key_dict = _find_jwk(jwks, kid)
    public_key = _build_public_key_from_jwk(key_dict)
    try:
        return jose_jwt.decode(
            token,
            key=public_key,
            algorithms=[settings.AUTH_SERVICE_JWT_ALGORITHM],
            audience=settings.M2M_JWT_AUDIENCE,
            issuer=settings.AUTH_SERVICE_ISSUER,
        )
    except JWTError as exc:
        logger.warning(f"RS token validation failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers=_auth_challenge_headers(),
        )


def _decode_hs_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.M2M_JWT_SECRET_KEY,
            algorithms=["HS256"],
            audience=settings.M2M_JWT_AUDIENCE,
            options={"verify_signature": True, "verify_aud": True},
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token signature has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers=_auth_challenge_headers(),
        )
    except jwt.InvalidTokenError as exc:
        logger.warning(f"HS token validation failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers=_auth_challenge_headers(),
        )


async def _decode_token(token: str) -> Dict[str, Any]:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        logger.warning(f"Invalid token header: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token header.",
            headers=_auth_challenge_headers(),
        )

    alg = header.get("alg")
    kid = header.get("kid")

    if alg == "HS256":
        return _decode_hs_token(token)

    if alg == settings.AUTH_SERVICE_JWT_ALGORITHM:
        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing key identifier.",
                headers=_auth_challenge_headers(),
            )
        return await _decode_rs_token(token, kid)

    logger.warning(f"Unsupported token algorithm received: {alg}")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token: unsupported algorithm.",
        headers=_auth_challenge_headers(),
    )


async def validate_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Dict[str, Any]:
    """
    Validate JWT token from Authorization header.
    """
    if not credentials:
        logger.warning("Missing authentication token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers=_auth_challenge_headers(),
        )

    token = credentials.credentials
    payload = await _decode_token(token)

    exp = payload.get("exp")
    if exp and exp < time.time():
        logger.warning(f"Token has expired: {payload.get('sub', 'unknown')}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers=_auth_challenge_headers(),
        )

    logger.debug(f"Successfully validated token for: {payload.get('sub', 'unknown')}")
    return payload


async def get_current_service(
    token_data: Dict[str, Any] = Depends(validate_token),
) -> str:
    """
    Get the service name from the authenticated token.
    """
    service = token_data.get("service") or token_data.get("client_id")
    if not service:
        logger.warning("Invalid token claims: service missing")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims: service missing",
            headers=_auth_challenge_headers(),
        )

    logger.debug(f"Authenticated service: {service}")
    return service


async def requires_scope(
    required_scope: str, token_data: Dict[str, Any] = Depends(validate_token)
) -> bool:
    """
    Check if token has the required scope.
    """
    scopes: list[str] = []
    scopes_value = token_data.get("scope")
    if isinstance(scopes_value, str):
        scopes.extend(scopes_value.split())

    permissions = token_data.get("permissions")
    if isinstance(permissions, list):
        scopes.extend(str(p) for p in permissions)

    if required_scope not in scopes:
        logger.warning(f"Token missing required scope: {required_scope}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions: required scope '{required_scope}' not granted",
        )

    return True
