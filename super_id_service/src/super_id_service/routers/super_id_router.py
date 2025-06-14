"""
Super ID router for generating and recording unique identifiers.
"""

import logging
import os
from functools import wraps
from typing import Callable, Union
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from super_id_service.config import settings
from super_id_service.dependencies import get_supabase_client, validate_token

# Corrected imports from the new schema structure
from super_id_service.schemas.auth_schema import TokenData
from super_id_service.schemas.super_id_schema import (
    BatchSuperIDResponse,
    SingleSuperIDResponse,
    SuperIdRequest,
)

logger = logging.getLogger(__name__)

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
@conditional_limiter(settings.rate_limit_requests_per_minute)
async def create_super_id(
    request: SuperIdRequest,
    token_data: TokenData = Depends(validate_token),
    supabase_client=Depends(get_supabase_client),
    # Corrected return type hint
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
    # Check required permission
    if "super_id:generate" not in token_data.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required permission: super_id:generate",
        )

    try:
        # Generate requested number of UUIDs
        generated_ids = [uuid4() for _ in range(request.count)]

        # Record the generated IDs in Supabase
        client_id = token_data.sub

        # For each UUID, create a record in the generated_super_ids table
        data = [
            {
                "super_id": str(uid),
                "requested_by_client_id": client_id,
                # Use the correct column name from the model: `super_id_metadata`
                "super_id_metadata": request.metadata,
            }
            for uid in generated_ids
        ]

        # Insert records into Supabase
        response = (
            await supabase_client.table("generated_super_ids").insert(data).execute()
        )

        # The actual response object from supabase-py v2 is different
        # We check for errors by looking at the `error` attribute if it exists
        if hasattr(response, "error") and response.error:
            logger.error(
                f"Failed to record super_ids in database: {response.error.message}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to record generated super_ids",
            )

        # Return response based on request count
        if request.count == 1:
            return SingleSuperIDResponse(super_id=generated_ids[0])
        else:
            return BatchSuperIDResponse(super_ids=generated_ids)

    except HTTPException as http_exc:
        # Re-raise HTTPExceptions directly to preserve status codes
        raise http_exc
    except Exception as e:
        logger.exception(f"Error in create_super_id: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate or record super_id",
        )
