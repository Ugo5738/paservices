"""Workflow status endpoints for orchestration tooling."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_rightmove_service.crud.workflow_status_crud import (
    get_status,
    list_statuses,
    upsert_status,
)
from data_capture_rightmove_service.db import get_db
from data_capture_rightmove_service.schemas.workflow_status import (
    WorkflowStatusResponse,
    WorkflowStatusUpsertRequest,
)

router = APIRouter(prefix="/workflow-status", tags=["Workflow Status"])


@router.get("/{super_id}", response_model=List[WorkflowStatusResponse])
async def list_workflow_statuses(
    super_id: UUID, db: AsyncSession = Depends(get_db)
) -> List[WorkflowStatusResponse]:
    return await list_statuses(db, super_id=super_id)


@router.get(
    "/{super_id}/{context}",
    response_model=WorkflowStatusResponse,
)
async def read_workflow_status(
    super_id: UUID, context: str, db: AsyncSession = Depends(get_db)
) -> WorkflowStatusResponse:
    record = await get_status(db, super_id=super_id, context=context)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"No workflow status found for super_id={super_id} context={context}",
        )
    return record


@router.put("/", response_model=WorkflowStatusResponse)
async def upsert_workflow_status_endpoint(
    payload: WorkflowStatusUpsertRequest, db: AsyncSession = Depends(get_db)
) -> WorkflowStatusResponse:
    return await upsert_status(
        db,
        super_id=payload.super_id,
        context=payload.context,
        property_id=payload.property_id,
        status=payload.status,
        stage=payload.stage,
        progress=payload.progress,
        data_location=payload.data_location,
        last_error=payload.last_error,
    )
