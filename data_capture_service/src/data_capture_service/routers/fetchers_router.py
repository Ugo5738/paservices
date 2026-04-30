"""
V2 primitive endpoints for coded fetchers.

POST /fetchers/lookup    — registry lookup by URL/domain
POST /fetchers/run       — invoke a registered fetcher against a URL
POST /fetchers/validate  — validate captured data against the baseline schema

These primitives are stateless and take no orchestration decisions. n8n owns
the routing/looping logic.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.adapters.motie.motie_parser import parse_motie_result
from data_capture_service.config import settings
from data_capture_service.crud import fetcher_crud
from data_capture_service.db import get_db
from data_capture_service.schemas.v2_schemas import (
    FetcherInfo,
    FetcherLookupRequest,
    FetcherLookupResponse,
    FetcherRunRequest,
    FetcherRunResponse,
    FetcherValidateRequest,
    FetcherValidateResponse,
)
from data_capture_service.services.fetcher_runner import run_fetcher
from data_capture_service.services.field_registry import (
    compute_completeness_score,
    compute_field_presence,
    get_missing_critical_fields,
)
from data_capture_service.utils.security import validate_token
from data_capture_service.utils.url_utils import extract_domain

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/fetchers",
    tags=["Fetchers V2"],
    dependencies=[Depends(validate_token)],
)


async def _build_info(db: AsyncSession, fetcher) -> FetcherInfo:
    api_url = await fetcher_crud.resolve_api_url(db, fetcher)
    return FetcherInfo(
        id=fetcher.id,
        domain=fetcher.domain,
        source_type=fetcher.source_type,
        route_path=fetcher.route_path,
        http_method=fetcher.http_method,
        api_url=api_url,
        param_schema=fetcher.param_schema or {},
        is_metered=fetcher.is_metered,
        status=fetcher.status,
        motie_project_uuid=fetcher.motie_project_uuid,
    )


@router.post("/lookup", response_model=FetcherLookupResponse)
async def lookup_fetcher(
    request: FetcherLookupRequest,
    db: AsyncSession = Depends(get_db),
):
    """Look up the active fetcher for the URL's domain. Returns metadata only."""
    domain = extract_domain(request.url)
    fetcher = await fetcher_crud.get_first_active_by_domain(db, domain)
    if not fetcher:
        return FetcherLookupResponse(domain=domain, found=False, fetcher=None)

    info = await _build_info(db, fetcher)
    return FetcherLookupResponse(domain=domain, found=True, fetcher=info)


@router.post("/run", response_model=FetcherRunResponse)
async def run_fetcher_endpoint(
    request: FetcherRunRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Invoke a registered fetcher against a URL.

    Routes via param_schema:
    - source_type='motie' → GET/POST {motie_project.api_url}{route_path}
    - source_type='proxy' → GET/POST {api_url_override}{route_path}
    """
    fetcher = await fetcher_crud.get_by_id(db, request.fetcher_id)
    if not fetcher:
        raise HTTPException(404, f"Fetcher {request.fetcher_id} not found")
    if fetcher.status != "active":
        raise HTTPException(
            409, f"Fetcher {fetcher.id} is {fetcher.status}, not active"
        )

    result = await run_fetcher(
        db=db,
        fetcher=fetcher,
        listing_url=request.url,
        super_id=str(request.super_id) if request.super_id else None,
        extra_params=request.extra_params,
        timeout=request.timeout,
    )

    return FetcherRunResponse(
        fetcher_id=fetcher.id,
        url=result.url,
        status=result.status,
        http_status_code=result.http_status_code,
        payload=result.payload,
        error_message=result.error_message,
        duration_ms=result.duration_ms,
        is_metered=result.is_metered,
    )


@router.post("/validate", response_model=FetcherValidateResponse)
async def validate_fetched_data(
    request: FetcherValidateRequest,
):
    """
    Validate captured data against the baseline schema (essential field presence
    + tier-weighted completeness score).

    Two ways to call:
    - Pass `fields` directly — pre-extracted structured fields from any source.
    - Pass `raw_payload` (with optional adapter_name hint) — server parses it.
      Currently only the motie parser is wired in; default behavior assumes
      a Motie-shaped payload.
    """
    fields: dict
    if request.fields is not None:
        fields = dict(request.fields)
    elif request.raw_payload is not None:
        # MVP: parse via the Motie parser, which handles flat-JSON payloads.
        # Other adapter parsers can be wired in later.
        try:
            parsed_fields, image_urls, floorplan_urls = parse_motie_result(
                request.raw_payload, request.url
            )
            fields = parsed_fields
            # Surface media into the field set so presence checks work.
            if "image_urls" not in fields:
                fields["image_urls"] = image_urls
            if "floorplan_urls" not in fields:
                fields["floorplan_urls"] = floorplan_urls
        except Exception as e:
            logger.error(f"Validate parse failed: {e}", exc_info=True)
            raise HTTPException(422, f"Could not parse raw_payload: {e}")
    else:
        raise HTTPException(400, "Provide either `fields` or `raw_payload` to validate")

    presence = compute_field_presence(fields)
    score = compute_completeness_score(presence)
    missing = [f for f, p in presence.items() if not p]
    missing_critical = get_missing_critical_fields(presence)

    # Pass condition: weighted completeness score >= ACCEPT_THRESHOLD (default 0.85).
    # Mirrors the legacy data_capture_pipeline accept logic. Tier weights live in
    # services.field_registry.PRIORITY_WEIGHTS (P0=1.0, P1=0.8, ..., P5=0.1) so a
    # missing low-priority field doesn't automatically fail validation.
    passed = score.overall >= settings.COMPLETENESS_ACCEPT_THRESHOLD

    return FetcherValidateResponse(
        passed=passed,
        completeness_score=score.overall,
        fields_present=score.fields_present,
        fields_total=score.fields_total,
        priority_scores=score.priority_scores,
        missing_fields=missing,
        missing_critical_fields=missing_critical,
    )
