"""
V2 primitive endpoints for AI fetchers.

POST /ai-fetchers/{adapter}/run — invoke a registered AI fetcher adapter

The adapter slot is pluggable: 'firecrawl' is the only registered adapter today.
Adding a new AI fetcher (BrightData, Gemini, etc.) is a new entry in
_AI_ADAPTERS plus the adapter implementation behind DataCaptureAdapter Protocol.
"""

import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException

from data_capture_service.adapters.base import DataCaptureAdapter, DataCaptureRequest
from data_capture_service.adapters.firecrawl import firecrawl_adapter
from data_capture_service.config import settings
from data_capture_service.schemas.v2_schemas import (
    AIFetcherRunRequest,
    AIFetcherRunResponse,
)
from data_capture_service.utils.security import validate_token

logger = logging.getLogger(__name__)

# Registered AI fetcher adapters. Keys are the {adapter} slug used in URLs.
_AI_ADAPTERS: Dict[str, DataCaptureAdapter] = {
    "firecrawl": firecrawl_adapter,
}


def _adapter_enabled(name: str) -> bool:
    if name == "firecrawl":
        return settings.firecrawl_enabled()
    # Future adapters carry their own enable flag.
    return True


router = APIRouter(
    prefix="/ai-fetchers",
    tags=["AI Fetchers V2"],
    dependencies=[Depends(validate_token)],
)


@router.post("/{adapter}/run", response_model=AIFetcherRunResponse)
async def run_ai_fetcher(adapter: str, request: AIFetcherRunRequest):
    """
    Run an AI fetcher adapter against a URL.

    Single-shot: no looping, no retries — the parent (e.g. WF B) drives multishot.
    No fail branch in the contract: the response always carries whatever was
    captured. Score and presence are returned so the parent can decide what to
    do next.
    """
    if adapter not in _AI_ADAPTERS:
        raise HTTPException(
            404,
            f"AI fetcher '{adapter}' not registered. Available: {list(_AI_ADAPTERS)}",
        )
    if not _adapter_enabled(adapter):
        raise HTTPException(503, f"AI fetcher '{adapter}' is disabled")

    impl = _AI_ADAPTERS[adapter]
    super_id_str = str(request.super_id) if request.super_id else None

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
        return AIFetcherRunResponse(
            adapter=adapter,
            url=request.url,
            status="failed",
            error_message=str(e),
        )

    parsed = await impl.parse(raw)
    score = await impl.score(parsed)

    status_str = raw.status.value if hasattr(raw.status, "value") else str(raw.status)

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
    )
