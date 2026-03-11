"""
CRUD operations for CanonicalPropertySnapshot and CanonicalMedia models.
"""

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from data_capture_service.models.canonical_media import CanonicalMedia
from data_capture_service.models.canonical_property_snapshot import (
    CanonicalPropertySnapshot,
)


async def create_snapshot(
    db: AsyncSession,
    run_id: uuid.UUID,
    super_id: uuid.UUID,
    source_adapter: str,
    source_url: str,
    completeness_score: Optional[float] = None,
    column_fields: Optional[Dict[str, Any]] = None,
    extras_json: Optional[Dict[str, Any]] = None,
) -> CanonicalPropertySnapshot:
    """Create a canonical property snapshot."""
    snapshot = CanonicalPropertySnapshot(
        id=uuid.uuid4(),
        run_id=run_id,
        super_id=super_id,
        source_adapter=source_adapter,
        source_url=source_url,
        completeness_score=completeness_score,
        extras_json=extras_json,
    )

    # Set column fields (Priority 0-3)
    if column_fields:
        for field_name, value in column_fields.items():
            if hasattr(snapshot, field_name) and value is not None:
                setattr(snapshot, field_name, value)

    db.add(snapshot)
    await db.flush()
    return snapshot


async def create_media_records(
    db: AsyncSession,
    snapshot_id: uuid.UUID,
    super_id: uuid.UUID,
    media_items: List[Dict[str, Any]],
) -> List[CanonicalMedia]:
    """Create canonical media records for a snapshot."""
    records = []
    for item in media_items:
        media = CanonicalMedia(
            id=uuid.uuid4(),
            snapshot_id=snapshot_id,
            super_id=super_id,
            media_type=item.get("media_type", "photo"),
            url=item["url"],
            caption=item.get("caption"),
            sort_order=item.get("sort_order", 0),
            is_high_res=item.get("is_high_res", False),
            width=item.get("width"),
            height=item.get("height"),
        )
        db.add(media)
        records.append(media)

    await db.flush()
    return records


async def get_snapshot_by_run(
    db: AsyncSession, run_id: uuid.UUID
) -> Optional[CanonicalPropertySnapshot]:
    """Get canonical snapshot for a run."""
    stmt = select(CanonicalPropertySnapshot).where(
        CanonicalPropertySnapshot.run_id == run_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_snapshot_with_media(
    db: AsyncSession, snapshot_id: uuid.UUID
) -> Optional[CanonicalPropertySnapshot]:
    """Get canonical snapshot with media eagerly loaded."""
    stmt = (
        select(CanonicalPropertySnapshot)
        .where(CanonicalPropertySnapshot.id == snapshot_id)
        .options(selectinload(CanonicalPropertySnapshot.media))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
