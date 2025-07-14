"""
Router for property data operations, including fetching from Rightmove API and storing in database.
"""

import asyncio
import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_rightmove_service.clients.rightmove_api_client import (
    rightmove_api_client,
)
from data_capture_rightmove_service.clients.super_id_service_client import (
    super_id_service_client,
)
from data_capture_rightmove_service.crud import event_crud
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
from data_capture_rightmove_service.crud.property_search import (
    store_property_search_results,
)
from data_capture_rightmove_service.db import AsyncSessionLocal, get_db
from data_capture_rightmove_service.models.scrape_event import ScrapeEventTypeEnum
from data_capture_rightmove_service.schemas.common import MessageResponse
from data_capture_rightmove_service.schemas.property_data import (
    CombinedPropertyResponse,
    CombinedPropertyResponseItem,
    FetchBatchRequest,
    FetchBatchResponse,
    FetchPropertyDetailsRequest,
    FetchPropertyResponse,
    PropertyDetailsStorageResponse,
    PropertySearchRequest,
    PropertyUrlResponse,
)
from data_capture_rightmove_service.utils.data_completeness import analyze_response
from data_capture_rightmove_service.utils.logging_config import logger
from data_capture_rightmove_service.utils.security import requires_scope, validate_token
from data_capture_rightmove_service.utils.url_parsing import (
    extract_rightmove_property_id,
    is_valid_rightmove_url,
)

router = APIRouter(prefix="/properties", tags=["Properties"])


@router.post("/fetch/combined", response_model=CombinedPropertyResponse)
async def fetch_combined_property_data(
    request: FetchPropertyDetailsRequest,
    db: AsyncSession = Depends(get_db),
) -> CombinedPropertyResponse:
    """
    Combined endpoint to fetch data from multiple Rightmove API endpoints and store in database.

    This endpoint orchestrates calls to two Rightmove API endpoints and handles the storage
    of their responses in the database. It provides a comprehensive response with details
    from both API calls, including success/failure status for each step in the process.

    Args:
        request: Property details request containing URL or ID and optional super_id
        db: Database session from dependency injection

    Returns:
        CombinedPropertyResponse with results from each endpoint

    Raises:
        HTTPException: If the property ID cannot be determined or other critical errors occur
    """
    # Extract and validate the property ID from URL or direct ID input
    try:
        # Try to extract property ID from URL if provided, otherwise use direct property_id
        extracted_id = (
            extract_rightmove_property_id(request.property_url)
            if request.property_url
            else None
        )
        if not extracted_id and not request.property_id:
            raise HTTPException(
                status_code=400,
                detail="Either a valid Rightmove property URL or property ID must be provided",
            )

        property_id = int(extracted_id or request.property_id)
        logger.info(
            f"Processing property ID: {property_id} from URL: {request.property_url}"
        )
    except (ValueError, TypeError) as e:
        logger.error(f"Failed to parse property ID: {str(e)}")
        raise HTTPException(
            status_code=400, detail=f"Invalid property ID format: {str(e)}"
        )

    # Obtain or use provided super_id for tracking this request chain
    try:
        if request.super_id:
            super_id = request.super_id
            logger.info(
                f"Using provided Super ID: {super_id} for property ID: {property_id}"
            )
        # else:
        #     super_id = await super_id_service_client.create_super_id(
        #         description=f"Rightmove data capture for property ID: {property_id}"
        #     )
        #     logger.info(
        #         f"Generated Super ID: {super_id} for property ID: {property_id}"
        #     )
    except HTTPException as e:
        # If super_id service is unavailable, raise the exception to the client
        logger.error(f"Super ID service error: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail=f"Super ID service is required but unavailable: {str(e)}",
        )

    # Log the initial request event
    try:
        await event_crud.log_scrape_event(
            db,
            super_id,
            ScrapeEventTypeEnum.REQUEST_RECEIVED,
            rightmove_property_id=property_id,
            payload=request.model_dump(mode="json"),
        )
    except Exception as e:
        logger.error(f"Failed to log initial request event: {str(e)}")
        # Explicitly roll back transaction to prevent PendingRollbackError
        try:
            await db.rollback()
            logger.info("Rolled back transaction after failed event logging")
        except Exception as rollback_error:
            logger.error(f"Failed to roll back transaction: {str(rollback_error)}")
        # Continue with processing even if logging fails

    results = []

    # Define the endpoints to call and their respective storage functions
    endpoints = {
        "properties/details": (
            rightmove_api_client.get_property_details,
            store_properties_details,
        ),
        "buy/property-for-sale/detail": (
            rightmove_api_client.get_property_for_sale_details,
            store_property_details,
        ),
    }

    for endpoint, (api_call, store_func) in endpoints.items():
        raw_data = None
        stored_successfully = False
        message = ""

        # Step 1: Log API call attempt
        try:
            logger.info(
                f"Calling Rightmove API endpoint: {endpoint} for property ID: {property_id}"
            )
            await event_crud.log_scrape_event(
                db,
                super_id,
                ScrapeEventTypeEnum.API_CALL_ATTEMPT,
                rightmove_property_id=property_id,
                api_endpoint_called=endpoint,
            )
        except Exception as e:
            logger.error(f"Failed to log API call attempt: {str(e)}")
            # Roll back transaction to prevent PendingRollbackError
            try:
                await db.rollback()
                logger.info(
                    f"Rolled back transaction after failed API call attempt logging"
                )
            except Exception as rollback_error:
                logger.error(f"Failed to roll back transaction: {str(rollback_error)}")
            # Continue with API call even if logging fails

        # Step 2: Make API call
        try:
            raw_data = await api_call(str(property_id))

            # Log successful API call
            if raw_data:
                # Analyze the response for data completeness
                item_count, null_count = analyze_response(raw_data)
                logger.info(
                    f"Received data from {endpoint}: {item_count} items, {null_count} null values"
                )

                # Log successful API call
                try:
                    await event_crud.log_scrape_event(
                        db,
                        super_id,
                        ScrapeEventTypeEnum.API_CALL_SUCCESS,
                        rightmove_property_id=property_id,
                        api_endpoint_called=endpoint,
                        http_status_code=200,
                        payload=raw_data,
                        response_item_count=item_count,
                        response_null_item_count=null_count,
                    )
                except Exception as e:
                    logger.error(f"Failed to log API success: {str(e)}")
                    # Roll back transaction to prevent PendingRollbackError
                    try:
                        await db.rollback()
                    except Exception as rollback_error:
                        logger.error(
                            f"Failed to roll back transaction: {str(rollback_error)}"
                        )
                    # Continue with storage even if logging fails
            else:
                message = "API returned empty response"
                logger.warning(
                    f"{message} for endpoint {endpoint} and property ID {property_id}"
                )
                try:
                    await event_crud.log_scrape_event(
                        db,
                        super_id,
                        ScrapeEventTypeEnum.API_CALL_SUCCESS_EMPTY,
                        rightmove_property_id=property_id,
                        api_endpoint_called=endpoint,
                    )
                except Exception as e:
                    logger.error(f"Failed to log empty API response: {str(e)}")
                    # Roll back transaction to prevent PendingRollbackError
                    try:
                        await db.rollback()
                        logger.info(
                            "Rolled back transaction after failed empty API logging"
                        )
                    except Exception as rollback_error:
                        logger.error(
                            f"Failed to roll back transaction: {str(rollback_error)}"
                        )

                results.append(
                    CombinedPropertyResponseItem(
                        api_endpoint=endpoint,
                        property_id=property_id,
                        super_id=super_id,
                        stored=False,
                        message=message,
                    )
                )
                continue  # Skip to the next endpoint

        except Exception as api_error:
            # Handle API call failure
            error_message = str(api_error)
            logger.error(f"API call to {endpoint} failed: {error_message}")

            # Log API call failure
            try:
                await event_crud.log_scrape_event(
                    db,
                    super_id,
                    ScrapeEventTypeEnum.API_CALL_FAILURE,
                    rightmove_property_id=property_id,
                    api_endpoint_called=endpoint,
                    error_code="API_ERROR",
                    error_message=error_message,
                )
            except Exception as log_error:
                logger.error(f"Failed to log API call failure: {str(log_error)}")
                # Roll back transaction to prevent PendingRollbackError
                try:
                    await db.rollback()
                    logger.info(
                        "Rolled back transaction after failed API failure logging"
                    )
                except Exception as rollback_error:
                    logger.error(
                        f"Failed to roll back transaction: {str(rollback_error)}"
                    )

            results.append(
                CombinedPropertyResponseItem(
                    api_endpoint=endpoint,
                    property_id=property_id,
                    super_id=super_id,
                    stored=False,
                    message=f"API call failed: {error_message}",
                )
            )
            continue  # Skip to next endpoint

        # Step 3: Store data in the database if API call was successful
        if raw_data:
            try:
                logger.info(
                    f"Storing data from {endpoint} in database for property ID: {property_id}"
                )
                stored_successfully, message = await store_func(db, raw_data, super_id)

                if stored_successfully:
                    logger.info(f"Successfully stored {endpoint} data: {message}")
                    # Log storage success
                    try:
                        await event_crud.log_scrape_event(
                            db,
                            super_id,
                            ScrapeEventTypeEnum.DATA_STORED_SUCCESS,
                            rightmove_property_id=property_id,
                            api_endpoint_called=endpoint,
                        )
                    except Exception as log_error:
                        logger.error(
                            f"Failed to log successful storage: {str(log_error)}"
                        )
                        # Explicitly roll back to prevent PendingRollbackError
                        await db.rollback()
                else:
                    logger.warning(f"Failed to store data: {message}")
                    # This is not an exception but a controlled failure response from storage function
                    try:
                        await event_crud.log_scrape_event(
                            db,
                            super_id,
                            ScrapeEventTypeEnum.DATA_STORED_FAILURE,
                            rightmove_property_id=property_id,
                            api_endpoint_called=endpoint,
                            error_code="STORAGE_ERROR",
                            error_message=message,
                        )
                    except Exception as log_error:
                        logger.error(f"Failed to log storage failure: {str(log_error)}")
                        # Explicitly roll back to prevent PendingRollbackError
                        await db.rollback()

            except Exception as storage_error:
                # Handle unexpected database storage errors
                error_message = str(storage_error)
                logger.error(
                    f"Exception during database storage for {endpoint}: {error_message}"
                )
                stored_successfully = False
                message = f"Failed to store data: {error_message}"

                # Explicitly roll back the transaction to prevent PendingRollbackError
                try:
                    await db.rollback()
                    logger.info(
                        f"Successfully rolled back transaction after storage error"
                    )
                except Exception as rollback_error:
                    logger.error(
                        f"Failed to roll back transaction: {str(rollback_error)}"
                    )

                # Log storage failure
                try:
                    await event_crud.log_scrape_event(
                        db,
                        super_id,
                        ScrapeEventTypeEnum.DATA_STORED_FAILURE,
                        rightmove_property_id=property_id,
                        api_endpoint_called=endpoint,
                        error_code="STORAGE_ERROR",
                        error_message=error_message,
                    )
                except Exception as log_error:
                    logger.error(f"Failed to log storage failure: {str(log_error)}")
                    # Try to roll back again if logging failed
                    try:
                        await db.rollback()
                    except Exception:
                        pass

            # Add result for this endpoint
            results.append(
                CombinedPropertyResponseItem(
                    api_endpoint=endpoint,
                    property_id=property_id,
                    super_id=super_id,
                    stored=stored_successfully,
                    message=message,
                )
            )

    logger.info(
        f"Completed processing for property ID {property_id}, endpoints processed: {len(results)}"
    )
    return CombinedPropertyResponse(
        property_id=property_id,
        property_url=request.property_url,
        results=results,
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
        # if not super_id:
        #     description = (
        #         request.description
        #         or f"Rightmove property details fetch for property ID: {property_id}"
        #     )
        #     super_id = await super_id_service_client.create_super_id(
        #         description=description
        #     )

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
        if not super_id:  # remove this
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


@router.post("/search/for-sale", response_model=MessageResponse, status_code=202)
async def search_properties_for_sale(
    request: PropertySearchRequest,
    background_tasks: BackgroundTasks,
    update_existing: bool = Query(
        False,
        description="If true, update existing properties. If false, create new snapshot records.",
    ),
):
    """
    Initiates a background task to fetch property search results for a given
    location and stores them in the database.
    """
    logger.info(
        f"Received request to search page {request.page_number} for location: {request.location_identifier}"
    )

    # The background task handles everything from this point.
    background_tasks.add_task(
        process_property_search,
        search_request=request,
        update_existing=update_existing,
    )

    return MessageResponse(
        success=True,
        message=f"Accepted search request for location '{request.location_identifier}'. "
        "Processing will continue in the background.",
    )


async def process_property_search(
    search_request: PropertySearchRequest,
    update_existing: bool,
):
    """
    The complete background task to fetch, log, and store property search results.
    """
    super_id = None
    # Use a new DB session for the background task to ensure it's isolated.
    async with AsyncSessionLocal() as db:
        try:
            # 1. Generate a Super ID for this entire workflow
            super_id = await super_id_service_client.create_super_id(
                description=f"Property search for location: {search_request.location_identifier}, page: {search_request.page_number}"
            )

            # 2. Log the initial request event
            await event_crud.log_scrape_event(
                db,
                super_id,
                ScrapeEventTypeEnum.REQUEST_RECEIVED,
                payload=search_request.model_dump(),
            )

            # 3. Log API call attempt
            api_endpoint = "/buy/property-for-sale"
            await event_crud.log_scrape_event(
                db,
                super_id,
                ScrapeEventTypeEnum.API_CALL_ATTEMPT,
                api_endpoint_called=api_endpoint,
                payload=search_request.model_dump(),
            )

            # 4. Make the API call
            api_response = await rightmove_api_client.search_properties_for_sale(
                location_identifier=search_request.location_identifier,
                min_price=search_request.min_price,
                max_price=search_request.max_price,
                min_bedrooms=search_request.min_bedrooms,
                max_bedrooms=search_request.max_bedrooms,
                property_type=search_request.property_type,
                radius_from_location=search_request.radius_from_location,
                page_number=search_request.page_number,
            )

            properties = api_response.get("data", [])
            if not properties:
                logger.info(
                    f"No properties found for search: {search_request.location_identifier}"
                )
                await event_crud.log_scrape_event(
                    db,
                    super_id,
                    ScrapeEventTypeEnum.API_CALL_SUCCESS,
                    api_endpoint_called=api_endpoint,
                    payload={"message": "No properties found"},
                )
                return

            # 5. Log API call success
            item_count, null_count = analyze_response(api_response)
            await event_crud.log_scrape_event(
                db,
                super_id,
                ScrapeEventTypeEnum.API_CALL_SUCCESS,
                api_endpoint_called=api_endpoint,
                payload=api_response,
                response_item_count=item_count,
                response_null_item_count=null_count,
            )

            # 6. Store the results
            successful, failed = await store_property_search_results(
                db, properties, super_id, update_existing
            )

            # 7. Log final storage status
            await event_crud.log_scrape_event(
                db,
                super_id,
                ScrapeEventTypeEnum.DATA_STORED_SUCCESS,
                payload={"successful_count": successful, "failed_count": failed},
            )
            logger.info(
                f"Search for {search_request.location_identifier} complete. Stored: {successful}, Failed: {failed}"
            )

        except Exception as e:
            logger.error(
                f"Background search task failed for {search_request.location_identifier}: {e}",
                exc_info=True,
            )
            if super_id:
                # Log failure if we got far enough to have a super_id
                await event_crud.log_scrape_event(
                    db,
                    super_id,
                    ScrapeEventTypeEnum.API_CALL_FAILURE,
                    error_message=str(e),
                )
        finally:
            # The 'async with' block handles the session closing automatically.
            pass


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
