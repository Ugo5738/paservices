"""
Router for property data operations, including fetching from Rightmove API and storing in database.
"""

import asyncio
import uuid
from typing import Dict, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Security,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_rightmove_service.clients.rightmove_api_client import (
    rightmove_api_client,
)
from data_capture_rightmove_service.clients.super_id_service_client import (
    super_id_service_client,
)
from data_capture_rightmove_service.crud.properties_details import (
    get_all_property_ids,
    get_property_details_by_id,
    store_properties_details,
)
from data_capture_rightmove_service.crud.property_details import (
    get_all_property_sale_ids,
    get_property_sale_details_by_id,
    store_property_details,
)
from data_capture_rightmove_service.db import get_db
from data_capture_rightmove_service.schemas.common import MessageResponse
from data_capture_rightmove_service.schemas.property_data import (
    FetchBatchRequest,
    FetchBatchResponse,
    FetchPropertyDetailsRequest,
    FetchPropertyResponse,
    PropertyDetailsStorageResponse,
    PropertySearchRequest,
)
from data_capture_rightmove_service.utils.logging_config import logger
from data_capture_rightmove_service.utils.security import requires_scope, validate_token
from data_capture_rightmove_service.utils.url_parsing import (
    extract_rightmove_property_id,
    is_valid_rightmove_url,
)

router = APIRouter(prefix="/properties", tags=["Properties"])


class PropertyUrlResponse(BaseModel):
    """Response for property URL validation and extraction"""

    url: str = Field(..., description="The URL that was checked")
    valid: bool = Field(..., description="Whether the URL is valid")
    property_id: Optional[int] = Field(
        None, description="Extracted property ID if valid"
    )
    message: str = Field(..., description="Message describing the result")


class CombinedPropertyResponseItem(BaseModel):
    """Response item for a single API call in the combined fetch endpoint"""

    api_endpoint: str = Field(..., description="The API endpoint that was called")
    property_id: int = Field(..., description="The property ID")
    super_id: uuid.UUID = Field(..., description="Super ID for tracking purposes")
    stored: bool = Field(..., description="Whether the data was stored successfully")
    message: str = Field(..., description="Success or error message")


class CombinedPropertyResponse(BaseModel):
    """Response for the combined fetch endpoint"""

    property_id: int = Field(..., description="The property ID")
    property_url: Optional[str] = Field(
        None, description="The property URL if provided"
    )
    results: List[CombinedPropertyResponseItem] = Field(
        ..., description="Results from each API call"
    )


@router.post("/fetch/combined", response_model=CombinedPropertyResponse)
async def fetch_combined_property_data(
    request: FetchPropertyDetailsRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> CombinedPropertyResponse:
    """
    Fetch property data from BOTH Rightmove API endpoints (properties/details and property-for-sale)
    and store ALL data in the database.

    Either property_id or property_url must be provided.
    If property_url is provided, the property_id will be extracted from it.

    This endpoint handles both API calls in a single request and ensures all data is stored.
    """
    try:
        # Extract property ID if URL is provided
        property_id = request.property_id
        property_url = request.property_url

        if not property_id and property_url:
            property_id = extract_rightmove_property_id(property_url)
            if not property_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to extract property ID from URL: {property_url}",
                )
        elif not property_id:
            raise HTTPException(
                status_code=400,
                detail="Either property_id or property_url must be provided",
            )

        # Results container
        results = []

        # 1. Fetch and store properties/details data
        try:
            # Use provided super_id or create a new one for properties/details
            super_id_details = request.super_id
            if not super_id_details:
                description = (
                    request.description
                    or f"Rightmove properties/details fetch for property ID: {property_id}"
                )
                super_id_details = await super_id_service_client.create_super_id(
                    description=description
                )

            # Fetch from Rightmove API - properties/details endpoint
            property_details_data = await rightmove_api_client.get_property_details(
                str(property_id)
            )

            if property_details_data:
                # Store in database - ensure ALL data is stored
                success, message = await store_properties_details(
                    db, property_details_data, super_id_details
                )

                # Add to results
                results.append(
                    CombinedPropertyResponseItem(
                        api_endpoint="properties/details",
                        property_id=property_id,
                        super_id=super_id_details,
                        stored=success,
                        message=message,
                    )
                )
            else:
                results.append(
                    CombinedPropertyResponseItem(
                        api_endpoint="properties/details",
                        property_id=property_id,
                        super_id=super_id_details,
                        stored=False,
                        message=f"No data returned from properties/details endpoint for ID: {property_id}",
                    )
                )
        except Exception as e:
            logger.error(f"Error in properties/details fetch: {str(e)}")
            if super_id_details:
                results.append(
                    CombinedPropertyResponseItem(
                        api_endpoint="properties/details",
                        property_id=property_id,
                        super_id=super_id_details,
                        stored=False,
                        message=f"Error: {str(e)}",
                    )
                )

        # 2. Fetch and store property-for-sale/detail data
        try:
            # Always create a new super_id for the second API call to ensure proper tracking
            description = (
                request.description
                or f"Rightmove property-for-sale fetch for property ID: {property_id}"
            )
            super_id_sale = await super_id_service_client.create_super_id(
                description=description
            )

            # Fetch from Rightmove API - property-for-sale endpoint
            property_sale_data = (
                await rightmove_api_client.get_property_for_sale_details(
                    str(property_id)
                )
            )

            if property_sale_data:
                # Store in database - ensure ALL data is stored
                success, message = await store_property_details(
                    db, property_sale_data, super_id_sale
                )

                # Add to results
                results.append(
                    CombinedPropertyResponseItem(
                        api_endpoint="property-for-sale/detail",
                        property_id=property_id,
                        super_id=super_id_sale,
                        stored=success,
                        message=message,
                    )
                )
            else:
                results.append(
                    CombinedPropertyResponseItem(
                        api_endpoint="property-for-sale/detail",
                        property_id=property_id,
                        super_id=super_id_sale,
                        stored=False,
                        message=f"No data returned from property-for-sale endpoint for ID: {property_id}",
                    )
                )
        except Exception as e:
            logger.error(f"Error in property-for-sale fetch: {str(e)}")
            if "super_id_sale" in locals():
                results.append(
                    CombinedPropertyResponseItem(
                        api_endpoint="property-for-sale/detail",
                        property_id=property_id,
                        super_id=super_id_sale,
                        stored=False,
                        message=f"Error: {str(e)}",
                    )
                )

        # Return combined results
        return CombinedPropertyResponse(
            property_id=property_id, property_url=property_url, results=results
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in combined property fetch: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch and store combined property data: {str(e)}",
        )


@router.get("/validate-url", response_model=PropertyUrlResponse)
async def validate_property_url(
    url: str = Query(..., description="Rightmove property URL to validate")
):
    """
    Validate a Rightmove property URL and extract the property ID.

    This endpoint is useful for client applications to check if a URL is valid
    and to extract the property ID before submitting the URL for processing.
    """
    try:
        # Check if URL is valid
        if not is_valid_rightmove_url(url):
            return PropertyUrlResponse(
                url=url,
                valid=False,
                property_id=None,
                message="Invalid Rightmove property URL",
            )

        # Extract property ID
        property_id = extract_rightmove_property_id(url)
        if not property_id:
            return PropertyUrlResponse(
                url=url,
                valid=False,
                property_id=None,
                message="Could not extract property ID from URL",
            )

        return PropertyUrlResponse(
            url=url,
            valid=True,
            property_id=property_id,
            message=f"Successfully extracted property ID: {property_id}",
        )
    except Exception as e:
        logger.error(f"Error validating property URL: {str(e)}")
        return PropertyUrlResponse(
            url=url,
            valid=False,
            property_id=None,
            message=f"Error processing URL: {str(e)}",
        )


@router.post("/fetch/details", response_model=PropertyDetailsStorageResponse)
async def fetch_property_details(
    request: FetchPropertyDetailsRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> PropertyDetailsStorageResponse:
    """
    Fetch property details from Rightmove API and store in database.
    Uses the properties/details endpoint.

    Either property_id or property_url must be provided.
    If property_url is provided, the property_id will be extracted from it.
    """
    try:
        # Extract property ID if URL is provided
        property_id = request.property_id
        if not property_id and request.property_url:
            property_id = extract_rightmove_property_id(request.property_url)
            if not property_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to extract property ID from URL: {request.property_url}",
                )
        elif not property_id:
            raise HTTPException(
                status_code=400,
                detail="Either property_id or property_url must be provided",
            )

        # Use provided super_id or create a new one
        super_id = request.super_id
        if not super_id:
            description = (
                request.description
                or f"Rightmove property details fetch for property ID: {property_id}"
            )
            super_id = await super_id_service_client.create_super_id(
                description=description
            )

        # Fetch from Rightmove API
        property_data = await rightmove_api_client.get_property_details(
            str(property_id)
        )

        if not property_data:
            raise HTTPException(
                status_code=404,
                detail=f"Property details not found for ID: {property_id}",
            )

        # Store in database
        success, message = await store_properties_details(db, property_data, super_id)

        return PropertyDetailsStorageResponse(
            property_id=property_id,
            super_id=super_id,
            stored=success,
            message=message,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching property details: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch and store property details: {str(e)}",
        )


@router.post("/fetch/property-for-sale", response_model=PropertyDetailsStorageResponse)
async def fetch_property_for_sale_details(
    request: FetchPropertyDetailsRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> PropertyDetailsStorageResponse:
    """
    Fetch property for sale details from Rightmove API and store in database.
    Uses the property-for-sale/detail endpoint.

    Either property_id or property_url must be provided.
    If property_url is provided, the property_id will be extracted from it.
    """
    try:
        # Extract property ID if URL is provided
        property_id = request.property_id
        if not property_id and request.property_url:
            property_id = extract_rightmove_property_id(request.property_url)
            if not property_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to extract property ID from URL: {request.property_url}",
                )
        elif not property_id:
            raise HTTPException(
                status_code=400,
                detail="Either property_id or property_url must be provided",
            )

        # Use provided super_id or create a new one
        super_id = request.super_id
        if not super_id:
            description = (
                request.description
                or f"Rightmove property for sale fetch for property ID: {property_id}"
            )
            super_id = await super_id_service_client.create_super_id(
                description=description
            )

        # Fetch from Rightmove API
        property_data = await rightmove_api_client.get_property_for_sale_details(
            str(property_id)
        )

        if not property_data:
            raise HTTPException(
                status_code=404,
                detail=f"Property for sale details not found for ID: {property_id}",
            )

        # Store in database
        success, message = await store_property_details(db, property_data, super_id)

        return PropertyDetailsStorageResponse(
            property_id=property_id,
            super_id=super_id,
            stored=success,
            message=message,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching property for sale details: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch and store property for sale details: {str(e)}",
        )


@router.post("/fetch/batch", response_model=FetchBatchResponse)
async def fetch_batch_properties(
    request: FetchBatchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> FetchBatchResponse:
    """
    Fetch multiple properties in a batch operation.
    This endpoint processes property IDs in parallel for faster batch processing.
    """
    if not request.property_ids:
        raise HTTPException(status_code=400, detail="No property IDs provided")

    if len(request.property_ids) > 50:
        raise HTTPException(
            status_code=400, detail="Maximum batch size is 50 properties"
        )

    # Get a batch ID (super_id) for tracking this batch operation
    batch_id = await super_id_service_client.create_super_id(
        description=f"Rightmove batch property fetch ({request.api_type}) for {len(request.property_ids)} properties"
    )

    # Define the processing function based on API type
    if request.api_type == "properties_details":
        process_func = process_property_details
    elif request.api_type == "property_for_sale":
        process_func = process_property_for_sale
    else:
        raise HTTPException(status_code=400, detail="Invalid API type specified")

    # Process properties in parallel
    tasks = []
    for property_id in request.property_ids:
        tasks.append(process_func(property_id, db))

    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    successful = 0
    failed = 0
    property_results = []

    for result in results:
        if isinstance(result, Exception):
            # Handle exception case
            failed += 1
            logger.error(f"Error in batch processing: {str(result)}")
            property_results.append(
                FetchPropertyResponse(
                    property_id=0,  # Unknown property ID
                    super_id=uuid.UUID(int=0),  # Placeholder UUID
                    status="failed",
                    message=f"Error: {str(result)}",
                )
            )
        else:
            # Handle successful case
            property_id, super_id, status, message = result
            if status == "success":
                successful += 1
            else:
                failed += 1

            property_results.append(
                FetchPropertyResponse(
                    property_id=property_id,
                    super_id=super_id,
                    status=status,
                    message=message,
                )
            )

    return FetchBatchResponse(
        batch_id=batch_id,
        total=len(request.property_ids),
        successful=successful,
        failed=failed,
        results=property_results,
    )


async def process_property_details(property_id: int, db: AsyncSession) -> tuple:
    """Process a single property using the properties/details endpoint."""
    try:
        # Get a super_id for tracking this request
        super_id = await super_id_service_client.create_super_id(
            description=f"Rightmove property details fetch for property ID: {property_id}"
        )

        # Fetch from Rightmove API
        property_data = await rightmove_api_client.get_property_details(
            str(property_id)
        )

        if not property_data:
            return (
                property_id,
                super_id,
                "failed",
                f"Property details not found for ID: {property_id}",
            )

        # Store in database
        success, message = await store_properties_details(db, property_data, super_id)

        status = "success" if success else "failed"
        return property_id, super_id, status, message

    except Exception as e:
        logger.error(
            f"Error processing property details for ID {property_id}: {str(e)}"
        )
        return property_id, uuid.UUID(int=0), "failed", f"Error: {str(e)}"


async def process_property_for_sale(property_id: int, db: AsyncSession) -> tuple:
    """Process a single property using the property-for-sale/detail endpoint."""
    try:
        # Get a super_id for tracking this request
        super_id = await super_id_service_client.create_super_id(
            description=f"Rightmove property for sale fetch for property ID: {property_id}"
        )

        # Fetch from Rightmove API
        property_data = await rightmove_api_client.get_property_for_sale_details(
            str(property_id)
        )

        if not property_data:
            return (
                property_id,
                super_id,
                "failed",
                f"Property for sale details not found for ID: {property_id}",
            )

        # Store in database
        success, message = await store_property_details(db, property_data, super_id)

        status = "success" if success else "failed"
        return property_id, super_id, status, message

    except Exception as e:
        logger.error(
            f"Error processing property for sale for ID {property_id}: {str(e)}"
        )
        return property_id, uuid.UUID(int=0), "failed", f"Error: {str(e)}"


@router.get("/details/{property_id}", response_model=Dict)
async def get_property_details(
    property_id: int, db: AsyncSession = Depends(get_db)
) -> Dict:
    """
    Get property details from the database by ID.
    Uses data from the properties/details endpoint.
    """
    property_data = await get_property_details_by_id(db, property_id)
    if not property_data:
        raise HTTPException(
            status_code=404, detail=f"Property details not found for ID: {property_id}"
        )
    return property_data


@router.get("/property-for-sale/{property_id}", response_model=Dict)
async def get_property_for_sale(
    property_id: int, db: AsyncSession = Depends(get_db)
) -> Dict:
    """
    Get property for sale details from the database by ID.
    Uses data from the property-for-sale/detail endpoint.
    """
    property_data = await get_property_sale_details_by_id(db, property_id)
    if not property_data:
        raise HTTPException(
            status_code=404,
            detail=f"Property for sale details not found for ID: {property_id}",
        )
    return property_data


@router.post("/search", response_model=Dict)
async def search_properties(
    search_request: PropertySearchRequest,
    background_tasks: BackgroundTasks,
    store_results: bool = Query(
        False, description="Whether to store search results in the database"
    ),
) -> Dict:
    """
    Search for properties using the Rightmove API.
    Optionally store the results in the database if store_results is True.
    """
    try:
        # Call the Rightmove API search endpoint
        search_results = await rightmove_api_client.search_properties_for_sale(
            location=search_request.location,
            min_price=search_request.min_price,
            max_price=search_request.max_price,
            min_bedrooms=search_request.min_bedrooms,
            max_bedrooms=search_request.max_bedrooms,
            property_type=search_request.property_type,
            radius=search_request.radius,
            page_number=search_request.page_number,
            page_size=search_request.page_size,
        )

        # If store_results is True, store each property in the database
        if store_results and "properties" in search_results:
            # This should be done as a background task to not block the response
            background_tasks.add_task(
                store_search_results, search_results.get("properties", [])
            )

        return search_results

    except Exception as e:
        logger.error(f"Error searching properties: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to search properties: {str(e)}"
        )


async def store_search_results(properties: List[Dict]) -> None:
    """Store search results in the database as a background task."""
    async with AsyncSession(bind=db_engine) as db:
        for property_data in properties:
            try:
                # Get property ID from the data
                property_id = property_data.get("id")
                if not property_id:
                    logger.warning("Property data missing ID, skipping")
                    continue

                # Get a super_id for tracking this property
                super_id = await super_id_service_client.create_super_id(
                    description=f"Rightmove search result for property ID: {property_id}"
                )

                # Store in database - pick the right function based on available data
                if "propertySubType" in property_data:
                    # This looks like the property-for-sale format
                    await store_property_details(db, property_data, super_id)
                else:
                    # Try the properties/details format
                    await store_properties_details(db, property_data, super_id)

            except Exception as e:
                logger.error(f"Error storing search result: {str(e)}")
                # Continue with next property, don't fail the entire batch


@router.get("/ids", response_model=List[int])
async def list_property_ids(
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    api_type: str = Query(
        "properties_details",
        description="API type: 'properties_details' or 'property_for_sale'",
    ),
    db: AsyncSession = Depends(get_db),
) -> List[int]:
    """
    List property IDs stored in the database.
    Supports pagination with limit and offset parameters.
    """
    if api_type == "properties_details":
        return await get_all_property_ids(db, limit, offset)
    elif api_type == "property_for_sale":
        return await get_all_property_sale_ids(db, limit, offset)
    else:
        raise HTTPException(status_code=400, detail="Invalid API type specified")
