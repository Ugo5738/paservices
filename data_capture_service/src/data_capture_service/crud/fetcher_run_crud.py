"""
CRUD operations for FetcherRun (V2 per-use audit trail).

After chunk 5 of the V2 SuperID implementation, FetcherRun rows are
immutable: insert once, never update. Iteration / supersession /
fallback chains live in the SuperID Metadata store
(super_id_service.activity_records + link_records). Success / failure
is signalled by `error_message IS NULL` and is set at insert time.

The previous multi-shot helpers (`list_by_parent`, `mark_final`,
`mark_superseded_in_group`) and the `status` column are gone.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.models.fetcher_run import FetcherRun, FetcherType

logger = logging.getLogger(__name__)


async def record(
    db: AsyncSession,
    *,
    fetcher_type: str,
    vendor: str,
    url: str,
    domain: str,
    super_id: Optional[UUID] = None,
    fetcher_id: Optional[UUID] = None,
    ai_fetcher_id: Optional[UUID] = None,
    motie_build_id: Optional[UUID] = None,
    completeness_score: Optional[float] = None,
    payload_json: Optional[Dict[str, Any]] = None,
    fields_json: Optional[Dict[str, Any]] = None,
    field_presence_json: Optional[Dict[str, Any]] = None,
    missing_fields_json: Optional[List[str]] = None,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> FetcherRun:
    """
    Insert one fetcher_runs row for one primitive use of a SuperID.

    The row is finalised at insert time — `finished_at = now()` is set
    eagerly. Success vs failure is signalled by whether `error_message`
    is populated; there is no separate status column.

    Single-use enforcement (chunk 4): the table carries UNIQUE(super_id),
    so a second call with the same super_id raises an IntegrityError.
    Callers should treat that as the principles-compliant "this service
    has used this SuperID before; reject" response and mint a fresh
    SuperID for the retry.
    """
    row = FetcherRun(
        super_id=super_id,
        fetcher_type=fetcher_type,
        vendor=vendor,
        fetcher_id=fetcher_id,
        ai_fetcher_id=ai_fetcher_id,
        motie_build_id=motie_build_id,
        url=url,
        domain=domain,
        completeness_score=completeness_score,
        payload_json=payload_json,
        fields_json=fields_json,
        field_presence_json=field_presence_json,
        missing_fields_json=missing_fields_json,
        error_message=error_message,
        duration_ms=duration_ms,
        metadata_json=metadata_json,
        finished_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


async def get_by_id(db: AsyncSession, run_id: UUID) -> Optional[FetcherRun]:
    """Fetch a fetcher_runs row by its primary key."""
    result = await db.execute(select(FetcherRun).where(FetcherRun.id == run_id))
    return result.scalars().first()


async def get_by_super_id(
    db: AsyncSession, super_id: UUID
) -> Optional[FetcherRun]:
    """
    Fetch the fetcher_runs row for a given super_id.

    Unique by construction (chunk 4 UNIQUE(super_id) constraint), so this
    returns at most one row.
    """
    result = await db.execute(
        select(FetcherRun).where(FetcherRun.super_id == super_id)
    )
    return result.scalars().first()
