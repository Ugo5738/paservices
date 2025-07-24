"""
Super ID router for generating and recording unique identifiers.
"""

import os
from functools import wraps
from typing import Callable, Union
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from super_id_service.config import settings
from super_id_service.db import get_db
from super_id_service.dependencies import validate_token
from super_id_service.models.generated_super_id import GeneratedSuperID

# Corrected imports from the new schema structure
from super_id_service.schemas.auth_schema import TokenData
from super_id_service.schemas.super_id_schema import (
    BatchSuperIDResponse,
    SingleSuperIDResponse,
    SuperIdRequest,
)
from super_id_service.utils.logging_config import logger

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


# Create a conditional limiter for testing
def conditional_limiter(limit_value: str) -> Callable:
    """Apply rate limiting only if not in test mode"""

    def decorator(func):
        # Skip rate limiting in test mode
        if os.environ.get("ENVIRONMENT") == "test":
            return func
        else:
            return limiter.limit(limit_value)(func)

    return decorator


router = APIRouter()


@router.post(
    "",
    # Corrected response model name
    response_model=Union[SingleSuperIDResponse, BatchSuperIDResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Generate and record one or more super_ids",
    description="Generates one or more UUID v4 super_ids and records them in the database.",
)
# Temporarily disable rate limiter for troubleshooting
# @conditional_limiter(settings.rate_limit_requests_per_minute)
async def create_super_id(
    request: SuperIdRequest,
    token_data: TokenData = Depends(validate_token),
    db: AsyncSession = Depends(get_db),
) -> Union[SingleSuperIDResponse, BatchSuperIDResponse]:
    """
    Generate and record one or more super_ids (UUID v4).

    Args:
        request: Contains count parameter for number of IDs to generate.
        token_data: Validated JWT data containing client_id and permissions.
        supabase_client: Initialized Supabase client.

    Returns:
        SingleSuperIDResponse: For single ID requests.
        BatchSuperIDResponse: For multiple ID requests.

    Raises:
        HTTPException: If database operations fail or permissions are insufficient.
    """
    if "super_id:generate" not in token_data.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required permission: super_id:generate",
        )

    # Always generate IDs first, as this is a local operation that cannot fail.
    generated_ids = [uuid4() for _ in range(request.count)]
    client_id = token_data.client_id

    # Create a list of SQLAlchemy model instances to be inserted.
    db_records = [
        GeneratedSuperID(
            super_id=uid,
            requested_by_client_id=client_id,
            super_id_metadata=request.metadata,
        )
        for uid in generated_ids
    ]

    try:
        # Use the SQLAlchemy session to add and commit the records.
        # The get_db dependency handles the commit and rollback automatically.
        db.add_all(db_records)
        logger.info(
            f"Successfully recorded {len(db_records)} super_id(s) in the database."
        )
    except Exception as e:
        # The get_db dependency will automatically roll back the transaction.
        logger.error(f"Error recording super_ids to the database: {e}", exc_info=True)
        # We still return the generated IDs as a fallback, per original business logic.
        logger.warning(
            "Failed to record super_ids in database but still returning the generated IDs"
        )

    if request.count == 1:
        return SingleSuperIDResponse(super_id=generated_ids[0])
    else:
        return BatchSuperIDResponse(super_ids=generated_ids)
