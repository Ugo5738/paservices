# src/floorplan_service/routers/floorplan_router.py

import uuid
from typing import List, Optional

import jwt
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Request,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..config import settings
from ..db import get_db
from ..models.floorplan_models import FpPropertyData
from ..schemas.floorplan_schemas import (
    FloorplanAnalysisRequest,
    MessageResponse,
    PropertyDetailResponse,
    PropertyOverviewResponse,
    WebhookPayload,
)
from ..services.analysis_service import (
    process_webhook_data_task,
    trigger_floorplan_analysis,
)
from ..utils.logging_config import logger
from ..utils.security import validate_token

router = APIRouter()


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
    "/analyze", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED
)
async def analyze_floorplans(
    request_data: FloorplanAnalysisRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    _token_data: dict = Depends(validate_token),
):
    """
    Initiates floorplan analysis by sending data to an external service.

    If the request is missing authentication or a super_id, this endpoint
    will return a **200 OK** with an MCP response guiding the client on how
    to acquire the necessary credentials.
    """
    actor = _extract_actor_from_request(request)
    logger.info(
        "Inbound request: floorplan analyze",
        extra={
            "request": {
                "method": request.method,
                "path": request.url.path,
                "client_host": (request.client.host if request.client else None),
                "actor": actor,
            },
            "body_excerpt": _redact_sensitive(request_data.model_dump()),
        },
    )

    # At this point, you know the token exists. A proper security dependency can now validate it.
    # For simplicity, we'll assume the token is valid for this example.
    if not request_data.super_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="super_id is required for floorplan analysis.",
        )

    background_tasks.add_task(
        trigger_floorplan_analysis,
        super_id=request_data.super_id,
        property_id=request_data.property_id,
        floorplans_data=request_data.model_dump()["floorplans"],
        callback_payload=(
            request_data.callback.model_dump(mode="json")
            if request_data.callback
            else None
        ),
    )
    response = MessageResponse(message="Floorplan analysis initiated.")
    logger.info(
        "Outbound response: floorplan analyze",
        extra={
            "status": status.HTTP_202_ACCEPTED,
            "super_id": str(request_data.super_id) if request_data.super_id else None,
        },
    )
    return response


@router.post(
    "/webhook", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED
)
async def floorplan_webhook(
    payload: WebhookPayload,
    background_tasks: BackgroundTasks,
    request: Request,
):
    """Webhook to receive results from the floorplan analysis service."""
    actor = _extract_actor_from_request(request)
    logger.info(
        "Inbound request: floorplan webhook",
        extra={
            "request": {
                "method": request.method,
                "path": request.url.path,
                "client_host": (request.client.host if request.client else None),
                "actor": actor,
            },
            "body_excerpt": _redact_sensitive(payload.model_dump()),
        },
    )
    background_tasks.add_task(
        process_webhook_data_task,
        payload_data=payload.model_dump(),  # Use model_dump for Pydantic v2
    )
    response = MessageResponse(message="Webhook received. Processing initiated.")
    logger.info(
        "Outbound response: floorplan webhook",
        extra={"status": status.HTTP_202_ACCEPTED},
    )
    return response


@router.get("/properties", response_model=List[PropertyOverviewResponse])
async def list_properties(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _token_data: dict = Depends(validate_token),
):
    """Lists all properties that have been analyzed."""
    actor = _extract_actor_from_request(request)
    logger.info(
        "Inbound request: list floorplan properties",
        extra={
            "request": {
                "method": request.method,
                "path": request.url.path,
                "client_host": (request.client.host if request.client else None),
                "actor": actor,
            }
        },
    )
    result = await db.execute(
        select(FpPropertyData).order_by(FpPropertyData.created_at.desc())
    )
    items = result.scalars().all()
    logger.info(
        "Outbound response: list floorplan properties",
        extra={"count": len(items)},
    )
    return items


@router.get("/properties/{property_id}", response_model=List[PropertyDetailResponse])
async def get_property_detail(
    property_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _token_data: dict = Depends(validate_token),
):
    """Retrieves all analysis results for a specific property ID."""
    actor = _extract_actor_from_request(request)
    logger.info(
        "Inbound request: get floorplan property detail",
        extra={
            "request": {
                "method": request.method,
                "path": request.url.path,
                "client_host": (request.client.host if request.client else None),
                "actor": actor,
            },
            "property_id": property_id,
        },
    )
    result = await db.execute(
        select(FpPropertyData).where(FpPropertyData.property_id == property_id)
    )
    properties = result.scalars().all()
    if not properties:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Property not found"
        )
    logger.info(
        "Outbound response: get floorplan property detail",
        extra={"count": len(properties), "property_id": property_id},
    )
    return properties


@router.get("/floorplans/{floorplan_id}", response_model=PropertyDetailResponse)
async def get_floorplan_detail(
    floorplan_id: str, request: Request, db: AsyncSession = Depends(get_db)
):
    """Retrieves the analysis result for a specific floorplan ID."""
    actor = _extract_actor_from_request(request)
    logger.info(
        "Inbound request: get floorplan detail",
        extra={
            "request": {
                "method": request.method,
                "path": request.url.path,
                "client_host": (request.client.host if request.client else None),
                "actor": actor,
            },
            "floorplan_id": floorplan_id,
        },
    )
    result = await db.execute(
        select(FpPropertyData).where(FpPropertyData.floorplan_id == floorplan_id)
    )
    floorplan = result.scalars().first()
    if not floorplan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Floorplan not found"
        )
    logger.info(
        "Outbound response: get floorplan detail",
        extra={"floorplan_id": floorplan_id},
    )
    return floorplan
