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
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.clients.super_id_service_client import (
    super_id_service_client,
)
from data_capture_service.crud import canonical_crud, fetcher_crud, fetcher_run_crud
from data_capture_service.db import get_db
from data_capture_service.models.fetcher_run import FetcherType
from data_capture_service.schemas.v2_schemas import (
    FetcherInfo,
    FetcherListResponse,
    FetcherLookupRequest,
    FetcherLookupResponse,
    FetcherRegisterRequest,
    FetcherRegisterResponse,
    FetcherRunBySuperIdResponse,
    FetcherRunRequest,
    FetcherRunResponse,
    FetcherValidateRequest,
    FetcherValidateResponse,
    MotiePublishedFetcher,
    PromoteToCanonicalRequest,
    PromoteToCanonicalResponse,
    RecordFromSnapshotRequest,
)
from data_capture_service.adapters.base import AdapterStatus
from data_capture_service.config import settings
from data_capture_service.services import fetcher_audit, parser_registry
from data_capture_service.services.baseline_provider import (
    firecrawl_baseline_provider,
)
from data_capture_service.services.fetcher_runner import run_fetcher
from data_capture_service.services.field_registry import (
    CANONICAL_COLUMN_FIELDS,
    EXTRAS_FIELDS,
    compute_completeness_score,
    compute_field_presence,
    get_missing_critical_fields,
)
from data_capture_service.services.thresholds import VALIDATE_PASS_THRESHOLD
from data_capture_service.utils.security import validate_token
from data_capture_service.utils.url_utils import extract_domain

# Field name → CanonicalPropertySnapshot column. Mirrors mappers/canonical_mapper.py's
# FIELD_TO_COLUMN but kept local so the V2 promote endpoint has a self-contained
# mapping path (V1's mapper takes a ParsedDataCaptureResult which we don't have
# in the V2 path — we have raw fields_json from fetcher_runs).
_FIELD_TO_COLUMN: dict = {
    "address_road": "address_road",
    "price": "price",
    "price_text": "price_text",
    "address_town": "address_town",
    "bedrooms": "bedrooms",
    "estate_agent_name": "estate_agent_name",
    "agent_address": "agent_address",
    "transaction_type": "transaction_type",
    "bathrooms": "bathrooms",
    "property_type": "property_type",
    "full_address": "full_address",
    "postcode": "postcode",
    "description": "description",
    "rightmove_url": "rightmove_url",
}
_MEDIA_FIELDS = {"image_urls", "floorplan_urls", "video_urls"}

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


@router.get(
    "/runs/by-super-id/{super_id}",
    response_model=FetcherRunBySuperIdResponse,
)
async def get_fetcher_run_by_super_id(
    super_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Read the immutable fetcher_runs row recorded under this SuperID.

    Per `docs/data_capture_v2_id_and_data_flow.md` Step 8, the Motie Build
    workflow uses the *already-captured* AI output as the benchmark for the
    fetcher it generates ("Motie generates a fetcher using the URL + the
    FireCrawl benchmark fields"). Rather than re-invoking the AI fetcher
    service (which would violate single-use — `ai_fetcher_service` has
    already consumed this SuperID during Data Capture's AI fallback), the
    Build workflow reads the cached row here.

    Reading does NOT count as a new use of the SuperID — single-use is a
    write/invocation rule, not a read rule. The Fetcher Build workflow
    remains "one use of one SuperID for the entire long-running execution"
    per docs §3.1.

    Returns 404 if no row exists for the given SuperID.
    """
    run = await fetcher_run_crud.get_by_super_id(db, super_id)
    if not run:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No fetcher_runs row recorded under super_id={super_id}. "
                "Has Data Capture actually run for this SuperID?"
            ),
        )
    return FetcherRunBySuperIdResponse(
        super_id=run.super_id,
        url=run.url,
        fetcher_type=run.fetcher_type,
        vendor=run.vendor,
        succeeded=run.succeeded,
        completeness_score=run.completeness_score,
        fields=run.fields_json,
        field_presence=run.field_presence_json,
        missing_fields=run.missing_fields_json,
        error_message=run.error_message,
        created_at=run.created_at,
    )


def _parse_and_score(fetcher, payload, url, *, when: bool = True):
    """
    chunk 8.6/8.7: parse `payload` via the fetcher's parser and compute
    field presence + completeness, so the fetcher_runs row is a complete,
    immutable, gate-checkable record (parity with the AI path).

    Parser resolution mirrors /fetchers/validate:
    fetcher.metadata_json["parser_name"] → 'motie' when
    source_type=='motie' → 'motie' fallback.

    MUST NOT raise — any failure (no parser, parse exception, empty
    payload, or `when` False) returns all-None so the caller records a
    raw-only row, exactly as the pre-8.6 behaviour.

    Returns: (parsed_fields, field_presence, completeness, missing_fields).
    """
    if not when or not isinstance(payload, dict) or not payload:
        return None, None, None, None
    try:
        meta = fetcher.metadata_json or {}
        parser_name = (
            (meta.get("parser_name") or "").lower()
            or ("motie" if fetcher.source_type == "motie" else "")
            or "motie"
        )
        parser = parser_registry.get(parser_name)
        if parser is None:
            logger.warning(
                "_parse_and_score: no parser '%s' for fetcher %s; "
                "recording raw-only row",
                parser_name,
                fetcher.id,
            )
            return None, None, None, None
        pf, image_urls, floorplan_urls = parser(payload, url)
        pf = pf or {}
        if image_urls and "image_urls" not in pf:
            pf["image_urls"] = image_urls
        if floorplan_urls and "floorplan_urls" not in pf:
            pf["floorplan_urls"] = floorplan_urls
        presence = compute_field_presence(pf)
        sc = compute_completeness_score(presence)
        missing = [f for f, p in presence.items() if not p]
        return pf, presence, sc.overall, missing
    except Exception as e:  # noqa: BLE001 — must never break run recording
        logger.warning(
            "_parse_and_score: parse/score failed for fetcher %s (%s); "
            "recording raw-only row",
            fetcher.id,
            e,
        )
        return None, None, None, None


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

    # Reference SuperID convention (chunk 7): default reference to operating
    # if the caller didn't specify one (the common, simple case).
    reference_super_id = request.reference_super_id or request.super_id

    # SuperID Metadata: record this use of the SuperID by the coded fetcher.
    # Non-blocking — failures are logged but don't kill the request
    # (chunk 3 / docs/superid_data_capture_design.md section 3.3).
    if request.super_id:
        activity_metadata = {
            "fetcher_id": str(fetcher.id),
            "domain": fetcher.domain,
        }
        if reference_super_id and reference_super_id != request.super_id:
            activity_metadata["reference_super_id"] = str(reference_super_id)
        await super_id_service_client.record_activity(
            super_id=request.super_id,
            used_by="coded_fetcher_service",
            source="wf_dc_a_cf/service_invocation",
            metadata=activity_metadata,
        )

    result = await run_fetcher(
        db=db,
        fetcher=fetcher,
        listing_url=request.url,
        super_id=str(request.super_id) if request.super_id else None,
        extra_params=request.extra_params,
        timeout=request.timeout,
    )

    # chunk 8.7: async/proxy fetchers (e.g. the legacy Rightmove bridge)
    # return HTTP 202 "Accepted" with no data — the real capture lands
    # later in a snapshot. Do NOT write a fetcher_runs row here: chunk-4
    # UNIQUE(super_id) allows only ONE row per super_id, and burning it on
    # the empty 202 ack means promote-to-canonical can never see the real
    # capture. The workflow polls + fetches the completed snapshot, then
    # calls /fetchers/record-from-snapshot to write the one real row.
    # The activity record above still stands — the service WAS invoked.
    if result.http_status_code == 202:
        logger.info(
            "Async fetcher accepted (202); deferring fetcher_runs row to "
            "/fetchers/record-from-snapshot",
            extra={
                "super_id": (
                    str(request.super_id) if request.super_id else None
                ),
                "fetcher_id": str(fetcher.id),
            },
        )
        return FetcherRunResponse(
            fetcher_id=fetcher.id,
            url=result.url,
            status="accepted",
            http_status_code=result.http_status_code,
            payload=result.payload if isinstance(result.payload, dict) else None,
            error_message=result.error_message,
            duration_ms=result.duration_ms,
            is_metered=result.is_metered,
            super_id=request.super_id,
            reference_super_id=reference_super_id,
        )

    succeeded = result.status == "success"

    # chunk 8.6: parse + score INLINE so the (synchronous) fetcher_runs row
    # is a complete, immutable, gate-checkable record — parity with the AI
    # path. Async captures take the /fetchers/record-from-snapshot route
    # above instead.
    parsed_fields, field_presence, completeness, missing_fields = (
        _parse_and_score(fetcher, result.payload, request.url, when=succeeded)
    )

    try:
        run = await fetcher_audit.record_run(
            db,
            fetcher_type=FetcherType.CODED.value,
            vendor=fetcher.source_type,
            url=request.url,
            domain=fetcher.domain,
            super_id=request.super_id,
            fetcher_id=fetcher.id,
            completeness_score=completeness,
            payload_json=result.payload if isinstance(result.payload, dict) else None,
            fields_json=parsed_fields,
            field_presence_json=field_presence,
            missing_fields_json=missing_fields,
            error_message=result.error_message,
            duration_ms=result.duration_ms,
            succeeded=succeeded,
            metadata_json={
                "http_status_code": result.http_status_code,
                "is_metered": result.is_metered,
                "reference_super_id": (
                    str(reference_super_id) if reference_super_id else None
                ),
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
        super_id=request.super_id,
        reference_super_id=reference_super_id,
    )


@router.post("/record-from-snapshot", response_model=FetcherRunResponse)
async def record_run_from_snapshot(
    request: RecordFromSnapshotRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    chunk 8.7: write the single immutable fetcher_runs row for an
    async/proxy capture from its completed snapshot.

    /fetchers/run returns 202 for async fetchers WITHOUT writing a row
    (it would burn the chunk-4 UNIQUE(super_id) row on empty data). After
    WF DC A CF polls workflow-status and fetches the completed snapshot,
    it calls this with the snapshot as `raw_payload`. The server parses +
    scores it here (never trusting a caller-supplied score — same
    defensive stance as promote-to-canonical, chunk 8.5) and writes the
    one row that promote-to-canonical then re-checks the gate against.
    """
    fetcher = await fetcher_crud.get_by_id(db, request.fetcher_id)
    if not fetcher:
        raise HTTPException(404, f"Fetcher {request.fetcher_id} not found")

    reference_super_id = request.reference_super_id or request.super_id

    # SuperID Metadata: record this use (the completed snapshot recording).
    # Non-blocking (chunk 3 / docs/superid_data_capture_design.md §3.3).
    if request.super_id:
        activity_metadata = {
            "fetcher_id": str(fetcher.id),
            "domain": fetcher.domain,
        }
        if reference_super_id and reference_super_id != request.super_id:
            activity_metadata["reference_super_id"] = str(reference_super_id)
        await super_id_service_client.record_activity(
            super_id=request.super_id,
            used_by="coded_fetcher_service",
            source="wf_dc_a_cf/record_from_snapshot",
            metadata=activity_metadata,
        )

    parsed_fields, field_presence, completeness, missing_fields = (
        _parse_and_score(fetcher, request.raw_payload, request.url, when=True)
    )
    succeeded = parsed_fields is not None
    err = None if succeeded else "snapshot parse produced no fields"

    try:
        await fetcher_audit.record_run(
            db,
            fetcher_type=FetcherType.CODED.value,
            vendor=fetcher.source_type,
            url=request.url,
            domain=fetcher.domain,
            super_id=request.super_id,
            fetcher_id=fetcher.id,
            completeness_score=completeness,
            payload_json=request.raw_payload,
            fields_json=parsed_fields,
            field_presence_json=field_presence,
            missing_fields_json=missing_fields,
            error_message=err,
            duration_ms=0,
            succeeded=succeeded,
            metadata_json={
                "recorded_from": "snapshot",
                "reference_super_id": (
                    str(reference_super_id) if reference_super_id else None
                ),
            },
        )
        await db.commit()
    except IntegrityError as ie:
        await db.rollback()
        logger.warning(
            "record-from-snapshot reject: super_id already used by this service",
            extra={
                "super_id": (
                    str(request.super_id) if request.super_id else None
                )
            },
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
        url=request.url,
        status="success" if succeeded else "failed",
        http_status_code=200,
        payload=request.raw_payload,
        error_message=err,
        duration_ms=0,
        is_metered=False,
        super_id=request.super_id,
        reference_super_id=reference_super_id,
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


# ─────────────────────────────────────────────────────────────────────────────
# /fetchers/promote-to-canonical (chunk 8 — V2 gate-promote primitive)
# ─────────────────────────────────────────────────────────────────────────────


def _map_fields_to_canonical(
    fields: dict,
) -> tuple[dict, dict, list[dict]]:
    """
    Split a raw fields dict (from fetcher_runs.fields_json) into the three
    canonical shapes:

      - column_fields: Priority 0-3 fields written as real columns
      - extras_json:   Priority 4+ fields stored in extras_json
      - media_items:   image / floorplan / video URLs lifted into
                       canonical_media rows

    Mirrors mappers/canonical_mapper.py for the V1 path, but takes a plain
    dict (V2 has fields_json from the audit row, not a ParsedDataCaptureResult).
    """
    column_fields: dict = {}
    for field_name in CANONICAL_COLUMN_FIELDS:
        if field_name in _MEDIA_FIELDS:
            continue
        column_name = _FIELD_TO_COLUMN.get(field_name, field_name)
        value = fields.get(field_name)
        if value is not None:
            column_fields[column_name] = value

    extras_json: dict = {}
    for field_name in EXTRAS_FIELDS:
        if field_name in _MEDIA_FIELDS:
            continue
        value = fields.get(field_name)
        if value is not None:
            extras_json[field_name] = value

    media_items: list[dict] = []
    for url in fields.get("image_urls", []) or []:
        if not url:
            continue
        media_items.append({"media_type": "photo", "url": url})
    for url in fields.get("floorplan_urls", []) or []:
        if not url:
            continue
        media_items.append({"media_type": "floorplan", "url": url})
    for url in fields.get("video_urls", []) or []:
        if not url:
            continue
        media_items.append({"media_type": "video", "url": url})

    return column_fields, extras_json, media_items


@router.post("/promote-to-canonical", response_model=PromoteToCanonicalResponse)
async def promote_to_canonical(
    request: PromoteToCanonicalRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Promote one gate-passing fetcher_runs row to canonical_property_snapshots.

    Append-only: a second promote of the same SuperID is rejected with 409
    (chunk 8 UNIQUE(super_id) on canonical_property_snapshots). To re-run an
    analysis, mint a fresh SuperID and run the capture again under it
    (docs/superid_principles.md section 4).

    Inputs:
      - super_id: the operating SuperID of the fetcher_runs row to promote.

    The endpoint:
      1. Looks up the fetcher_runs row by super_id (chunk 4 UNIQUE makes this
         unambiguous).
      2. Verifies the row passed the gate:
           - error_message IS NULL,
           - completeness_score >= VALIDATE_PASS_THRESHOLD,
           - no critical fields missing (from field_presence_json).
      3. Maps fields_json into canonical column_fields + extras_json + media.
      4. Inserts canonical_property_snapshot (run_id = NULL for V2 path) and
         canonical_media rows in one transaction.
      5. Writes an activity record on the SuperID for the promote action
         (non-blocking).
    """
    run = await fetcher_run_crud.get_by_super_id(db, request.super_id)
    if not run:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No fetcher_runs row found for super_id={request.super_id}. "
                "The promote endpoint can only be called for SuperIDs this "
                "service has already used (run /fetchers/run or "
                "/ai-fetchers/{adapter}/run first)."
            ),
        )

    # Gate check (defensive — the n8n workflow normally only calls promote
    # after a separate /fetchers/validate pass, but the service enforces it
    # too so a stray direct call can't write a sub-threshold canonical row).
    if run.error_message is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "fetcher_runs row recorded an error_message; promotion is "
                "not permitted. Mint a fresh SuperID and retry the capture."
            ),
        )
    score = run.completeness_score or 0.0
    if score < VALIDATE_PASS_THRESHOLD:
        raise HTTPException(
            status_code=409,
            detail=(
                f"completeness_score {score:.3f} is below "
                f"VALIDATE_PASS_THRESHOLD {VALIDATE_PASS_THRESHOLD}; "
                "promotion is not permitted."
            ),
        )
    missing_critical = get_missing_critical_fields(run.field_presence_json or {})
    if missing_critical:
        # Cross-check against the FireCrawl baseline before rejecting.
        # A field that's missing from the parsed output BUT genuinely
        # absent from the page (e.g. a listing with no floorplan) should
        # NOT block promotion. Only enforce critical fields the baseline
        # confirms ARE present on the page.
        #
        # This is the V2 realisation of Rolf's "FireCrawl baseline gives
        # the validation gate ground truth" pattern (docs/superid_data_
        # capture_design.md): the baseline tells us what's actually on
        # the page; the gate only fires for fields the scraper genuinely
        # missed, not for fields that aren't there at all.
        baseline_confirmed_missing = list(missing_critical)
        if settings.firecrawl_enabled():
            try:
                baseline = await firecrawl_baseline_provider.fetch_baseline(
                    run.url
                )
                if (
                    baseline.status
                    in (AdapterStatus.SUCCESS, AdapterStatus.PARTIAL)
                    and baseline.field_presence
                ):
                    # Keep only fields the baseline confirms ARE on the
                    # page (default True = if baseline doesn't cover the
                    # field, be strict and require it).
                    baseline_confirmed_missing = [
                        f
                        for f in missing_critical
                        if baseline.field_presence.get(f, True)
                    ]
                    logger.info(
                        "Promote gate baseline cross-check: parsed-missing=%s "
                        "baseline-confirmed-on-page=%s (genuinely absent on "
                        "this page → allowed: %s)",
                        missing_critical,
                        baseline_confirmed_missing,
                        sorted(
                            set(missing_critical) - set(baseline_confirmed_missing)
                        ),
                    )
                else:
                    logger.warning(
                        "Promote gate: FireCrawl baseline returned no usable "
                        "data (status=%s); falling back to strict "
                        "missing-critical check.",
                        baseline.status,
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Promote gate: baseline cross-check failed (%s); "
                    "falling back to strict missing-critical check.",
                    exc,
                )

        if baseline_confirmed_missing:
            # Strict-gate explanation lives here so we can name the fields
            # actually missed (per baseline) vs the union of all P0/P1
            # absent in the parsed output.
            raise HTTPException(
                status_code=409,
                detail=(
                    "Critical fields present on the page (per baseline) but "
                    f"missing from the parsed result: "
                    f"{baseline_confirmed_missing}. Promotion is not "
                    "permitted."
                ),
            )

    fields = run.fields_json or {}
    column_fields, extras_json, media_items = _map_fields_to_canonical(fields)

    try:
        snapshot = await canonical_crud.create_snapshot(
            db=db,
            run_id=None,  # V2 path has no parent data_capture_runs row
            super_id=run.super_id,
            source_adapter=run.vendor,
            source_url=run.url,
            completeness_score=run.completeness_score,
            column_fields=column_fields,
            extras_json=extras_json if extras_json else None,
        )
        if media_items:
            await canonical_crud.create_media_records(
                db=db,
                snapshot_id=snapshot.id,
                super_id=run.super_id,
                media_items=media_items,
            )
        await db.commit()
    except IntegrityError as ie:
        await db.rollback()
        logger.warning(
            "Promote-to-canonical reject: super_id already promoted",
            extra={"super_id": str(request.super_id)},
        )
        raise HTTPException(
            status_code=409,
            detail=(
                "super_id has already been promoted to canonical. Mint a "
                "fresh SuperID and retry the capture if you need a new "
                "canonical row (principles section 4)."
            ),
        ) from ie

    # SuperID Metadata: record the promote action for traceability.
    # Non-blocking — failures are logged but don't undo the canonical write.
    await super_id_service_client.record_activity(
        super_id=run.super_id,
        used_by="data_capture_service",
        source="data_capture_service/promoted_to_canonical",
        metadata={
            "fetcher_type": run.fetcher_type,
            "vendor": run.vendor,
            "completeness_score": run.completeness_score,
            "columns_written": len(column_fields),
            "extras_count": len(extras_json),
            "media_count": len(media_items),
        },
    )

    return PromoteToCanonicalResponse(
        super_id=run.super_id,
        source_url=run.url,
        source_adapter=run.vendor,
        completeness_score=run.completeness_score,
        columns_written=len(column_fields),
        extras_count=len(extras_json),
        media_count=len(media_items),
    )
