"""CRUD helpers for workflow status tracking in the Rightmove service."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_rightmove_service.models import WorkflowStatus


async def list_statuses(
    db: AsyncSession, *, super_id: UUID
) -> List[WorkflowStatus]:
    stmt = (
        select(WorkflowStatus)
        .where(WorkflowStatus.super_id == super_id)
        .order_by(WorkflowStatus.context)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_status(
    db: AsyncSession, *, super_id: UUID, context: str
) -> Optional[WorkflowStatus]:
    stmt = select(WorkflowStatus).where(
        WorkflowStatus.super_id == super_id,
        WorkflowStatus.context == context,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def upsert_status(
    db: AsyncSession,
    *,
    super_id: UUID,
    context: str,
    property_id: Optional[str] = None,
    status: str,
    stage: Optional[str] = None,
    progress: Optional[float] = None,
    data_location: Optional[str] = None,
    last_error: Optional[str] = None,
) -> WorkflowStatus:
    record = await get_status(db, super_id=super_id, context=context)
    if record is None:
        record = WorkflowStatus(
            super_id=super_id,
            context=context,
            property_id=property_id,
            status=status,
            stage=stage,
            progress=progress,
            data_location=data_location,
            last_error=last_error,
        )
        db.add(record)
    else:
        record.status = status
        if stage is not None:
            record.stage = stage
        if progress is not None:
            record.progress = progress
        if data_location is not None:
            record.data_location = data_location
        if last_error is not None:
            record.last_error = last_error
        if property_id:
            record.property_id = property_id

    await db.flush()
    await db.refresh(record)
    return record
