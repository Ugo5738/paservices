"""
CRUD operations for SuperID Metadata store: link records.

Append-only by design. There are no update or delete operations — those are
forbidden by both the application contract and a database trigger (see
migration 674e901b2bd1).

Bidirectional: `super_id_a` / `super_id_b` order is not semantically
meaningful. Queries for "all links involving X" must check both columns.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.link_record import LinkRecord
from ..utils.logging_config import logger


async def create_link_record(
    db: AsyncSession,
    *,
    super_id_a: UUID,
    super_id_b: UUID,
    created_by: str,
    source: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> LinkRecord:
    """
    Insert a single link record. Caller controls the transaction.

    Idempotent insertion is acceptable but not required — duplicate writes
    are stored, not rejected. Interpretation happens at read time.
    """
    record = LinkRecord(
        super_id_a=super_id_a,
        super_id_b=super_id_b,
        created_by=created_by,
        source=source,
        link_metadata=metadata if metadata is not None else {},
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    logger.info(
        "Recorded link between SuperIDs",
        extra={
            "super_id_a": str(super_id_a),
            "super_id_b": str(super_id_b),
            "created_by": created_by,
            "source": source,
            "link_id": str(record.link_id),
        },
    )
    return record


async def list_links_for_super_id(
    db: AsyncSession,
    *,
    super_id: UUID,
    limit: int = 100,
    offset: int = 0,
) -> List[LinkRecord]:
    """
    List link records where `super_id` appears in either `super_id_a` or
    `super_id_b`. Bidirectional by construction; oldest first.
    """
    stmt = (
        select(LinkRecord)
        .where(
            or_(
                LinkRecord.super_id_a == super_id,
                LinkRecord.super_id_b == super_id,
            )
        )
        .order_by(LinkRecord.created_at.asc(), LinkRecord.link_id.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
