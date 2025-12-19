from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.analysis_update import AnalysisUpdate


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        candidate = value.strip()
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            return None
    return None


async def create_analysis_update(
    db: AsyncSession,
    raw_payload: Dict[str, Any],
) -> AnalysisUpdate:
    """Insert an append-only AnalysisUpdate row from an arbitrary callback payload."""
    update = AnalysisUpdate(
        super_id=str(raw_payload.get("super_id") or ""),
        status=raw_payload.get("status"),
        context=raw_payload.get("context"),
        event_timestamp=_parse_dt(raw_payload.get("timestamp")),
        summary=raw_payload.get("summary"),
        metadata_=raw_payload.get("metadata"),
        data_location=raw_payload.get("data_location"),
        final_result=raw_payload.get("final_result"),
        error=raw_payload.get("error"),
        raw_payload=raw_payload,
    )
    db.add(update)
    await db.flush()
    return update


async def list_analysis_updates(
    db: AsyncSession,
    super_id: str,
    *,
    limit: int = 50,
) -> List[AnalysisUpdate]:
    stmt = (
        select(AnalysisUpdate)
        .where(AnalysisUpdate.super_id == super_id)
        .order_by(desc(AnalysisUpdate.received_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
