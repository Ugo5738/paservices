"""
CRUD operations for DataCaptureRun model.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from data_capture_service.models.data_capture_run import DataCaptureRun, DataCaptureRunMode, DataCaptureRunStatus


async def create_run(
    db: AsyncSession,
    super_id: uuid.UUID,
    target_url: str,
    target_domain: str,
    mode: DataCaptureRunMode = DataCaptureRunMode.ORCHESTRATED,
    selected_adapter: Optional[str] = None,
) -> DataCaptureRun:
    """Create a new data_capture run record."""
    run = DataCaptureRun(
        id=uuid.uuid4(),
        super_id=super_id,
        target_url=target_url,
        target_domain=target_domain,
        mode=mode,
        selected_adapter=selected_adapter,
        status=DataCaptureRunStatus.PENDING,
    )
    db.add(run)
    await db.flush()
    return run


async def update_run_status(
    db: AsyncSession,
    run_id: uuid.UUID,
    status: DataCaptureRunStatus,
    completeness_score: Optional[float] = None,
    error_message: Optional[str] = None,
    selected_adapter: Optional[str] = None,
    fallback_count: Optional[int] = None,
    route_decision_json: Optional[dict] = None,
) -> Optional[DataCaptureRun]:
    """Update the status and optional fields of a data_capture run."""
    run = await db.get(DataCaptureRun, run_id)
    if not run:
        return None

    run.status = status

    if completeness_score is not None:
        run.completeness_score = completeness_score
    if error_message is not None:
        run.error_message = error_message
    if selected_adapter is not None:
        run.selected_adapter = selected_adapter
    if fallback_count is not None:
        run.fallback_count = fallback_count
    if route_decision_json is not None:
        run.route_decision_json = route_decision_json

    # Set finished_at for terminal states
    if status in (
        DataCaptureRunStatus.COMPLETED,
        DataCaptureRunStatus.FAILED,
        DataCaptureRunStatus.COMPLETED_WITH_WARNINGS,
    ):
        run.finished_at = datetime.now(timezone.utc)

    await db.flush()
    return run


async def get_run(db: AsyncSession, run_id: uuid.UUID) -> Optional[DataCaptureRun]:
    """Get a data_capture run by ID."""
    return await db.get(DataCaptureRun, run_id)


async def get_run_with_steps(
    db: AsyncSession, run_id: uuid.UUID
) -> Optional[DataCaptureRun]:
    """Get a data_capture run with all its steps eagerly loaded."""
    stmt = (
        select(DataCaptureRun)
        .where(DataCaptureRun.id == run_id)
        .options(selectinload(DataCaptureRun.steps))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
