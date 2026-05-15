"""
V2 primitive endpoint for AI fetchers.

POST /ai-fetchers/{adapter}/run     — invoke a registered AI fetcher adapter

Adapter selection is DB-driven via ai_fetcher_registry — adding a new
vendor (BrightData, Gemini, ChatGPT, …) is one INSERT into
data_capture.ai_fetchers, no router code change. There is no
`if name == "firecrawl"` branch anywhere.

Every call writes exactly one immutable `data_capture.fetcher_runs` row.
The row is keyed by SuperID (UNIQUE per chunk 4); if the caller passes
a super_id this service has already used the insert raises an
IntegrityError, which is the principles-compliant "this service has
used this SuperID before; reject" response. The caller must mint a
fresh SuperID for a retry.

The previous `parent_run_id` / `attempt_number` / `loop_start` query
parameters and the `/ai-fetchers/promote-winner` endpoint are gone
(chunk 5). Iteration is now expressed as a *new* SuperID per pass plus
a link record connecting it to the prior one — see
docs/data_capture_v2_id_and_data_flow.md.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.adapters.base import DataCaptureRequest
from data_capture_service.clients.super_id_service_client import (
    super_id_service_client,
)
from data_capture_service.db import get_db
from data_capture_service.models.fetcher_run import FetcherType
from data_capture_service.schemas.v2_schemas import (
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
    db: AsyncSession = Depends(get_db),
):
    """
    Run an AI fetcher adapter against a URL.

    The row written to `fetcher_runs` is final and immutable. Success vs
    failure is signalled by `error_message IS NULL`; there is no status
    lifecycle. If `request.super_id` is set and this service has already
    used it, the insert fails with 409 — the caller must mint a fresh
    SuperID and try again (docs/superid_principles.md section 4).
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

    # SuperID Metadata: record this use of the SuperID by the AI fetcher.
    # Non-blocking — failures are logged but don't kill the request
    # (chunk 3 / docs/superid_data_capture_design.md section 3.3).
    if request.super_id:
        await super_id_service_client.record_activity(
            super_id=request.super_id,
            used_by="ai_fetcher_service",
            source="wf_dc_b_aif/service_invocation",
            metadata={"adapter": adapter, "domain": domain},
        )

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
        try:
            run = await fetcher_audit.record_run(
                db,
                fetcher_type=FetcherType.AI.value,
                vendor=adapter,
                url=request.url,
                domain=domain,
                super_id=request.super_id,
                ai_fetcher_id=ai_row.id,
                error_message=str(e),
                succeeded=False,
            )
            await db.commit()
        except IntegrityError as ie:
            await db.rollback()
            logger.warning(
                "AI fetcher run reject: super_id already used by this service",
                extra={"super_id": super_id_str, "adapter": adapter},
            )
            raise HTTPException(
                status_code=409,
                detail=(
                    "super_id has already been used by the AI fetcher service. "
                    "Mint a new super_id and retry (principles section 4)."
                ),
            ) from ie
        return AIFetcherRunResponse(
            adapter=adapter,
            url=request.url,
            status="failed",
            error_message=str(e),
            run_id=run.id,
        )

    parsed = await impl.parse(raw)
    score = await impl.score(parsed)
    status_str = raw.status.value if hasattr(raw.status, "value") else str(raw.status)
    succeeded = status_str == "success"

    try:
        run = await fetcher_audit.record_run(
            db,
            fetcher_type=FetcherType.AI.value,
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
        await db.commit()
    except IntegrityError as ie:
        await db.rollback()
        logger.warning(
            "AI fetcher run reject: super_id already used by this service",
            extra={"super_id": super_id_str, "adapter": adapter},
        )
        raise HTTPException(
            status_code=409,
            detail=(
                "super_id has already been used by the AI fetcher service. "
                "Mint a new super_id and retry (principles section 4)."
            ),
        ) from ie

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
    )
