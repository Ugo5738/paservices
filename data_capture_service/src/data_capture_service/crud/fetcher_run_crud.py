"""
CRUD operations for FetcherRun (V2 primitive run audit trail).

Every /fetchers/run and /ai-fetchers/{name}/run call should persist a row.
WF B's multishot loop creates several `draft` rows that share a parent_run_id;
the workflow promotes the winning attempt to `final` and supersedes the rest.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.models.fetcher_run import (
    FetcherRun,
    FetcherRunKind,
    FetcherRunStatus,
)

logger = logging.getLogger(__name__)


async def record(
    db: AsyncSession,
    *,
    kind: str,
    vendor: str,
    url: str,
    domain: str,
    status: str = FetcherRunStatus.DRAFT.value,
    super_id: Optional[UUID] = None,
    fetcher_id: Optional[UUID] = None,
    ai_fetcher_id: Optional[UUID] = None,
    motie_build_id: Optional[UUID] = None,
    parent_run_id: Optional[UUID] = None,
    attempt_number: int = 1,
    completeness_score: Optional[float] = None,
    payload_json: Optional[Dict[str, Any]] = None,
    fields_json: Optional[Dict[str, Any]] = None,
    field_presence_json: Optional[Dict[str, Any]] = None,
    missing_fields_json: Optional[List[str]] = None,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
    metadata_json: Optional[Dict[str, Any]] = None,
    finished: bool = True,
) -> FetcherRun:
    """
    Insert a fetcher_runs row for one primitive attempt.

    `finished=True` (the default) sets finished_at=now, since most callers
    record a completed call. Set finished=False for in-flight rows; mark them
    finished later via mark_finished.
    """
    row = FetcherRun(
        parent_run_id=parent_run_id,
        super_id=super_id,
        kind=kind,
        vendor=vendor,
        fetcher_id=fetcher_id,
        ai_fetcher_id=ai_fetcher_id,
        motie_build_id=motie_build_id,
        url=url,
        domain=domain,
        attempt_number=attempt_number,
        status=status,
        completeness_score=completeness_score,
        payload_json=payload_json,
        fields_json=fields_json,
        field_presence_json=field_presence_json,
        missing_fields_json=missing_fields_json,
        error_message=error_message,
        duration_ms=duration_ms,
        metadata_json=metadata_json,
        finished_at=datetime.now(timezone.utc) if finished else None,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


async def get_by_id(db: AsyncSession, run_id: UUID) -> Optional[FetcherRun]:
    result = await db.execute(select(FetcherRun).where(FetcherRun.id == run_id))
    return result.scalars().first()


async def list_by_parent(
    db: AsyncSession, parent_run_id: UUID
) -> List[FetcherRun]:
    """Return all attempts grouped under a parent (oldest first)."""
    result = await db.execute(
        select(FetcherRun)
        .where(FetcherRun.parent_run_id == parent_run_id)
        .order_by(FetcherRun.attempt_number.asc(), FetcherRun.started_at.asc())
    )
    return list(result.scalars().all())


async def mark_final(db: AsyncSession, run_id: UUID) -> Optional[FetcherRun]:
    """Promote a draft to final."""
    await db.execute(
        update(FetcherRun)
        .where(FetcherRun.id == run_id)
        .values(status=FetcherRunStatus.FINAL.value)
    )
    await db.flush()
    return await get_by_id(db, run_id)


async def mark_superseded_in_group(
    db: AsyncSession, parent_run_id: UUID, exclude_id: UUID
) -> int:
    """
    Mark every draft in the group as superseded EXCEPT exclude_id (the winner).

    The "group" is identified by parent_run_id. WF B's first-attempt row has
    parent_run_id IS NULL but its own id is what later attempts use as
    parent_run_id, so to catch it we also match rows where id = parent_run_id.

    Returns the number of rows updated.
    """
    result = await db.execute(
        update(FetcherRun)
        .where(
            or_(
                FetcherRun.parent_run_id == parent_run_id,
                FetcherRun.id == parent_run_id,
            ),
            FetcherRun.id != exclude_id,
            FetcherRun.status == FetcherRunStatus.DRAFT.value,
        )
        .values(status=FetcherRunStatus.SUPERSEDED.value)
    )
    await db.flush()
    return result.rowcount or 0


async def mark_finished(
    db: AsyncSession,
    run_id: UUID,
    *,
    status: Optional[str] = None,
    completeness_score: Optional[float] = None,
    payload_json: Optional[Dict[str, Any]] = None,
    fields_json: Optional[Dict[str, Any]] = None,
    field_presence_json: Optional[Dict[str, Any]] = None,
    missing_fields_json: Optional[List[str]] = None,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> Optional[FetcherRun]:
    """Update an in-flight row with the run outcome."""
    values: Dict[str, Any] = {"finished_at": datetime.now(timezone.utc)}
    if status is not None:
        values["status"] = status
    if completeness_score is not None:
        values["completeness_score"] = completeness_score
    if payload_json is not None:
        values["payload_json"] = payload_json
    if fields_json is not None:
        values["fields_json"] = fields_json
    if field_presence_json is not None:
        values["field_presence_json"] = field_presence_json
    if missing_fields_json is not None:
        values["missing_fields_json"] = missing_fields_json
    if error_message is not None:
        values["error_message"] = error_message
    if duration_ms is not None:
        values["duration_ms"] = duration_ms

    await db.execute(
        update(FetcherRun).where(FetcherRun.id == run_id).values(**values)
    )
    await db.flush()
    return await get_by_id(db, run_id)
