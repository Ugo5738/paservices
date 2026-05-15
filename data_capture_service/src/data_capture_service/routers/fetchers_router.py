"""
V2 primitive endpoints for coded fetchers.

GET  /fetchers           — list registered fetchers (filterable by domain/source_type)
POST /fetchers/lookup    — registry lookup by URL/domain
POST /fetchers/run       — invoke a registered fetcher against a URL
POST /fetchers/validate  — validate captured data against the baseline schema
POST /fetchers/register  — insert a fetcher row from a build artefact (WF C)

These primitives are stateless and take no orchestration decisions. n8n owns
the routing/looping logic. Every /fetchers/run call writes a fetcher_runs
audit row (rule 5).
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.clients.super_id_service_client import (
    super_id_service_client,
)
from data_capture_service.crud import fetcher_crud
from data_capture_service.db import get_db
from data_capture_service.models.fetcher_run import FetcherType
from data_capture_service.schemas.v2_schemas import (
    FetcherInfo,
    FetcherListResponse,
    FetcherLookupRequest,
    FetcherLookupResponse,
    FetcherRegisterRequest,
    FetcherRegisterResponse,
    FetcherRunRequest,
    FetcherRunResponse,
    FetcherValidateRequest,
    FetcherValidateResponse,
    MotiePublishedFetcher,
)
from data_capture_service.services import fetcher_audit, parser_registry
from data_capture_service.services.fetcher_runner import run_fetcher
from data_capture_service.services.field_registry import (
    compute_completeness_score,
    compute_field_presence,
    get_missing_critical_fields,
)
from data_capture_service.services.thresholds import VALIDATE_PASS_THRESHOLD
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


@router.get("", response_model=FetcherListResponse)
async def list_fetchers(
    domain: Optional[str] = Query(
        default=None,
        description="Filter to fetchers covering this domain (case-insensitive).",
    ),
    source_type: Optional[str] = Query(
        default=None,
        description="Filter by source_type ('motie' | 'proxy').",
    ),
    status: Optional[str] = Query(
        default=None,
        description="Filter by status ('active' | 'disabled'). Defaults to all.",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """
    List registered fetchers, optionally filtered by domain / source_type / status.

    Used by pa_mcp's `list_pre_built_fetchers_tool` so MCP agents can introspect
    which scrapers are registered for which domains. Returns metadata only —
    same shape as `/fetchers/lookup`'s `fetcher` field, just one per row.
    """
    rows = await fetcher_crud.list_filtered(
        db, domain=domain, source_type=source_type, status=status, limit=limit
    )
    fetchers = [await _build_info(db, f) for f in rows]
    return FetcherListResponse(fetchers=fetchers, total=len(fetchers))


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

    Persists the attempt to fetcher_runs as a single-shot 'final' row.
    """
    fetcher = await fetcher_crud.get_by_id(db, request.fetcher_id)
    if not fetcher:
        raise HTTPException(404, f"Fetcher {request.fetcher_id} not found")
    if fetcher.status != "active":
        raise HTTPException(
            409, f"Fetcher {fetcher.id} is {fetcher.status}, not active"
        )

    # SuperID Metadata: record this use of the SuperID by the coded fetcher.
    # Non-blocking — failures are logged but don't kill the request
    # (chunk 3 / docs/superid_data_capture_design.md section 3.3).
    if request.super_id:
        await super_id_service_client.record_activity(
            super_id=request.super_id,
            used_by="coded_fetcher_service",
            source="wf_dc_a_cf/service_invocation",
            metadata={"fetcher_id": str(fetcher.id), "domain": fetcher.domain},
        )

    result = await run_fetcher(
        db=db,
        fetcher=fetcher,
        listing_url=request.url,
        super_id=str(request.super_id) if request.super_id else None,
        extra_params=request.extra_params,
        timeout=request.timeout,
    )

    succeeded = result.status == "success"
    try:
        run = await fetcher_audit.record_run(
            db,
            fetcher_type=FetcherType.CODED.value,
            vendor=fetcher.source_type,
            url=request.url,
            domain=fetcher.domain,
            super_id=request.super_id,
            fetcher_id=fetcher.id,
            payload_json=result.payload if isinstance(result.payload, dict) else None,
            error_message=result.error_message,
            duration_ms=result.duration_ms,
            succeeded=succeeded,
            metadata_json={
                "http_status_code": result.http_status_code,
                "is_metered": result.is_metered,
            },
        )
        await db.commit()
    except IntegrityError as ie:
        await db.rollback()
        logger.warning(
            "Coded fetcher run reject: super_id already used by this service",
            extra={"super_id": str(request.super_id) if request.super_id else None},
        )
        raise HTTPException(
            status_code=409,
            detail=(
                "super_id has already been used by the coded fetcher service. "
                "Mint a new super_id and retry (principles section 4)."
            ),
        ) from ie

    return FetcherRunResponse(
        fetcher_id=fetcher.id,
        url=result.url,
        status=result.status,
        http_status_code=result.http_status_code,
        payload=result.payload,
        error_message=result.error_message,
        duration_ms=result.duration_ms,
        is_metered=result.is_metered,
        run_id=run.id,
    )


@router.post("/validate", response_model=FetcherValidateResponse)
async def validate_fetched_data(
    request: FetcherValidateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Validate captured data against the baseline schema (essential field
    presence + tier-weighted completeness score).

    Two ways to call:
    - Pass `fields` directly — pre-extracted structured fields from any source.
    - Pass `raw_payload` (with optional adapter_name hint) — server selects
      the parser via the parser registry. NEVER hardcoded to Motie.

    The "passed" cutoff is service-owned (services.thresholds.VALIDATE_PASS_THRESHOLD),
    not a query parameter — keeps thresholds out of n8n workflow JSON.
    """
    fields: dict
    if request.fields is not None:
        fields = dict(request.fields)
    elif request.raw_payload is not None:
        # Pick parser via registry. Resolution order:
        #   1. caller-supplied request.adapter_name (explicit override)
        #   2. fetcher.metadata_json["parser_name"] (registered hint —
        #      e.g. the rightmove proxy fetcher carries parser_name="rightmove"
        #      so its non-Motie response shape is parsed correctly)
        #   3. fetcher.source_type — works for source_type='motie' since we
        #      have a "motie" parser; falls through for 'proxy' since proxy
        #      fetchers vary by vendor
        #   4. final fallback: 'motie' (backwards-compatible default)
        adapter_name = (request.adapter_name or "").lower() or None

        if adapter_name is None and request.fetcher_id is not None:
            fetcher = await fetcher_crud.get_by_id(db, request.fetcher_id)
            if fetcher:
                meta = fetcher.metadata_json or {}
                hinted = (meta.get("parser_name") or "").lower() or None
                if hinted and parser_registry.get(hinted) is not None:
                    adapter_name = hinted
                elif fetcher.source_type == "motie":
                    adapter_name = "motie"

        adapter_name = adapter_name or "motie"
        parser = parser_registry.get(adapter_name)
        if parser is None:
            raise HTTPException(
                422,
                f"No parser registered for adapter '{adapter_name}'. "
                f"Known: {parser_registry.known()}. Pass `fields` directly to skip.",
            )

        try:
            parsed_fields, image_urls, floorplan_urls = parser(
                request.raw_payload, request.url
            )
            fields = parsed_fields
            if image_urls and "image_urls" not in fields:
                fields["image_urls"] = image_urls
            if floorplan_urls and "floorplan_urls" not in fields:
                fields["floorplan_urls"] = floorplan_urls
        except Exception as e:
            logger.error(f"Validate parse failed via {adapter_name}: {e}", exc_info=True)
            raise HTTPException(
                422, f"Could not parse raw_payload via {adapter_name}: {e}"
            )
    else:
        raise HTTPException(
            400, "Provide either `fields` or `raw_payload` to validate"
        )

    presence = compute_field_presence(fields)
    score = compute_completeness_score(presence)
    missing = [f for f, p in presence.items() if not p]
    missing_critical = get_missing_critical_fields(presence)

    passed = score.overall >= VALIDATE_PASS_THRESHOLD

    return FetcherValidateResponse(
        passed=passed,
        completeness_score=score.overall,
        fields_present=score.fields_present,
        fields_total=score.fields_total,
        priority_scores=score.priority_scores,
        missing_fields=missing,
        missing_critical_fields=missing_critical,
        fields=fields,
    )


@router.post("/register", response_model=FetcherRegisterResponse)
async def register_fetcher(
    request: FetcherRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Insert (or update) a registry row from a build artefact.

    Called by WF C *after* WF3 publishes a Motie deployment and produces the
    artefact. Per Rolf: W3 (build+publish) does not write to our registry —
    that's a parent-workflow concern, handled here.

    Stores `build_score` so a later drift-detection pass can compare against
    the initial benchmark.
    """
    if not request.routes:
        raise HTTPException(422, "At least one route is required")

    now = datetime.now(timezone.utc) if request.build_score is not None else None
    published: list[MotiePublishedFetcher] = []
    for r in request.routes:
        fetcher = await fetcher_crud.upsert_motie_fetcher(
            db=db,
            domain=request.domain,
            motie_project_uuid=request.motie_project_uuid,
            route_path=r.route_path,
            http_method=r.http_method,
            param_schema=r.param_schema,
            is_metered=request.is_metered,
            metadata_json=request.metadata_json
            or ({"openapi_summary": r.summary} if r.summary else None),
        )
        # Stamp the build score for drift reference.
        if request.build_score is not None:
            fetcher.build_score = request.build_score
            fetcher.build_scored_at = now
            await db.flush()

        published.append(
            MotiePublishedFetcher(
                fetcher_id=fetcher.id,
                domain=fetcher.domain,
                route_path=fetcher.route_path,
                http_method=fetcher.http_method,
                param_schema=fetcher.param_schema,
            )
        )

    await db.commit()
    return FetcherRegisterResponse(fetchers=published)
