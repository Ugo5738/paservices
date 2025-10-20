# super_id_service/src/super_id_service/dependencies.py

import json
from typing import Any, Dict, Optional

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwk, jwt
from jose.exceptions import JWTError

from .config import settings
from .schemas.auth_schema import TokenData
from .utils.logging_config import logger

security = HTTPBearer(auto_error=False)


async def fetch_jwks() -> Dict[str, Any]:
    """
    Fetch the JWKS from the auth service.
    Raises HTTPException on failure.
    """
    url = f"{settings.AUTH_SERVICE_URL.rstrip('/')}/.well-known/jwks.json"
    logger.info(f"Fetching JWKS from: {url}")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            jwks = resp.json()
            logger.debug(f"JWKS response: {jwks}")
            return jwks
    except Exception as e:
        logger.error(f"Error fetching JWKS: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch JWKS from auth service: {e}",
        )


def _find_jwk_for_kid(jwks: Dict[str, Any], kid: str) -> Optional[Dict[str, Any]]:
    keys = jwks.get("keys", []) or []
    for key in keys:
        if key.get("kid") == kid:
            return key
    return None


def _build_public_key_from_jwk(jwk_dict: Dict[str, Any]):
    """
    Construct a public key object from a JWK dict for use with python-jose.
    Supports RSA keys via jwk.construct(...) from jose.
    """
    try:
        public_key = jwk.construct(jwk_dict)
        return public_key
    except Exception as e:
        logger.error(f"Failed to build public key from JWK: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error constructing public key",
        )


async def validate_jwt_and_get_claims(
    authorization_header: Optional[str],
) -> Dict[str, Any]:
    """
    Validates a bearer token via JWKS: signature, issuer, audience, expiry.
    Returns claims dict if valid, else raises HTTPException.
    """
    if not authorization_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={
                "WWW-Authenticate": f'Bearer resource_metadata="{settings.SUPER_ID_SERVICE_RESOURCE_METADATA_URL}"'
            },
        )

    parts = authorization_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={
                "WWW-Authenticate": f'Bearer resource_metadata="{settings.SUPER_ID_SERVICE_RESOURCE_METADATA_URL}"'
            },
        )

    token = parts[1]

    # Get unverified header to extract kid
    try:
        unverified_header = jwt.get_unverified_header(token)
        logger.info(f"🔎 Token header: {unverified_header}")
    except JWTError as e:
        logger.error(f"Invalid JWT header: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT header",
            headers={
                "WWW-Authenticate": f'Bearer resource_metadata="{settings.SUPER_ID_SERVICE_RESOURCE_METADATA_URL}"'
            },
        )

    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing 'kid' header",
            headers={
                "WWW-Authenticate": f'Bearer resource_metadata="{settings.SUPER_ID_SERVICE_RESOURCE_METADATA_URL}"'
            },
        )

    jwks = await fetch_jwks()
    jwk_dict = _find_jwk_for_kid(jwks, kid)
    if not jwk_dict:
        logger.error(f"No matching JWK found for kid: {kid}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to find matching JWK for token 'kid'",
            headers={
                "WWW-Authenticate": f'Bearer resource_metadata="{settings.SUPER_ID_SERVICE_RESOURCE_METADATA_URL}"'
            },
        )

    public_key = _build_public_key_from_jwk(jwk_dict)

    try:
        claims = jwt.decode(
            token,
            key=public_key,
            algorithms=[settings.AUTH_SERVICE_JWT_ALGORITHM],
            audience=settings.AUTH_SERVICE_AUDIENCE,
            issuer=settings.AUTH_SERVICE_ISSUER,
        )
        logger.debug(f"JWT claims: {claims}")
    except JWTError as e:
        logger.error(f"Token validation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {e}",
            headers={
                "WWW-Authenticate": f'Bearer resource_metadata="{settings.SUPER_ID_SERVICE_RESOURCE_METADATA_URL}"'
            },
        )

    # Optional: enforce custom claim checks
    token_type = claims.get("token_type")
    if token_type and token_type != "m2m_access":
        logger.error(f"Invalid token_type: {token_type}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={
                "WWW-Authenticate": f'Bearer resource_metadata="{settings.SUPER_ID_SERVICE_RESOURCE_METADATA_URL}"'
            },
        )

    return claims


async def validate_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[TokenData]:
    """
    Dependency for FastAPI endpoints: provides structured TokenData
    """
    # If no credentials were provided, return None to indicate unauthenticated caller.
    if not credentials:
        return None

    token = credentials.credentials
    auth_header = f"Bearer {token}"

    claims = await validate_jwt_and_get_claims(auth_header)

    # Map claims into your TokenData; ensure schema matches what you generate in auth_service
    token_data = TokenData(
        sub=claims.get("sub"),
        client_id=claims.get("sub"),
        permissions=claims.get("permissions", []),
        roles=claims.get("roles", []),
        iss=claims.get("iss"),
        aud=claims.get("aud", None),
        exp=claims.get("exp"),
        # Optionally include raw_claims for debugging or additional logic
        raw_claims=claims,
    )
    return token_data
