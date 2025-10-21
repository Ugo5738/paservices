"""
Super ID router for generating and recording unique identifiers.
"""

from typing import Callable
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import jwt
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..crud.super_id_crud import create_and_store_super_id
from ..db import get_db
from ..dependencies import validate_token
from ..models.generated_super_id import GeneratedSuperID

# Corrected imports from the new schema structure
from ..schemas.auth_schema import TokenData
from ..schemas.super_id_schema import SuperIdRequest, SuperIDResponse
from ..utils.logging_config import logger

router = APIRouter(
    # dependencies=[Depends(validate_token)]
)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


# Create a conditional limiter for testing
def conditional_limiter(limit_value: str) -> Callable:
    """Apply rate limiting only if not in test mode"""

    def decorator(func):
        # Skip rate limiting in test mode
        if settings.is_testing():
            return func
        else:
            return limiter.limit(limit_value)(func)

    return decorator


def _redact_sensitive(data):
    SENSITIVE_KEYS = {
        "password",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "secret",
        "api_key",
    }
    if isinstance(data, dict):
        return {
            k: ("<redacted>" if k.lower() in SENSITIVE_KEYS else _redact_sensitive(v))
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_redact_sensitive(v) for v in data]
    return data


def _extract_actor_from_request(request: Request):
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return {"sub": None, "service": None}
    token = auth.split(" ", 1)[1].strip()
    try:
        claims = jwt.decode(token, options={"verify_signature": False})
        return {
            "sub": claims.get("sub"),
            "service": claims.get("service")
            or claims.get("client_id")
            or claims.get("azp"),
        }
    except Exception:
        return {"sub": None, "service": None}


@router.post(
    "",
    response_model=SuperIDResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate and Record Super ID (REST API)",
    description="Generates one UUID and records them. Authenticated via M2M JWT.",
)
# Temporarily disable rate limiter for troubleshooting
# @conditional_limiter(settings.rate_limit_requests_per_minute)
async def create_super_ids_api(
    request_body: SuperIdRequest,
    request: Request,
    token_data: TokenData = Depends(validate_token),
    db: AsyncSession = Depends(get_db),
) -> SuperIDResponse:
    """
    Handles HTTP requests to generate Super IDs.
    1. Validates M2M JWT.
    2. Calls the CRUD layer to perform the database operation.
    3. Commits the transaction.
    4. Formats the HTTP response.
    """
    actor = _extract_actor_from_request(request)
    logger.info(
        "Inbound request: create super_id(s)",
        extra={
            "request": {
                "method": request.method,
                "path": request.url.path,
                "client_host": (request.client.host if request.client else None),
                "actor": actor,
            },
            "body_excerpt": _redact_sensitive(request_body.model_dump()),
        },
    )

    # token_data: TokenData = request.state.token_data

    # Enforce required permission for all authenticated callers.
    if "super_id:generate" not in token_data.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required permission: super_id:generate",
        )

    try:
        record = await create_and_store_super_id(
            db=db,
            user_id=token_data.client_id,
            metadata=request_body.metadata,
        )

        # The get_db dependency will handle the commit upon successful return.

        logger.info(
            f"FastAPI router successfully created {record} super_id for client {token_data.client_id}"
        )
        return SuperIDResponse.model_validate(record)

    except Exception as e:
        logger.error(
            f"Error in FastAPI router while creating super_id: {e}", exc_info=True
        )
        # The get_db dependency will handle the rollback.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate or record super_id due to a server error.",
        )
