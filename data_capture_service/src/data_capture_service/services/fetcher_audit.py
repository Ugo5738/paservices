"""
Fetcher Audit — thin convenience layer over fetcher_run_crud.

Centralises the "create a fetcher_runs row" logic so the routers don't have
to know the column names directly. Also handles the idiom WF B uses for
multishot:

    parent_run_id = await begin_attempt_group(db, ...)
    for attempt in 1..N:
        run = await record_attempt(db, parent_run_id=parent_run_id, ...)
    await promote_winner(db, parent_run_id, run.id)

The router layer can ignore parent_run_id entirely for single-shot calls
(WF1 path) — the helper just creates a finalised row in that case.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.crud import fetcher_run_crud
from data_capture_service.models.fetcher_run import (
    FetcherRun,
    FetcherRunKind,
    FetcherRunStatus,
)

logger = logging.getLogger(__name__)


async def record_single_shot_run(
    db: AsyncSession,
    *,
    kind: str,
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
    succeeded: bool = True,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> FetcherRun:
    """
    Persist one V2 primitive call as a final/failed row.

    Used by WF1 (coded fetcher) and WF C / W3 internals — anything that's
    not part of a multishot loop.
    """
    status = FetcherRunStatus.FINAL.value if succeeded else FetcherRunStatus.FAILED.value
    return await fetcher_run_crud.record(
        db,
        kind=kind,
        vendor=vendor,
        url=url,
        domain=domain,
        status=status,
        super_id=super_id,
        fetcher_id=fetcher_id,
        ai_fetcher_id=ai_fetcher_id,
        motie_build_id=motie_build_id,
        completeness_score=completeness_score,
        payload_json=payload_json,
        fields_json=fields_json,
        field_presence_json=field_presence_json,
        missing_fields_json=missing_fields_json,
        error_message=error_message,
        duration_ms=duration_ms,
        metadata_json=metadata_json,
    )


async def record_loop_attempt(
    db: AsyncSession,
    *,
    kind: str,
    vendor: str,
    url: str,
    domain: str,
    parent_run_id: Optional[UUID],
    attempt_number: int,
    super_id: Optional[UUID] = None,
    ai_fetcher_id: Optional[UUID] = None,
    fetcher_id: Optional[UUID] = None,
    completeness_score: Optional[float] = None,
    payload_json: Optional[Dict[str, Any]] = None,
    fields_json: Optional[Dict[str, Any]] = None,
    field_presence_json: Optional[Dict[str, Any]] = None,
    missing_fields_json: Optional[List[str]] = None,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
    succeeded: bool = True,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> FetcherRun:
    """
    Persist one attempt within a multishot group (WF B's AI-fetcher loop).

    Status defaults to 'draft' on success (so a winner can later be promoted)
    and 'failed' otherwise. Use promote_winner_in_group to flip the chosen
    attempt to 'final' and supersede the rest.
    """
    status = FetcherRunStatus.DRAFT.value if succeeded else FetcherRunStatus.FAILED.value
    return await fetcher_run_crud.record(
        db,
        kind=kind,
        vendor=vendor,
        url=url,
        domain=domain,
        status=status,
        super_id=super_id,
        fetcher_id=fetcher_id,
        ai_fetcher_id=ai_fetcher_id,
        parent_run_id=parent_run_id,
        attempt_number=attempt_number,
        completeness_score=completeness_score,
        payload_json=payload_json,
        fields_json=fields_json,
        field_presence_json=field_presence_json,
        missing_fields_json=missing_fields_json,
        error_message=error_message,
        duration_ms=duration_ms,
        metadata_json=metadata_json,
    )


async def promote_winner_in_group(
    db: AsyncSession,
    *,
    parent_run_id: UUID,
    winner_run_id: UUID,
) -> int:
    """
    Promote one attempt to 'final' and supersede the rest.

    Returns the number of rows superseded (excluding the winner). Idempotent:
    re-promoting the same winner is a no-op (the winner is already final and
    the others are already superseded).
    """
    await fetcher_run_crud.mark_final(db, winner_run_id)
    superseded = await fetcher_run_crud.mark_superseded_in_group(
        db, parent_run_id, exclude_id=winner_run_id
    )
    return superseded
