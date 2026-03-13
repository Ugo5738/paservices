"""
CRUD operations for DataCaptureRunStep model.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.models.data_capture_run_step import (
    DataCaptureRunStep,
    StepStatus,
    StepType,
)


async def create_step(
    db: AsyncSession,
    run_id: uuid.UUID,
    step_order: int,
    adapter_name: str,
    step_type: StepType,
    provider_type: Optional[str] = None,
    super_id: Optional[uuid.UUID] = None,
) -> DataCaptureRunStep:
    """Create a new step record for a data_capture run."""
    step = DataCaptureRunStep(
        id=uuid.uuid4(),
        run_id=run_id,
        step_order=step_order,
        adapter_name=adapter_name,
        step_type=step_type,
        provider_type=provider_type,
        status=StepStatus.PENDING,
        started_at=datetime.now(timezone.utc),
        super_id=super_id,
    )
    db.add(step)
    await db.flush()
    return step


async def update_step(
    db: AsyncSession,
    step_id: uuid.UUID,
    status: Optional[StepStatus] = None,
    completeness_score: Optional[float] = None,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
    provider_run_id: Optional[str] = None,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> Optional[DataCaptureRunStep]:
    """Update fields on an existing step."""
    step = await db.get(DataCaptureRunStep, step_id)
    if not step:
        return None

    if status is not None:
        step.status = status
    if completeness_score is not None:
        step.completeness_score = completeness_score
    if error_message is not None:
        step.error_message = error_message
    if duration_ms is not None:
        step.duration_ms = duration_ms
    if provider_run_id is not None:
        step.provider_run_id = provider_run_id
    if metadata_json is not None:
        step.metadata_json = metadata_json

    # Set finished_at for terminal states
    if status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED):
        step.finished_at = datetime.now(timezone.utc)

    await db.flush()
    return step
