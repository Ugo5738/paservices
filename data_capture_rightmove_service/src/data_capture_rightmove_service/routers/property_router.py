# data_capture_rightmove_service/src/data_capture_rightmove_service/routers/property_router.py
"""
Router for property data operations, including fetching from Rightmove API and storing in database.
"""

import asyncio
import json
import math
import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional

import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
from data_capture_rightmove_service.models.properties_details_v2 import (
    ApiPropertiesDetailsV2,
)
from data_capture_rightmove_service.models.property_for_sale import PropertyListing
from data_capture_rightmove_service.models.scrape_event import ScrapeEventTypeEnum
from data_capture_rightmove_service.schemas.common import MessageResponse
from data_capture_rightmove_service.schemas.property_data import (  # PropertiesBySuperIdResponse,
    CombinedPropertyResponse,
    CombinedPropertyResponseItem,
    FetchBatchRequest,
    FetchBatchResponse,
    FetchPropertyDetailsRequest,
    FetchPropertyResponse,
    FilteredPropertiesResponse,
    FilteredScrapedPropertiesResponse,
    PropertyDetailsStorageResponse,
    PropertyListingResponse,
    PropertySearchRequest,
    PropertyUrlResponse,
    ScrapedListingResponse,
    WorkflowCallback,
)
from data_capture_rightmove_service.utils.data_completeness import analyze_response
from data_capture_rightmove_service.utils.logging_config import (
    configure_logging,
    logger,
)
from data_capture_rightmove_service.utils.security import requires_scope, validate_token
from data_capture_rightmove_service.utils.status_notifier import get_status_notifier
from data_capture_rightmove_service.utils.url_parsing import (
    extract_rightmove_property_id,
    is_valid_rightmove_url,
)

router = APIRouter(prefix="/properties", tags=["Properties"])


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

def _extract_callback_urls(callback_urls_payload: Optional[dict]) -> List[str]:
    if not isinstance(callback_urls_payload, dict):
        return []
    urls: List[str] = []
    workflow_url = callback_urls_payload.get("workflow_callback_url")
    external_url = callback_urls_payload.get("external_callback_url")
    if workflow_url:
        urls.append(str(workflow_url))
    if external_url:
        urls.append(str(external_url))
    return list(dict.fromkeys(urls))



@router.post(
    "/fetch/combined",
    response_model=MessageResponse,
    status_code=202,
    operation_id="fetch_combined_property_data",
)
async def fetch_combined_property_data(
    request: FetchPropertyDetailsRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
    token_data: dict = Depends(validate_token),
) -> MessageResponse:
    actor = _extract_actor_from_request(http_request)
    payload_excerpt = _redact_sensitive(request.model_dump(mode="json"))
    logger.info(
        "Inbound request: fetch combined property data",
        extra={
            "request": {
                "method": http_request.method,
                "path": http_request.url.path,
                "client_host": (
                    http_request.client.host if http_request.client else None
                ),
                "actor": actor,
                "body_excerpt": payload_excerpt,
            },
            "super_id": str(request.super_id) if request.super_id else None,
        },
    )

    try:
        extracted_id = (
            extract_rightmove_property_id(request.property_url)
            if request.property_url
            else None
        )
        if not extracted_id and not request.property_id:
            raise ValueError(
                "Either a valid Rightmove property URL or property ID must be provided"
            )
    except (ValueError, TypeError) as exc:
        logger.error(
            "Failed to parse property identifier from request.",
            extra={"request_body": request.model_dump(mode="json"), "error": str(exc)},
            exc_info=True,
        )
        raise HTTPException(status_code=400, detail=f"Invalid property identifier: {exc}")

    if not request.super_id:
        raise HTTPException(
            status_code=400,
            detail="super_id is required to fetch combined property data.",
        )

    callback_payload = (
        request.callback.model_dump(mode="json") if request.callback else None
    )

    background_tasks.add_task(
        process_combined_property_fetch,
        request.model_dump(mode="json"),
        token_data,
        callback_payload,
    )

    return MessageResponse(
        message=(
            "Accepted combined fetch request. Processing will continue in the background."
        ),
        success=True,
    )


async def process_combined_property_fetch(
    request_payload: Dict[str, Any],
    token_data: Dict[str, Any],
    callback_payload: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        request = FetchPropertyDetailsRequest.model_validate(request_payload)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error(
            "Failed to validate combined fetch payload.",
            extra={"payload": request_payload, "error": str(exc)},
        )
        return

    callback = (
        WorkflowCallback.model_validate(callback_payload)
        if callback_payload
        else None
    )
    callback_url = callback.url if callback else None
    callback_headers = callback.headers if callback else None
    callback_urls_payload = request_payload.get("callback_urls")
    callback_urls = _extract_callback_urls(callback_urls_payload)
    if callback_url:
        callback_urls = list(dict.fromkeys([str(callback_url), *callback_urls]))

    try:
        extracted_id = (
            extract_rightmove_property_id(request.property_url)
            if request.property_url
            else None
        )
        if not extracted_id and not request.property_id:
            raise ValueError(
                "Either a valid Rightmove property URL or property ID must be provided"
            )
        property_id = int(extracted_id or request.property_id)
    except Exception as exc:
        logger.error(
            "Failed resolving property identifier for combined fetch.",
            extra={"payload": request_payload, "error": str(exc)},
        )
        return

    super_id = request.super_id
    if not super_id:
        logger.error(
            "Combined fetch task invoked without super_id.",
            extra={"property_id": property_id},
        )
        return

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

    notifier = get_status_notifier()
    status_context = "fetch_combined"
    status_results: List[Dict[str, Any]] = []
    status_data: Dict[str, Any] = {
        "property_id": property_id,
        "property_url": request.property_url,
        "super_id": str(super_id),
        "results": status_results,
    }
    status_metadata: Dict[str, Any] = {
        "property_id": property_id,
        "property_url": request.property_url,
        "client_id": token_data.get("sub"),
        "callback_url": callback_url,
        "callback_urls": callback_urls_payload,
    }
    status_summary: Dict[str, Any] = {
        "total_endpoints": len(endpoints),
        "completed_endpoints": 0,
    }

    notification_status = "completed"
    failure_summary: Optional[Dict[str, Any]] = None

    if notifier:
        await notifier.notify(
            super_id=super_id,
            status="started",
            context=status_context,
            data=status_data,
            summary=dict(status_summary),
            metadata=status_metadata,
            webhook_url=callback_url,
            webhook_urls=callback_urls,
            webhook_headers=callback_headers,
            property_id=property_id,
            stage="initializing",
            progress=0.0,
        )

    async with AsyncSessionLocal() as db:
        try:
            await event_crud.log_scrape_event(
                db,
                super_id,
                ScrapeEventTypeEnum.REQUEST_RECEIVED,
                rightmove_property_id=property_id,
                payload=request_payload,
            )
            await db.commit()
        except Exception as log_exc:
            logger.error(
                "Failed to log initial combined fetch event.",
                extra={"super_id": str(super_id), "error": str(log_exc)},
            )
            await db.rollback()

        try:
            for endpoint, (api_call, store_func) in endpoints.items():
                raw_data = None
                stored_successfully = False
                message = ""

                try:
                    await event_crud.log_scrape_event(
                        db,
                        super_id,
                        ScrapeEventTypeEnum.API_CALL_ATTEMPT,
                        rightmove_property_id=property_id,
                        api_endpoint_called=endpoint,
                    )
                    await db.commit()
                except Exception as log_exc:
                    logger.error(
                        "Failed to log API attempt for combined fetch.",
                        extra={"endpoint": endpoint, "error": str(log_exc)},
                    )
                    await db.rollback()

                try:
                    raw_data = await api_call(str(property_id))
                except Exception as api_exc:
                    message = f"API call failed: {api_exc}"
                    notification_status = "failed"
                    failure_summary = {"error": str(api_exc)}
                    logger.error(
                        "Combined fetch API call failed.",
                        extra={
                            "endpoint": endpoint,
                            "property_id": property_id,
                            "super_id": str(super_id),
                            "error": str(api_exc),
                        },
                    )
                    try:
                        await event_crud.log_scrape_event(
                            db,
                            super_id,
                            ScrapeEventTypeEnum.API_CALL_FAILURE,
                            rightmove_property_id=property_id,
                            api_endpoint_called=endpoint,
                            error_code="API_ERROR",
                            error_message=str(api_exc),
                        )
                        await db.commit()
                    except Exception:
                        await db.rollback()
                else:
                    if raw_data:
                        item_count, null_count = analyze_response(raw_data)
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
                            await db.commit()
                        except Exception as log_exc:
                            logger.error(
                                "Failed to log API success for combined fetch.",
                                extra={"endpoint": endpoint, "error": str(log_exc)},
                            )
                            await db.rollback()

                        try:
                            stored_successfully, message = await store_func(
                                db, raw_data, super_id
                            )
                            await db.commit()
                            if stored_successfully:
                                await event_crud.log_scrape_event(
                                    db,
                                    super_id,
                                    ScrapeEventTypeEnum.DATA_STORED_SUCCESS,
                                    rightmove_property_id=property_id,
                                    api_endpoint_called=endpoint,
                                )
                            else:
                                await event_crud.log_scrape_event(
                                    db,
                                    super_id,
                                    ScrapeEventTypeEnum.DATA_STORED_FAILURE,
                                    rightmove_property_id=property_id,
                                    api_endpoint_called=endpoint,
                                    error_code="STORAGE_ERROR",
                                    error_message=message,
                                )
                            await db.commit()
                        except Exception as storage_exc:
                            stored_successfully = False
                            message = f"Failed to store data: {storage_exc}"
                            notification_status = "failed"
                            failure_summary = {"error": str(storage_exc)}
                            logger.error(
                                "Combined fetch storage failure.",
                                extra={
                                    "endpoint": endpoint,
                                    "property_id": property_id,
                                    "error": str(storage_exc),
                                },
                            )
                            await db.rollback()
                            try:
                                await event_crud.log_scrape_event(
                                    db,
                                    super_id,
                                    ScrapeEventTypeEnum.DATA_STORED_FAILURE,
                                    rightmove_property_id=property_id,
                                    api_endpoint_called=endpoint,
                                    error_code="STORAGE_ERROR",
                                    error_message=str(storage_exc),
                                )
                                await db.commit()
                            except Exception:
                                await db.rollback()
                    else:
                        message = "API returned empty response"
                        logger.warning(
                            "Combined fetch endpoint returned empty payload.",
                            extra={
                                "endpoint": endpoint,
                                "property_id": property_id,
                                "super_id": str(super_id),
                            },
                        )
                        try:
                            await event_crud.log_scrape_event(
                                db,
                                super_id,
                                ScrapeEventTypeEnum.API_CALL_SUCCESS_EMPTY,
                                rightmove_property_id=property_id,
                                api_endpoint_called=endpoint,
                            )
                            await db.commit()
                        except Exception:
                            await db.rollback()

                status_results.append(
                    CombinedPropertyResponseItem(
                        api_endpoint=endpoint,
                        property_id=property_id,
                        super_id=super_id,
                        stored=stored_successfully,
                        message=message,
                        raw_data=raw_data,
                    ).model_dump(mode="json")
                )
                status_summary["completed_endpoints"] = len(status_results)

                if notifier:
                    progress = (
                        len(status_results) / max(len(endpoints), 1)
                        if endpoints
                        else None
                    )
                    await notifier.notify(
                        super_id=super_id,
                        status="in_progress",
                        context=status_context,
                        data=status_data,
                        summary=dict(status_summary),
                        metadata=status_metadata,
                        webhook_url=callback_url,
                        webhook_urls=callback_urls,
                        webhook_headers=callback_headers,
                        property_id=property_id,
                        stage=f"endpoint:{endpoint}",
                        progress=progress,
                    )

        except Exception as exc:
            notification_status = "failed"
            failure_summary = {"error": str(exc)}
            logger.error(
                "Combined fetch task encountered an error.",
                extra={
                    "super_id": str(super_id),
                    "property_id": property_id,
                    "error": str(exc),
                },
                exc_info=True,
            )
            await db.rollback()
        finally:
            if notifier:
                try:
                    summary_payload = dict(status_summary)
                    if failure_summary:
                        summary_payload.update(failure_summary)
                    await notifier.notify(
                        super_id=super_id,
                        status=notification_status,
                        context=status_context,
                        data=status_data,
                        summary=summary_payload,
                        metadata=status_metadata,
                        webhook_url=callback_url,
                        webhook_urls=callback_urls,
                        webhook_headers=callback_headers,
                        property_id=property_id,
                        stage="completed"
                        if notification_status == "completed"
                        else "combined_fetch",
                        progress=1.0 if notification_status == "completed" else None,
                        last_error=summary_payload.get("error"),
                    )
                except Exception as notify_error:
                    logger.error(
                        "Failed to broadcast combined fetch status update.",
                        extra={
                            "context": status_context,
                            "super_id": str(super_id),
                            "error": str(notify_error),
                        },
                    )
@router.get("/validate-url", response_model=PropertyUrlResponse)
async def validate_property_url(
    url: str = Query(..., description="Rightmove property URL to validate"),
    http_request: Request = None,
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

        response = PropertyUrlResponse(
            url=url,
            valid=True,
            property_id=property_id,
            message=f"Successfully extracted property ID: {property_id}",
        )
        if http_request is not None:
            logger.info(
                "Outbound response: validate property url",
                extra={"status": 200, "valid": True, "property_id": property_id},
            )
        return response
    except Exception as e:
        logger.error(f"Error validating property URL: {str(e)}")
        return PropertyUrlResponse(
            url=url,
            valid=False,
            property_id=None,
            message=f"Error processing URL: {str(e)}",
        )


@router.post(
    "/fetch/details",
    response_model=PropertyDetailsStorageResponse,
    operation_id="fetch_property_details",
)
async def fetch_property_details(
    request: FetchPropertyDetailsRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
    _token_data: dict = Depends(validate_token),
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

        # Require a super_id to proceed
        super_id = request.super_id
        if not super_id:
            raise HTTPException(
                status_code=400,
                detail="super_id is required to fetch property details.",
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

        response = PropertyDetailsStorageResponse(
            property_id=property_id,
            super_id=super_id,
            stored=success,
            message=message,
        )
        logger.info(
            "Outbound response: fetch property details",
            extra={
                "property_id": property_id,
                "stored": success,
                "super_id": str(super_id) if super_id else None,
            },
        )
        return response
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
    http_request: Request,
    _token_data: dict = Depends(validate_token),
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

        # Require caller-provided super_id
        super_id = request.super_id
        if not super_id:
            raise HTTPException(
                status_code=400,
                detail="super_id is required to fetch property-for-sale details.",
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
    http_request: Request,
    _token_data: dict = Depends(validate_token),
    update_existing: bool = Query(
        False,
        description="If true, update existing properties. If false, create new snapshot records.",
    ),
):
    """
    Initiates a background task to fetch property search results for a given
    location and stores them in the database.
    """

    # --- ADD THIS LINE FOR DEBUGGING ---
    logger.info(f"Received search request payload: {request.model_dump()}")
    # ------------------------------------

    actor = _extract_actor_from_request(http_request)
    logger.info(
        "Inbound request: search properties for sale",
        extra={
            "request": {
                "method": http_request.method,
                "path": http_request.url.path,
                "client_host": (
                    http_request.client.host if http_request.client else None
                ),
                "actor": actor,
            },
            "body_excerpt": _redact_sensitive(request.model_dump(mode="json")),
            "update_existing": update_existing,
        },
    )

    if not request.super_id:
        logger.error(
            "Rejecting search request without super_id.",
            extra={"location_identifier": request.location_identifier},
        )
        raise HTTPException(
            status_code=400,
            detail="super_id is required for property search requests.",
        )

    # The background task handles everything from this point.
    background_tasks.add_task(
        process_property_search,
        search_request=request,
        update_existing=update_existing,
    )

    response = MessageResponse(
        success=True,
        message=f"Accepted search request for location '{request.location_identifier}'. "
        "Processing will continue in the background.",
    )
    logger.info(
        "Outbound response: search properties for sale",
        extra={"status": 202, "location_identifier": request.location_identifier},
    )
    return response


async def process_property_search(
    search_request: PropertySearchRequest,
    update_existing: bool,
):
    """
    The complete background task to fetch, log, and store property search results.
    If `num_properties` is specified in the request, it will paginate through
    results until the threshold is met. Otherwise, it fetches a single page.
    """
    configure_logging()

    if not search_request.super_id:
        logger.error(
            "Background task invoked without super_id; aborting.",
            extra={"location_identifier": search_request.location_identifier},
        )
        return
    super_id = search_request.super_id

    callback = search_request.callback
    callback_url = callback.url if callback else None
    callback_headers = callback.headers if callback else None
    callback_urls_payload = search_request.model_dump(mode="json").get("callback_urls")
    callback_urls = _extract_callback_urls(callback_urls_payload)
    if callback_url:
        callback_urls = list(dict.fromkeys([str(callback_url), *callback_urls]))

    notifier = get_status_notifier()
    status_context = "search"
    collected_properties: List[Dict[str, Any]] = []
    status_data: Dict[str, Any] = {
        "location_identifier": search_request.location_identifier,
        "super_id": str(super_id),
        "properties": collected_properties,
    }
    status_summary: Dict[str, Any] = {
        "total_successful": 0,
        "total_failed": 0,
        "current_page": 0,
        "total_pages": None,
    }
    status_metadata: Dict[str, Any] = {
        "location_identifier": search_request.location_identifier,
        "num_properties_requested": search_request.num_properties,
        "update_existing": update_existing,
        "callback_url": callback_url,
        "callback_urls": callback_urls_payload,
    }

    if notifier:
        await notifier.notify(
            super_id=super_id,
            status="started",
            context=status_context,
            data=status_data,
            summary=dict(status_summary),
            metadata=status_metadata,
            webhook_url=callback_url,
            webhook_urls=callback_urls,
            webhook_headers=callback_headers,
            stage="initializing",
            progress=0.0,
        )
    notification_status = "completed"
    failure_summary: Optional[Dict[str, Any]] = None
    total_successful = 0
    total_failed = 0

    # Use a new DB session for the background task to ensure it's isolated.
    async with AsyncSessionLocal() as db:
        try:
            # 1. Generate a Super ID for this entire workflow
            description = (
                f"Property search for location: {search_request.location_identifier}"
            )
            if search_request.num_properties:
                description += (
                    f" (requesting up to {search_request.num_properties} properties)"
                )
            else:
                description += f", page: {search_request.page_number}"

            # 2. Log the initial request event
            await event_crud.log_scrape_event(
                db,
                super_id,
                ScrapeEventTypeEnum.REQUEST_RECEIVED,
                payload=search_request.model_dump(),
            )

            num_to_fetch = search_request.num_properties
            # Prepare parameters for the API client, excluding num_properties
            search_params = search_request.model_dump(exclude_unset=True)
            search_params.pop("num_properties", None)
            search_params.pop("super_id", None)

            # Initialize counters for the entire workflow
            total_successful = 0
            total_failed = 0

            # --- PAGINATION LOGIC ---
            logger.info(
                f"Starting paginated search for location: {search_request.location_identifier}, targeting up to {num_to_fetch} properties."
            )

            # Fetch the first page to get metadata
            search_params["page_number"] = 1
            initial_response = await rightmove_api_client.search_properties_for_sale(
                **search_params
            )

            properties_on_page = initial_response.get("data", [])
            if not properties_on_page:
                logger.info("No properties found on the first page. Exiting task.")
                status_summary["total_pages"] = 0
                status_summary["current_page"] = 0
                return

            # Store the first page of results
            successful, failed = await store_property_search_results(
                db, properties_on_page, super_id, update_existing
            )
            total_successful += successful
            total_failed += failed
            logger.info(f"Page 1: Stored {successful} properties, {failed} failed.")

            total_results = initial_response.get("totalResultCount", 0)
            per_page = initial_response.get("resultsPerPage", 25)
            total_pages = (
                math.ceil(total_results / per_page) if total_results > 0 else 1
            )
            logger.info(
                f"Total properties available: {total_results}. Total pages: {total_pages}"
            )

            collected_properties.extend(properties_on_page)
            status_summary["total_successful"] = total_successful
            status_summary["total_failed"] = total_failed
            status_summary["current_page"] = 1
            status_summary["total_pages"] = total_pages
            status_metadata["total_results_available"] = total_results
            status_metadata["results_per_page"] = per_page
            if notifier:
                progress = 1 / total_pages if total_pages else None
                await notifier.notify(
                    super_id=super_id,
                    status="in_progress",
                    context=status_context,
                    data=status_data,
                    summary=dict(status_summary),
                    metadata=status_metadata,
                    webhook_url=callback_url,
                    webhook_urls=callback_urls,
                    webhook_headers=callback_headers,
                    stage="page:1",
                    progress=progress,
                )

            # Loop through subsequent pages
            for page_num in range(2, total_pages + 1):
                if num_to_fetch and total_successful >= num_to_fetch:
                    status_metadata["target_reached"] = True
                    logger.info(
                        f"Target of {num_to_fetch} properties reached. Stopping fetch."
                    )
                    break

                logger.info(
                    f"Fetching and processing page {page_num} of {total_pages}..."
                )
                search_params["page_number"] = page_num
                page_response = await rightmove_api_client.search_properties_for_sale(
                    **search_params
                )

                properties_on_page = page_response.get("data", [])
                if not properties_on_page:
                    # --- ADD THIS LINE FOR PROOF ---
                    logger.warning(
                        f"Raw response for empty page {page_num}: {page_response}"
                    )
                    # ---------------------------------
                    logger.warning(
                        f"No properties found on page {page_num}. Stopping pagination."
                    )
                    break

                # Store this page's results immediately
                successful, failed = await store_property_search_results(
                    db, properties_on_page, super_id, update_existing
                )
                total_successful += successful
                total_failed += failed
                logger.info(
                    f"Page {page_num}: Stored {successful} properties, {failed} failed. Cumulative totals: {total_successful} successful, {total_failed} failed."
                )

                collected_properties.extend(properties_on_page)
                status_summary["total_successful"] = total_successful
                status_summary["total_failed"] = total_failed
                status_summary["current_page"] = page_num
                status_summary["total_pages"] = total_pages
                if notifier:
                    progress = page_num / total_pages if total_pages else None
                    await notifier.notify(
                        super_id=super_id,
                        status="in_progress",
                        context=status_context,
                        data=status_data,
                        summary=dict(status_summary),
                        metadata=status_metadata,
                        webhook_url=callback_url,
                        webhook_urls=callback_urls,
                        webhook_headers=callback_headers,
                        stage=f"page:{page_num}",
                        progress=progress,
                    )

                await asyncio.sleep(0.5)  # Politeness delay

            logger.info(
                f"Search for {search_request.location_identifier} complete. Total Stored: {total_successful}, Total Failed: {total_failed}"
            )
            status_metadata["total_successful"] = total_successful
            status_metadata["total_failed"] = total_failed
            # Final log event summarizing the entire operation
            await event_crud.log_scrape_event(
                db,
                super_id,
                ScrapeEventTypeEnum.DATA_STORED_SUCCESS,
                payload={
                    "successful_count": total_successful,
                    "failed_count": total_failed,
                    "message": "Paginated search complete.",
                },
            )

            await db.commit()

        except Exception as e:
            notification_status = "failed"
            failure_summary = {"error": str(e)}
            logger.error(
                f"Background search task failed for {search_request.location_identifier}: {e}",
                exc_info=True,
            )
            await db.rollback()  # Good practice to explicitly rollback on error

            if super_id:
                # This log event might fail if the primary error was DB-related, but try anyway
                try:
                    await event_crud.log_scrape_event(
                        db,
                        super_id,
                        ScrapeEventTypeEnum.API_CALL_FAILURE,
                        error_message=str(e),
                    )
                    await db.commit()
                except:
                    await db.rollback()
        finally:
            if notifier:
                try:
                    status_summary["total_successful"] = total_successful
                    status_summary["total_failed"] = total_failed
                    status_summary.setdefault("current_page", 0)
                    status_summary.setdefault("total_pages", None)
                    summary_payload = dict(status_summary)
                    if failure_summary:
                        summary_payload.update(failure_summary)
                    await notifier.notify(
                        super_id=super_id,
                        status=notification_status,
                        context=status_context,
                        data=status_data,
                        summary=summary_payload,
                        metadata=status_metadata,
                        webhook_url=callback_url,
                        webhook_urls=callback_urls,
                        webhook_headers=callback_headers,
                        stage="completed" if notification_status == "completed" else "search",
                        progress=1.0 if notification_status == "completed" else None,
                        last_error=summary_payload.get("error"),
                    )
                except Exception as notify_error:
                    logger.error(
                        "Failed to broadcast search status update",
                        extra={
                            "context": status_context,
                            "super_id": str(super_id),
                            "error": str(notify_error),
                        },
                    )


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


@router.get("/listings", response_model=FilteredPropertiesResponse)
async def get_filtered_property_listings(
    token_data: dict = Depends(validate_token),
    db: AsyncSession = Depends(get_db),
    on_date: str = Query(
        ..., description="Filter properties created on a specific date (YYYY-MM-DD)."
    ),
    from_time: Optional[str] = Query(
        None, description="Optional start time on that date (HH:MM)."
    ),
    to_time: Optional[str] = Query(
        None, description="Optional end time on that date (HH:MM)."
    ),
    min_bedrooms: Optional[int] = Query(None, ge=0),
    max_bedrooms: Optional[int] = Query(None, ge=0),
    min_bathrooms: Optional[int] = Query(None, ge=0),
    max_bathrooms: Optional[int] = Query(None, ge=0),
    limit: int = Query(1000, le=5000),
):
    """
    Retrieves a list of the most recent unique property listings based on filter criteria.
    Primarily filters by a specific date, with optional time window and property attributes.
    """
    logger.info(f"Fetching listings for date: {on_date} from {from_time} to {to_time}")
    try:
        # --- Date and Time Filtering Logic ---
        target_date = datetime.strptime(on_date, "%Y-%m-%d").date()

        start_datetime = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
        end_datetime = datetime.combine(target_date, time.max, tzinfo=timezone.utc)

        if from_time:
            start_time_obj = time.fromisoformat(from_time)
            start_datetime = start_datetime.replace(
                hour=start_time_obj.hour, minute=start_time_obj.minute
            )

        if to_time:
            end_time_obj = time.fromisoformat(to_time)
            end_datetime = end_datetime.replace(
                hour=end_time_obj.hour, minute=end_time_obj.minute
            )

        # Subquery to find the latest snapshot for each property ID
        latest_snapshot_subq = (
            select(
                PropertyListing.id,
                func.max(PropertyListing.snapshot_id).label("max_snapshot_id"),
            )
            .group_by(PropertyListing.id)
            .subquery()
        )

        stmt = select(PropertyListing).join(
            latest_snapshot_subq,
            PropertyListing.snapshot_id == latest_snapshot_subq.c.max_snapshot_id,
        )

        # Apply filters
        stmt = stmt.where(PropertyListing.created_at >= start_datetime)
        stmt = stmt.where(PropertyListing.created_at <= end_datetime)

        if min_bedrooms is not None:
            stmt = stmt.where(PropertyListing.bedrooms >= min_bedrooms)
        if max_bedrooms is not None:
            stmt = stmt.where(PropertyListing.bedrooms <= max_bedrooms)
        if min_bathrooms is not None:
            stmt = stmt.where(PropertyListing.bathrooms >= min_bathrooms)
        if max_bathrooms is not None:
            stmt = stmt.where(PropertyListing.bathrooms <= max_bathrooms)

        stmt = stmt.order_by(desc(PropertyListing.created_at)).limit(limit)

        result = await db.execute(stmt)
        properties = result.scalars().all()

        # Manually construct the list of response objects instead of relying on model_validate.
        # This gives us explicit control over the data being returned.
        property_responses = []
        for p in properties:
            property_responses.append(
                PropertyListingResponse(
                    id=p.id,
                    snapshot_id=p.snapshot_id,
                    property_url=p.property_url,  # Explicitly include the URL
                    display_address=p.display_address,
                    bedrooms=p.bedrooms,
                    bathrooms=p.bathrooms,
                    created_at=p.created_at,
                    super_id=p.super_id,
                )
            )

        return FilteredPropertiesResponse(properties=property_responses)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date or time format. Use YYYY-MM-DD and HH:MM.",
        )
    except Exception as e:
        logger.error(f"Error retrieving filtered properties: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to retrieve properties from database."
        )


@router.get("/scraped-listings", response_model=FilteredScrapedPropertiesResponse)
async def get_scraped_property_listings(
    token_data: dict = Depends(validate_token),
    db: AsyncSession = Depends(get_db),
    on_date: str = Query(
        ..., description="Filter properties scraped on a specific date (YYYY-MM-DD)."
    ),
    from_time: Optional[str] = Query(
        None, description="Optional start time on that date (HH:MM)."
    ),
    to_time: Optional[str] = Query(
        None, description="Optional end time on that date (HH:MM)."
    ),
    min_bedrooms: Optional[int] = Query(None, ge=0),
    limit: int = Query(1000, le=5000),
):
    """
    Retrieves a list of properties that have been successfully scraped, including
    the unique super_id associated with each scrape event.
    """
    logger.info(
        f"Fetching SCRAPED listings for date: {on_date} from {from_time} to {to_time}"
    )
    try:
        target_date = datetime.strptime(on_date, "%Y-%m-%d").date()
        start_datetime = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
        end_datetime = datetime.combine(target_date, time.max, tzinfo=timezone.utc)

        if from_time:
            start_time_obj = time.fromisoformat(from_time)
            start_datetime = start_datetime.replace(
                hour=start_time_obj.hour, minute=start_time_obj.minute
            )
        if to_time:
            end_time_obj = time.fromisoformat(to_time)
            end_datetime = end_datetime.replace(
                hour=end_time_obj.hour, minute=end_time_obj.minute
            )

        # Query the detailed scrape table, NOT the search results table
        stmt = select(ApiPropertiesDetailsV2)
        stmt = stmt.where(ApiPropertiesDetailsV2.created_at >= start_datetime)
        stmt = stmt.where(ApiPropertiesDetailsV2.created_at <= end_datetime)

        if min_bedrooms is not None:
            stmt = stmt.where(ApiPropertiesDetailsV2.bedrooms >= min_bedrooms)

        stmt = stmt.order_by(desc(ApiPropertiesDetailsV2.created_at)).limit(limit)

        result = await db.execute(stmt)
        properties = result.scalars().all()

        property_responses = [
            ScrapedListingResponse.model_validate(p) for p in properties
        ]

        return FilteredScrapedPropertiesResponse(properties=property_responses)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date or time format. Use YYYY-MM-DD and HH:MM.",
        )
    except Exception as e:
        logger.error(f"Error retrieving scraped properties: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to retrieve scraped properties."
        )


class DirectSearchRequest(BaseModel):
    """Pydantic model for the direct test endpoint."""

    location_identifier: str
    search_radius: float
    added_to_site: Optional[int] = None
    has_include_under_offer_sold_stc: Optional[bool] = None


@router.post("/search/for-sale/direct-test", status_code=200)
async def direct_api_test(
    request: DirectSearchRequest,
):
    """
    A temporary debug endpoint to call the Rightmove API directly and return the raw response.
    This bypasses background tasks and database saving for pure API testing.
    """
    logger.info(f"--- DIRECT API TEST INITIATED ---")
    logger.info(f"Received direct test request with params: {request.model_dump()}")

    try:
        # Prepare parameters for the API client from the request body
        api_params = request.model_dump(exclude_unset=True)

        # The client expects 'include_under_offer_sold_stc', not 'has_include...'
        if "has_include_under_offer_sold_stc" in api_params:
            api_params["include_under_offer_sold_stc"] = api_params.pop(
                "has_include_under_offer_sold_stc"
            )

        # Call the API client directly with the provided parameters
        api_response = await rightmove_api_client.search_properties_for_sale(
            **api_params
        )

        logger.info(f"--- DIRECT API TEST RESPONSE ---")
        logger.info(json.dumps(api_response, indent=2))

        # Return the full, raw response from the external API
        return api_response

    except Exception as e:
        logger.error(f"Direct API test failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred during the direct API call: {str(e)}",
        )
