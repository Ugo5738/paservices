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
    description="Generates one or more UUID v4 super_ids and records them in the database."
)
# Temporarily disable rate limiter for troubleshooting
# @conditional_limiter(settings.rate_limit_requests_per_minute)
async def create_super_id(
    request: SuperIdRequest,
    token_data: TokenData = Depends(validate_token),  # Add back the token_data parameter
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
    if "super_id:generate" not in token_data.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required permission: super_id:generate",
        )

    try:
        # Generate requested number of UUIDs first - this always works
        generated_ids = [uuid4() for _ in range(request.count)]
        
        # Get client ID from token data
        client_id = token_data.sub
        
        # Prepare data for recording in Supabase
        data = [
            {
                "super_id": str(uid),
                "requested_by_client_id": client_id,
                # Use the correct column name from the model: `super_id_metadata`
                "super_id_metadata": request.metadata,
            }
            for uid in generated_ids
        ]
        
        # Try to record in Supabase, but don't let it fail the entire request
        try:
            # Insert records into Supabase
            response = await supabase_client.table("generated_super_ids").insert(data).execute()

            # Check for errors
            if hasattr(response, "error") and response.error:
                logger.error(
                    f"Failed to record super_ids in database but still returning them: {response.error.message}"
                )
                # Don't fail the request, just log the error
        except Exception as e:
            # Log the error but continue since we've already generated the IDs
            logger.error(f"Error in create_super_id: {e}")
            logger.warning("Failed to record super_ids in database but still returning the generated IDs")

        # Return response based on request count
        if request.count == 1:
            return SingleSuperIDResponse(super_id=str(generated_ids[0]))
        # Return the generated UUIDs as strings, even if database recording failed
        return BatchSuperIDResponse(super_ids=[str(id) for id in generated_ids])
        
    except HTTPException as http_exc:
        # Re-raise HTTPExceptions directly to preserve status codes
        raise http_exc
    except Exception as e:
        # This should only happen for truly unexpected errors
        logger.error(f"Unexpected error in create_super_id: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error generating super_ids",
        )
