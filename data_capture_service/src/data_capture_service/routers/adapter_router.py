"""
Per-adapter endpoints — each adapter is individually addressable for discrete MCP tool exposure.

POST /data_capture/adapters/motie      — Direct Motie data_capture (still runs baseline+validation)
POST /data_capture/adapters/firecrawl  — Firecrawl baseline only (quick field check)
GET  /data_capture/adapters/registry   — List registered adapters
"""

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.clients.super_id_service_client import super_id_service_client
from data_capture_service.config import settings
from data_capture_service.db import AsyncSessionLocal, get_db
from data_capture_service.schemas.data_capture_schemas import (
    AdapterDataCaptureRequest,
    AdapterInfo,
    AdapterRegistryResponse,
    DataCaptureStartResponse,
    DataCaptureStatusEnum,
)
from data_capture_service.services.baseline_provider import firecrawl_baseline_provider
from data_capture_service.services.data_capture_pipeline import data_capture_pipeline
from data_capture_service.utils.security import validate_token

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/data_capture/adapters",
    tags=["Adapters"],
    dependencies=[Depends(validate_token)],
)


async def _run_single_adapter_background(
    url: str,
    super_id: uuid.UUID,
    adapter_name: str,
    run_id: uuid.UUID,
):
    """Background task for single-adapter data_capture."""
    async with AsyncSessionLocal() as db:
        try:
            await data_capture_pipeline.execute_single_adapter(
                db=db,
                url=url,
                super_id=super_id,
                adapter_name=adapter_name,
                existing_run_id=run_id,
            )
            await db.commit()
        except Exception as e:
            logger.error(
                f"Single adapter ({adapter_name}) background task failed: {e}",
                exc_info=True,
            )
            await db.rollback()


@router.post("/motie", response_model=DataCaptureStartResponse, status_code=202)
async def data_capture_with_motie(
    request: AdapterDataCaptureRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Direct Motie data_capture — still runs baseline + validation for data quality.

    MCP Tool Name: data_capture_with_motie_tool
    """
    if not settings.motie_enabled():
        raise HTTPException(
            status_code=503,
            detail="Motie adapter is not enabled or configured",
        )

    super_id = request.super_id
    if not super_id:
        try:
            super_id = await super_id_service_client.create_super_id(
                description=f"Motie data_capture: {request.url}"
            )
        except Exception as e:
            logger.error(f"Failed to generate Super ID: {e}")
            raise HTTPException(
                status_code=503,
                detail="Super ID service unavailable. Provide a super_id in the request or ensure the Super ID service is running.",
            )

    from data_capture_service.crud import data_capture_run_crud
    from data_capture_service.utils.url_utils import extract_domain

    run = await data_capture_run_crud.create_run(
        db=db,
        super_id=super_id,
        target_url=request.url,
        target_domain=extract_domain(request.url),
        selected_adapter="motie",
        callback_url=request.callback_url,
    )
    await db.commit()

    background_tasks.add_task(
        _run_single_adapter_background,
        url=request.url,
        super_id=super_id,
        adapter_name="motie",
        run_id=run.id,
    )

    return DataCaptureStartResponse(
        run_id=run.id,
        super_id=super_id,
        status=DataCaptureStatusEnum.PENDING,
        poll_url=f"/api/v1/data_capture/runs/{run.id}",
        message="Motie data_capture started",
    )


@router.post("/firecrawl", status_code=200)
async def data_capture_with_firecrawl(
    request: AdapterDataCaptureRequest,
):
    """
    Firecrawl baseline only — quick field presence check.
    Returns synchronously since Firecrawl is fast (~3s).

    MCP Tool Name: data_capture_with_firecrawl_tool
    """
    if not settings.firecrawl_enabled():
        raise HTTPException(
            status_code=503,
            detail="Firecrawl is not enabled (no API key configured)",
        )

    baseline = await firecrawl_baseline_provider.fetch_baseline(request.url)

    return {
        "url": request.url,
        "status": (
            baseline.status.value
            if hasattr(baseline.status, "value")
            else str(baseline.status)
        ),
        "field_presence": baseline.field_presence,
        "image_count": baseline.image_count,
        "has_price": baseline.has_price,
        "has_address": baseline.has_address,
        "has_floorplan": baseline.has_floorplan,
        "duration_ms": baseline.duration_ms,
        "credits_used": baseline.credits_used,
        "error_message": baseline.error_message,
    }


@router.get("/registry", response_model=AdapterRegistryResponse)
async def list_adapters():
    """List all registered data_capture adapters."""
    adapters = []

    # Motie
    adapters.append(
        AdapterInfo(
            name="motie",
            display_name="Motie AI DataCapture",
            provider_type="ai_agent",
            supported_domains=["*"],
            is_enabled=settings.motie_enabled(),
            priority=1,
        )
    )

    # Firecrawl (baseline provider, not a full adapter)
    adapters.append(
        AdapterInfo(
            name="firecrawl",
            display_name="Firecrawl Baseline Provider",
            provider_type="baseline",
            supported_domains=["*"],
            is_enabled=settings.firecrawl_enabled(),
            priority=0,
        )
    )

    return AdapterRegistryResponse(
        adapters=adapters,
        total=len(adapters),
    )
