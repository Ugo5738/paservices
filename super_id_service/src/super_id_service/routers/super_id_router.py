"""
Super ID router for generating and recording unique identifiers.
"""
import logging
import os
from typing import Union, Callable
from uuid import uuid4
from functools import wraps

from fastapi import APIRouter, Depends, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from super_id_service.config import settings
from super_id_service.dependencies import get_supabase_client, validate_token
from super_id_service.schemas.super_id import (
    SuperIDRequest as SuperIdRequest,
    SingleSuperIDResponse as SuperIdResponse,
    BatchSuperIDResponse as SuperIdListResponse
)
from super_id_service.schemas.auth import TokenData

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
    response_model=Union[SuperIdResponse, SuperIdListResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Generate and record one or more super_ids",
    description="Generates one or more UUID v4 super_ids and records them in the database.",
)
@conditional_limiter(settings.rate_limit_requests_per_minute)
async def create_super_id(
    request: SuperIdRequest,
    token_data: TokenData = Depends(validate_token),
    supabase_client = Depends(get_supabase_client),
) -> Union[SuperIdResponse, SuperIdListResponse]:
    """
    Generate and record one or more super_ids (UUID v4).
    
    Args:
        request: Contains count parameter for number of IDs to generate
        token_data: Validated JWT data containing client_id and permissions
        supabase_client: Initialized Supabase client
        
    Returns:
        SuperIdResponse: For single ID requests
        SuperIdListResponse: For multiple ID requests
        
    Raises:
        HTTPException: If database operations fail or permissions are insufficient
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
                "metadata": {"iss": token_data.iss} if token_data.iss else None,
            } 
            for uid in generated_ids
        ]
        
        # Insert records into Supabase
        response = await supabase_client.table("generated_super_ids").insert(data).execute()
        
        if response.get("error"):
            logger.error(f"Failed to record super_ids in database: {response.get('error')}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to record generated super_ids",
            )
            
        # Return response based on request count
        if request.count == 1:
            return SuperIdResponse(super_id=generated_ids[0])
        else:
            return SuperIdListResponse(super_ids=generated_ids)
            
    except Exception as e:
        logger.exception(f"Error in create_super_id: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate or record super_id",
        )
