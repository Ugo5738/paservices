# src/floorplan_service/routers/floorplan_router.py

import uuid
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

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

router = APIRouter()


@router.post(
    "/analyze", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED
)
async def analyze_floorplans(
    request: FloorplanAnalysisRequest,
    background_tasks: BackgroundTasks,
):
    """Initiates floorplan analysis by sending data to an external service."""
    background_tasks.add_task(
        trigger_floorplan_analysis,
        super_id=request.super_id,
        property_id=request.property_id,
        floorplans_data=request.model_dump()[
            "floorplans"
        ],  # Use model_dump for Pydantic v2
    )
    return MessageResponse(message="Floorplan analysis initiated.")


@router.post(
    "/webhook", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED
)
async def floorplan_webhook(
    payload: WebhookPayload,
    background_tasks: BackgroundTasks,
):
    """Webhook to receive results from the floorplan analysis service."""
    background_tasks.add_task(
        process_webhook_data_task,
        payload_data=payload.model_dump(),  # Use model_dump for Pydantic v2
    )
    return MessageResponse(message="Webhook received. Processing initiated.")


@router.get("/properties", response_model=List[PropertyOverviewResponse])
async def list_properties(db: AsyncSession = Depends(get_db)):
    """Lists all properties that have been analyzed."""
    result = await db.execute(
        select(FpPropertyData).order_by(FpPropertyData.created_at.desc())
    )
    return result.scalars().all()


@router.get("/properties/{property_id}", response_model=List[PropertyDetailResponse])
async def get_property_detail(property_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieves all analysis results for a specific property ID."""
    result = await db.execute(
        select(FpPropertyData).where(FpPropertyData.property_id == property_id)
    )
    properties = result.scalars().all()
    if not properties:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Property not found"
        )
    return properties


@router.get("/floorplans/{floorplan_id}", response_model=PropertyDetailResponse)
async def get_floorplan_detail(floorplan_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieves the analysis result for a specific floorplan ID."""
    result = await db.execute(
        select(FpPropertyData).where(FpPropertyData.floorplan_id == floorplan_id)
    )
    floorplan = result.scalars().first()
    if not floorplan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Floorplan not found"
        )
    return floorplan
