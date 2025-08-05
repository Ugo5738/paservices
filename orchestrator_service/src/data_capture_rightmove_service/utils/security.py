"""
Security utilities for Data Capture Rightmove Service.
"""

import time
from typing import Dict, Optional

import jwt
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from data_capture_rightmove_service.config import settings
from data_capture_rightmove_service.utils.logging_config import logger

security = HTTPBearer(auto_error=False)


async def validate_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Dict:
    """
    Validate JWT token from Authorization header.

    Args:
        credentials: JWT credentials from Authorization header

    Returns:
        Dict containing token claims

    Raises:
        HTTPException: If token is invalid or expired
    """
    if not credentials:
        logger.warning("Missing authentication token")
        raise HTTPException(
            status_code=401,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        # Validate the token
        payload = jwt.decode(
            token,
            settings.M2M_JWT_SECRET_KEY,
            algorithms=["HS256"],
            audience=settings.M2M_JWT_AUDIENCE,
            options={
                "verify_signature": True,
                "verify_aud": True,
            },  # Ensure verify_aud is True
        )

        # Check if token has expired
        if payload.get("exp") and payload["exp"] < time.time():
            logger.warning(f"Token has expired: {payload.get('sub', 'unknown')}")
            raise HTTPException(
                status_code=401,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.debug(
            f"Successfully validated token for: {payload.get('sub', 'unknown')}"
        )
        return payload

    except jwt.ExpiredSignatureError:
        logger.warning("Token signature has expired")
        raise HTTPException(
            status_code=401,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_service(
    token_data: Dict = Depends(validate_token),
) -> str:
    """
    Get the service name from the authenticated token.

    Args:
        token_data: Validated token data

    Returns:
        Service name from token

    Raises:
        HTTPException: If service is not found in token
    """
    if "service" not in token_data:
        logger.warning("Invalid token claims: service missing")
        raise HTTPException(
            status_code=401, detail="Invalid token claims: service missing"
        )

    service = token_data["service"]
    logger.debug(f"Authenticated service: {service}")
    return service


async def requires_scope(
    required_scope: str, token_data: Dict = Depends(validate_token)
) -> bool:
    """
    Check if token has the required scope.

    Args:
        required_scope: Scope required for access
        token_data: Validated token data

    Returns:
        True if token has required scope

    Raises:
        HTTPException: If token does not have required scope
    """
    if "scope" not in token_data:
        logger.warning("Token missing scope claim")
        raise HTTPException(
            status_code=403, detail="Insufficient permissions: missing scope claim"
        )

    scopes = token_data["scope"].split()

    if required_scope not in scopes:
        logger.warning(f"Token missing required scope: {required_scope}")
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient permissions: required scope '{required_scope}' not granted",
        )

    return True
