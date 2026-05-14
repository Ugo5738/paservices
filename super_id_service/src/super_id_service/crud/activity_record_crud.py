"""
CRUD operations for SuperID Metadata store: activity records.

Append-only by design. There are no update or delete operations — those are
forbidden by both the application contract and a database trigger (see
migration 674e901b2bd1).
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.activity_record import ActivityRecord
from ..utils.logging_config import logger


async def create_activity_record(
    db: AsyncSession,
    *,
    super_id: UUID,
    used_by: str,
    source: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> ActivityRecord:
    """
    Insert a single activity record. Caller controls the transaction.

    Idempotent insertion is acceptable but not required — duplicate writes
    are stored, not rejected. Interpretation happens at read time.
    """
    record = ActivityRecord(
        super_id=super_id,
        used_by=used_by,
        source=source,
        activity_metadata=metadata if metadata is not None else {},
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    logger.info(
        "Recorded activity for super_id",
        extra={
            "super_id": str(super_id),
            "used_by": used_by,
            "source": source,
            "activity_id": str(record.activity_id),
        },
    )
    return record


async def list_activity_for_super_id(
    db: AsyncSession,
    *,
    super_id: UUID,
    limit: int = 100,
    offset: int = 0,
) -> List[ActivityRecord]:
    """List activity records for a given SuperID, oldest first."""
    stmt = (
        select(ActivityRecord)
        .where(ActivityRecord.super_id == super_id)
        .order_by(ActivityRecord.used_at.asc(), ActivityRecord.activity_id.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
