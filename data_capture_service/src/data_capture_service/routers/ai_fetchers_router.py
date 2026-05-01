"""
V2 primitive endpoints for AI fetchers.

POST /ai-fetchers/{adapter}/run     — invoke a registered AI fetcher adapter
POST /ai-fetchers/promote-winner    — flip one draft attempt to final, supersede the rest

Adapter selection is DB-driven via ai_fetcher_registry — adding a new vendor
(BrightData, Gemini, ChatGPT, ...) is one INSERT into data_capture.ai_fetchers,
no router code change. There is no `if name == "firecrawl"` branch anywhere.

Every call writes a `data_capture.fetcher_runs` row so WF B's multishot loop
has visible interim attempts (rule 5: interim vs final state).
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.adapters.base import DataCaptureRequest
from data_capture_service.db import get_db
from data_capture_service.models.fetcher_run import FetcherRunKind, FetcherRunStatus
from data_capture_service.schemas.v2_schemas import (
    AIFetcherPromoteRequest,
    AIFetcherPromoteResponse,
    AIFetcherRunRequest,
    AIFetcherRunResponse,
)
from data_capture_service.services import (
    ai_fetcher_registry,
    fetcher_audit,
)
from data_capture_service.utils.security import validate_token
from data_capture_service.utils.url_utils import extract_domain

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ai-fetchers",
    tags=["AI Fetchers V2"],
    dependencies=[Depends(validate_token)],
)


@router.post("/{adapter}/run", response_model=AIFetcherRunResponse)
async def run_ai_fetcher(
    adapter: str,
    request: AIFetcherRunRequest,
    parent_run_id: Optional[UUID] = Query(
        default=None,
        description="Group this attempt with siblings under a parent for "
        "multishot loops (e.g. WF B). Omit on the first attempt; subsequent "
        "attempts pass the first attempt's run_id here.",
    ),
    attempt_number: int = Query(default=1, ge=1),
    loop_start: bool = Query(
        default=False,
        description="Set true on the FIRST attempt of a multishot loop so the "
        "row persists as 'draft' (returnable for later promote-winner) instead "
        "of 'final'. Subsequent attempts use parent_run_id instead.",
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Run an AI fetcher adapter against a URL.

    Single-shot (no parent_run_id, loop_start=false): row is persisted as 'final'.
    Multishot first attempt (loop_start=true): row is persisted as 'draft'; its
    run_id becomes the group identifier subsequent attempts pass as parent_run_id.
    Multishot child attempt (parent_run_id set): row is persisted as 'draft'.

    The parent (e.g. WF B) ends the loop by calling /ai-fetchers/promote-winner
    with parent_run_id and the chosen winner_run_id.
    """
    try:
        ai_row, impl = await ai_fetcher_registry.load_by_name(db, adapter)
    except ai_fetcher_registry.AIFetcherNotRegistered as e:
        available = await ai_fetcher_registry.list_enabled_names(db)
        raise HTTPException(404, f"{e}. Enabled: {available}")
    except ai_fetcher_registry.AIFetcherDisabled as e:
        raise HTTPException(503, str(e))

    super_id_str = str(request.super_id) if request.super_id else None
    domain = extract_domain(request.url)
    in_loop = parent_run_id is not None or loop_start

    try:
        raw = await impl.fetch_raw(
            DataCaptureRequest(
                url=request.url,
                super_id=super_id_str,
                adapter_name=adapter,
                prompt=request.prompt,
                metadata=(
                    {"schema_hint": request.schema_hint}
                    if request.schema_hint
                    else None
                ),
            )
        )
    except Exception as e:
        logger.error(f"AI fetcher {adapter} fetch_raw exception: {e}", exc_info=True)
        if in_loop:
            run = await fetcher_audit.record_loop_attempt(
                db,
                kind=FetcherRunKind.AI.value,
                vendor=adapter,
                url=request.url,
                domain=domain,
                parent_run_id=parent_run_id,
                attempt_number=attempt_number,
                super_id=request.super_id,
                ai_fetcher_id=ai_row.id,
                error_message=str(e),
                succeeded=False,
            )
        else:
            run = await fetcher_audit.record_single_shot_run(
                db,
                kind=FetcherRunKind.AI.value,
                vendor=adapter,
                url=request.url,
                domain=domain,
                super_id=request.super_id,
                ai_fetcher_id=ai_row.id,
                error_message=str(e),
                succeeded=False,
            )
        await db.commit()
        return AIFetcherRunResponse(
            adapter=adapter,
            url=request.url,
            status="failed",
            error_message=str(e),
            run_id=run.id,
            parent_run_id=parent_run_id,
            attempt_number=attempt_number,
        )

    parsed = await impl.parse(raw)
    score = await impl.score(parsed)
    status_str = raw.status.value if hasattr(raw.status, "value") else str(raw.status)
    succeeded = status_str == "success"

    run_kwargs = dict(
        kind=FetcherRunKind.AI.value,
        vendor=adapter,
        url=request.url,
        domain=domain,
        super_id=request.super_id,
        ai_fetcher_id=ai_row.id,
        completeness_score=score.overall,
        payload_json=raw.payload,
        fields_json=parsed.fields,
        field_presence_json=parsed.field_presence,
        missing_fields_json=parsed.missing_fields,
        error_message=raw.error_message or parsed.error_message,
        duration_ms=raw.duration_ms,
        succeeded=succeeded,
    )

    if in_loop:
        run = await fetcher_audit.record_loop_attempt(
            db,
            parent_run_id=parent_run_id,
            attempt_number=attempt_number,
            **run_kwargs,
        )
    else:
        run = await fetcher_audit.record_single_shot_run(db, **run_kwargs)

    await db.commit()

    return AIFetcherRunResponse(
        adapter=adapter,
        url=request.url,
        status=status_str,
        payload=raw.payload,
        fields=parsed.fields,
        field_presence=parsed.field_presence,
        missing_fields=parsed.missing_fields,
        completeness_score=score.overall,
        duration_ms=raw.duration_ms,
        error_message=raw.error_message or parsed.error_message,
        run_id=run.id,
        parent_run_id=parent_run_id,
        attempt_number=attempt_number,
    )


@router.post("/promote-winner", response_model=AIFetcherPromoteResponse)
async def promote_winner(
    request: AIFetcherPromoteRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Promote one draft attempt to 'final' and mark its sibling drafts as
    'superseded'. Used by WF B at the end of its multishot loop to record
    which attempt became the canonical AI-fetcher result for the URL.
    """
    superseded = await fetcher_audit.promote_winner_in_group(
        db,
        parent_run_id=request.parent_run_id,
        winner_run_id=request.winner_run_id,
    )
    await db.commit()
    return AIFetcherPromoteResponse(
        parent_run_id=request.parent_run_id,
        winner_run_id=request.winner_run_id,
        superseded_count=superseded,
    )
