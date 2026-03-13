"""
Orchestrated data_capture endpoints.

POST /data_capture/start          — Start orchestrated pipeline (202 Accepted, background task)
GET  /data_capture/runs/{run_id}  — Poll run status
GET  /data_capture/runs/{run_id}/result — Get canonical result
POST /data_capture/runs/{run_id}/retry  — Retry failed run
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.clients.super_id_service_client import super_id_service_client
from data_capture_service.config import settings
from data_capture_service.crud import canonical_crud, data_capture_run_crud
from data_capture_service.db import AsyncSessionLocal, get_db
from data_capture_service.models.data_capture_run import DataCaptureRunStatus
from data_capture_service.schemas.data_capture_schemas import (
    CanonicalSnapshotResponse,
    DataCaptureResultResponse,
    DataCaptureRunStatusResponse,
    DataCaptureStartRequest,
    DataCaptureStartResponse,
    DataCaptureStatusEnum,
    MediaItem,
    QualityReport,
    StepInfo,
    StepStatusEnum,
    StepTypeEnum,
)
from data_capture_service.services.data_capture_pipeline import data_capture_pipeline
from data_capture_service.utils.security import validate_token

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/data_capture",
    tags=["DataCapture"],
    dependencies=[Depends(validate_token)],
)


async def _run_pipeline_background(
    url: str,
    super_id: uuid.UUID,
    skip_baseline: bool = False,
):
    """Background task that runs the full data_capture pipeline."""
    async with AsyncSessionLocal() as db:
        try:
            await data_capture_pipeline.execute(
                db=db,
                url=url,
                super_id=super_id,
                skip_baseline=skip_baseline,
            )
            await db.commit()
        except Exception as e:
            logger.error(f"Pipeline background task failed: {e}", exc_info=True)
            await db.rollback()


@router.post("/start", response_model=DataCaptureStartResponse, status_code=202)
async def start_data_capture(
    request: DataCaptureStartRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Start an orchestrated data_capture pipeline.

    Returns 202 Accepted immediately with a run_id for polling.
    The pipeline runs in the background:
    1. Firecrawl baseline (if enabled)
    2. Adapter chain (motie_existing → motie_build)
    3. Validation gate
    4. Canonical storage
    """
    # Generate super_id if not provided
    super_id = request.super_id
    if not super_id:
        try:
            super_id = await super_id_service_client.create_super_id(
                description=f"DataCapture: {request.url}"
            )
        except Exception as e:
            logger.error(f"Failed to generate Super ID: {e}")
            raise HTTPException(
                status_code=503,
                detail="Super ID service unavailable. Provide a super_id in the request or ensure the Super ID service is running.",
            )

    # Create the run record synchronously so we can return the run_id
    from data_capture_service.utils.url_utils import extract_domain

    run = await data_capture_run_crud.create_run(
        db=db,
        super_id=super_id,
        target_url=request.url,
        target_domain=extract_domain(request.url),
    )
    await db.commit()

    # Launch pipeline in background
    background_tasks.add_task(
        _run_pipeline_background,
        url=request.url,
        super_id=super_id,
        skip_baseline=request.skip_baseline,
    )

    return DataCaptureStartResponse(
        run_id=run.id,
        super_id=super_id,
        status=DataCaptureStatusEnum.PENDING,
        poll_url=f"/api/v1/data_capture/runs/{run.id}",
        message="DataCapture pipeline started",
    )


@router.get("/runs/{run_id}", response_model=DataCaptureRunStatusResponse)
async def get_run_status(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Poll the status of a data_capture run."""
    run = await data_capture_run_crud.get_run_with_steps(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    steps = []
    for step in sorted(run.steps, key=lambda s: s.step_order):
        steps.append(
            StepInfo(
                step_order=step.step_order,
                adapter_name=step.adapter_name,
                step_type=StepTypeEnum(step.step_type.value),
                status=StepStatusEnum(step.status.value),
                completeness_score=step.completeness_score,
                error_message=step.error_message,
                duration_ms=step.duration_ms,
                provider_run_id=step.provider_run_id,
            )
        )

    return DataCaptureRunStatusResponse(
        run_id=run.id,
        super_id=run.super_id,
        status=DataCaptureStatusEnum(run.status.value),
        target_url=run.target_url,
        target_domain=run.target_domain,
        selected_adapter=run.selected_adapter,
        completeness_score=run.completeness_score,
        fallback_count=run.fallback_count,
        error_message=run.error_message,
        steps=steps,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


@router.get("/runs/{run_id}/result", response_model=DataCaptureResultResponse)
async def get_run_result(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get the canonical result of a completed data_capture run."""
    run = await data_capture_run_crud.get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    if run.status not in (
        DataCaptureRunStatus.COMPLETED,
        DataCaptureRunStatus.COMPLETED_WITH_WARNINGS,
    ):
        raise HTTPException(
            status_code=409,
            detail=f"Run is not complete (status={run.status.value})",
        )

    snapshot = await canonical_crud.get_snapshot_by_run(db, run_id)
    if not snapshot:
        raise HTTPException(
            status_code=404,
            detail=f"No canonical snapshot found for run {run_id}",
        )

    # Load media
    snapshot_with_media = await canonical_crud.get_snapshot_with_media(db, snapshot.id)

    canonical = CanonicalSnapshotResponse(
        address_road=snapshot.address_road,
        price=snapshot.price,
        price_text=snapshot.price_text,
        source_url=snapshot.source_url,
        address_town=snapshot.address_town,
        bedrooms=snapshot.bedrooms,
        estate_agent_name=snapshot.estate_agent_name,
        agent_address=snapshot.agent_address,
        transaction_type=snapshot.transaction_type,
        bathrooms=snapshot.bathrooms,
        property_type=snapshot.property_type,
        full_address=snapshot.full_address,
        postcode=snapshot.postcode,
        description=snapshot.description,
        rightmove_url=snapshot.rightmove_url,
        extras=snapshot.extras_json,
    )

    media = []
    if snapshot_with_media and snapshot_with_media.media:
        for m in snapshot_with_media.media:
            media.append(
                MediaItem(
                    media_type=m.media_type,
                    url=m.url,
                    caption=m.caption,
                    sort_order=m.sort_order,
                    is_high_res=m.is_high_res,
                    width=m.width,
                    height=m.height,
                )
            )

    quality = QualityReport(
        completeness_score=snapshot.completeness_score or 0.0,
        priority_scores=(
            run.route_decision_json.get("priority_scores", {})
            if run.route_decision_json
            else {}
        ),
        fields_present=(
            run.route_decision_json.get("fields_present", 0)
            if run.route_decision_json
            else 0
        ),
        fields_total=(
            run.route_decision_json.get("fields_total", 0)
            if run.route_decision_json
            else 0
        ),
        baseline_available=True,  # Simplified — refine if needed
    )

    return DataCaptureResultResponse(
        run_id=run.id,
        super_id=run.super_id,
        status=DataCaptureStatusEnum(run.status.value),
        source_adapter=snapshot.source_adapter,
        canonical=canonical,
        media=media,
        quality=quality,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


@router.post(
    "/runs/{run_id}/retry", response_model=DataCaptureStartResponse, status_code=202
)
async def retry_run(
    run_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Retry a failed data_capture run."""
    run = await data_capture_run_crud.get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    if run.status not in (
        DataCaptureRunStatus.FAILED,
        DataCaptureRunStatus.COMPLETED_WITH_WARNINGS,
    ):
        raise HTTPException(
            status_code=409,
            detail=f"Can only retry failed or warning runs (status={run.status.value})",
        )

    # Create a new run for the retry
    new_run = await data_capture_run_crud.create_run(
        db=db,
        super_id=run.super_id,
        target_url=run.target_url,
        target_domain=run.target_domain,
    )
    await db.commit()

    background_tasks.add_task(
        _run_pipeline_background,
        url=run.target_url,
        super_id=run.super_id,
    )

    return DataCaptureStartResponse(
        run_id=new_run.id,
        super_id=run.super_id,
        status=DataCaptureStatusEnum.PENDING,
        poll_url=f"/api/v1/data_capture/runs/{new_run.id}",
        message=f"Retry started (original run: {run_id})",
    )
