"""
CRUD operations for DataCaptureUsage model.
"""

import uuid
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.models.data_capture_usage import DataCaptureUsage


async def record_usage(
    db: AsyncSession,
    run_id: uuid.UUID,
    adapter_name: str,
    operation: str,
    step_id: Optional[uuid.UUID] = None,
    credits_used: float = 0.0,
    request_count: int = 0,
    response_bytes: int = 0,
    metadata_json: Optional[Dict[str, Any]] = None,
    super_id: Optional[uuid.UUID] = None,
) -> DataCaptureUsage:
    """Record usage/cost data for a data_capture operation."""
    usage = DataCaptureUsage(
        id=uuid.uuid4(),
        run_id=run_id,
        step_id=step_id,
        adapter_name=adapter_name,
        operation=operation,
        credits_used=credits_used,
        request_count=request_count,
        response_bytes=response_bytes,
        metadata_json=metadata_json,
        super_id=super_id,
    )
    db.add(usage)
    await db.flush()
    return usage
