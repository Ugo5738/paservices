"""
V2 Fetcher Build endpoints (Motie).

n8n only sees an encapsulated build state machine. Motie's 4-step protocol
(invoke → poll session → deploy → poll deployment) is hidden inside the
data-capture service.

POST /fetcher-builds/motie/build/start         — kick off invoke (or repair); creates motie_builds row
GET  /fetcher-builds/motie/build/{id}/status   — advance state machine + return current state
POST /fetcher-builds/motie/build/{id}/score    — run AI fetcher + deployed scraper, score, save
POST /fetcher-builds/motie/build/{id}/publish  — return the registry artefact (NO DB write)
GET  /fetcher-builds/motie/projects/{uuid}     — current project state + Motie agent status

The legacy single-step endpoints (/build, /session, /deploy, /deployment, /publish)
remain on the same router for now to avoid breaking the V1 deployed n8n while WF3
is migrated; they are flagged as deprecated.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.adapters.base import DataCaptureRequest
from data_capture_service.adapters.motie.motie_client import motie_client
from data_capture_service.config import settings
from data_capture_service.crud import (
    ai_fetcher_crud,
    fetcher_crud,
    motie_build_crud,
    motie_project_crud,
)
from data_capture_service.db import get_db
from data_capture_service.models.fetcher_run import FetcherType
from data_capture_service.models.motie_build import (
    MotieBuildPromptKind,
    MotieBuildState,
)
from data_capture_service.models.motie_scraper_project import MotieScraperProject
from data_capture_service.schemas.v2_schemas import (
    MotieArtefactRoute,
    MotieBuildArtefactResponse,
    MotieBuildRequest,
    MotieBuildResponse,
    MotieBuildScoreRequest,
    MotieBuildScoreResponse,
    MotieBuildStartRequest,
    MotieBuildStartResponse,
    MotieBuildStatusResponse,
    MotieDeploymentStatusResponse,
    MotieDeployRequest,
    MotieDeployResponse,
    MotieProjectDeactivateResponse,
    MotieProjectStatusResponse,
    MotiePublishedFetcher,
    MotiePublishRequest,
    MotiePublishResponse,
    MotieSessionStatusResponse,
)
from data_capture_service.services import (
    ai_fetcher_registry,
    fetcher_audit,
    motie_build_orchestrator,
    scoring,
)
from data_capture_service.services.motie_prompts import (
    build_initial_prompt,
    build_repair_prompt,
)
from data_capture_service.services.thresholds import BUILD_PUBLISH_THRESHOLD
from data_capture_service.utils.security import validate_token
from data_capture_service.utils.url_utils import extract_domain

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/fetcher-builds/motie",
    tags=["Fetcher Builds (Motie)"],
    dependencies=[Depends(validate_token)],
)


def _ensure_motie_enabled():
    if not settings.motie_enabled():
        raise HTTPException(
            503, "Motie is not configured (set DATA_CAPTURE_SERVICE_MOTIE_API_TOKEN)"
        )


def _project_name_for(domain: str) -> str:
    return f"data-capture-{domain}"


def _build_status_response(build) -> MotieBuildStatusResponse:
    return MotieBuildStatusResponse(
        build_id=build.id,
        project_uuid=build.project_uuid,
        motie_project_id="",  # filled below
        domain=build.domain,
        url=build.url,
        state=build.state,
        session_id=build.session_id,
        deployment_id=build.deployment_id,
        api_url=build.api_url,
        attempt_number=build.attempt_number,
        parent_build_id=build.parent_build_id,
        benchmark_score=build.benchmark_score,
        error_message=build.error_message,
        is_terminal=build.is_terminal(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# V2 encapsulated build (state machine inside the service)
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/build/start", response_model=MotieBuildStartResponse, status_code=202)
async def start_build(
    request: MotieBuildStartRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Kick off a Motie build (initial or repair).

    Encapsulates rule 7 — the caller polls /build/{id}/status to advance the
    state machine instead of orchestrating Motie's session+deployment APIs.
    """
    _ensure_motie_enabled()

    domain = (request.domain or extract_domain(request.url)).lower()
    if not domain:
        raise HTTPException(400, "Could not derive domain from url")

    if request.prompt_kind not in (
        MotieBuildPromptKind.BUILD.value,
        MotieBuildPromptKind.REPAIR.value,
    ):
        raise HTTPException(
            400, f"prompt_kind must be 'build' or 'repair', got '{request.prompt_kind}'"
        )

    # Honour Rolf's "one active project per domain" rule by default.
    # If the active project is busy on Motie's side, the orchestrator raises
    # MotieProjectBusy → 409, and WF3's Respond Busy branch resets the
    # build_flag back to pending for retry. Recovery from a genuinely stuck
    # session: POST /fetcher-builds/motie/projects/{uuid}/deactivate.
    try:
        project, created_new = await motie_build_orchestrator.ensure_project_for_domain(
            db, domain, spawn_new_on_busy=False
        )
    except motie_build_orchestrator.MotieProjectBusy as exc:
        raise HTTPException(
            409,
            f"Motie project {exc.project.motie_project_id} is busy "
            f"(agent_status={exc.agent_status}, "
            f"active_session={exc.active_session_id}). "
            "Try again later, or deactivate the stuck project via "
            f"POST /fetcher-builds/motie/projects/{exc.project.id}/deactivate.",
        )

    # Build the prompt — diff-aware for repairs so the score actually moves.
    if request.prompt_kind == MotieBuildPromptKind.REPAIR.value:
        if not request.failing_error:
            raise HTTPException(
                400, "failing_error is required for prompt_kind='repair'"
            )
        prompt = build_repair_prompt(
            url=request.url,
            failing_error=request.failing_error,
            missing_fields=request.missing_fields,
            missing_critical_fields=request.missing_critical_fields,
            benchmark_fields=request.benchmark_fields,
            extra_context=request.extra_prompt_context,
        )
    else:
        prompt = build_initial_prompt(
            url=request.url,
            benchmark_fields=request.benchmark_fields,
            extra_context=request.extra_prompt_context,
        )

    try:
        build = await motie_build_orchestrator.start_build(
            db,
            project=project,
            domain=domain,
            url=request.url,
            prompt=prompt,
            prompt_kind=request.prompt_kind,
            parent_build_id=request.parent_build_id,
            metadata_json={"created_new_project": created_new},
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"Motie build start failed: {e}", exc_info=True)
        raise HTTPException(502, f"Motie build start failed: {e}")

    await db.commit()

    return MotieBuildStartResponse(
        build_id=build.id,
        project_uuid=project.id,
        motie_project_id=project.motie_project_id,
        domain=domain,
        url=request.url,
        state=build.state,
        session_id=build.session_id,
        attempt_number=build.attempt_number,
        parent_build_id=build.parent_build_id,
        created_new_project=created_new,
    )


@router.get("/build/{build_id}/status", response_model=MotieBuildStatusResponse)
async def get_build_status(
    build_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Advance the state machine by one Motie poll and return current state.
    Idempotent — calling on a terminal build returns immediately.
    """
    _ensure_motie_enabled()
    build = await motie_build_crud.get_by_id(db, build_id)
    if not build:
        raise HTTPException(404, f"motie_build {build_id} not found")

    if not build.is_terminal():
        build = await motie_build_orchestrator.advance(db, build)
        await db.commit()
        # Refresh after commit so any state-machine writes are reflected.
        build = await motie_build_crud.get_by_id(db, build_id)

    project = await db.get(MotieScraperProject, build.project_uuid)
    motie_project_id = project.motie_project_id if project else ""

    resp = _build_status_response(build)
    resp.motie_project_id = motie_project_id
    return resp


@router.post("/build/{build_id}/score", response_model=MotieBuildScoreResponse)
async def score_build(
    build_id: UUID,
    request: MotieBuildScoreRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Run the default-baseline AI fetcher AND the freshly-deployed Motie
    scraper against the build's URL, then score Motie's output against the
    baseline.

    This is the W3 internal scoring step — vendor-agnostic via
    ai_fetcher_registry. The baseline is whatever AI fetcher row has
    is_default_baseline=true (today: Firecrawl). Score gets written to the
    motie_builds row for the repair-loop decision.
    """
    if request.build_id != build_id:
        raise HTTPException(400, "build_id in path and body must match")

    build = await motie_build_crud.get_by_id(db, build_id)
    if not build:
        raise HTTPException(404, f"motie_build {build_id} not found")
    if build.state != MotieBuildState.DEPLOYED.value:
        raise HTTPException(
            409,
            f"motie_build {build_id} is in state '{build.state}'; can only score "
            "after state='deployed'.",
        )
    if not build.api_url:
        raise HTTPException(
            500, f"motie_build {build_id} is deployed but has no api_url"
        )

    # 1. Run the default-baseline AI fetcher to capture the ground-truth fields
    #    on the same URL. Persisted as a build_benchmark fetcher_runs row.
    try:
        ai_row, ai_adapter = await ai_fetcher_registry.load_default_baseline(db)
    except ai_fetcher_registry.AIFetcherNotRegistered as e:
        raise HTTPException(503, str(e))

    super_id_str = str(request.super_id) if request.super_id else None
    baseline_raw = await ai_adapter.fetch_raw(
        DataCaptureRequest(
            url=build.url,
            super_id=super_id_str,
            adapter_name=ai_row.name,
        )
    )
    baseline_parsed = await ai_adapter.parse(baseline_raw)
    baseline_score_obj = await ai_adapter.score(baseline_parsed)
    baseline_status = (
        baseline_raw.status.value
        if hasattr(baseline_raw.status, "value")
        else str(baseline_raw.status)
    )

    baseline_run = await fetcher_audit.record_run(
        db,
        fetcher_type=FetcherType.BUILD_BENCHMARK.value,
        vendor=ai_row.name,
        url=build.url,
        domain=build.domain,
        super_id=request.super_id,
        ai_fetcher_id=ai_row.id,
        motie_build_id=build.id,
        completeness_score=baseline_score_obj.overall,
        payload_json=baseline_raw.payload,
        fields_json=baseline_parsed.fields,
        field_presence_json=baseline_parsed.field_presence,
        missing_fields_json=baseline_parsed.missing_fields,
        succeeded=baseline_status == "success",
        error_message=baseline_raw.error_message or baseline_parsed.error_message,
        duration_ms=baseline_raw.duration_ms,
        metadata_json={"role": "build_benchmark"},
    )

    # 2. Call the deployed Motie scraper on the same URL.
    candidate_payload: Dict[str, Any] = {}
    candidate_error: str | None = None
    try:
        # Discover the route from the OpenAPI spec — avoids hardcoding.
        spec = await motie_client.get_openapi_spec(build.api_url)
        first_route = next(iter(_routes_from_openapi(spec)), None)
        if first_route is None:
            raise RuntimeError(
                f"No callable routes in OpenAPI spec at {build.api_url}"
            )
        candidate_payload = await motie_client.call_deployed_endpoint(
            api_url=build.api_url,
            route_path=first_route["path"],
            listing_url=build.url,
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"Motie scoring run failed: {e}", exc_info=True)
        candidate_error = str(e)

    # 3. Parse Motie payload via the registry (same parser /fetchers/validate uses).
    from data_capture_service.services import parser_registry

    motie_parser = parser_registry.get("motie")
    if motie_parser is None:
        raise HTTPException(500, "motie parser missing from parser_registry")

    if candidate_payload:
        try:
            candidate_fields, image_urls, floorplan_urls = motie_parser(
                candidate_payload, build.url
            )
            if image_urls and "image_urls" not in candidate_fields:
                candidate_fields["image_urls"] = image_urls
            if floorplan_urls and "floorplan_urls" not in candidate_fields:
                candidate_fields["floorplan_urls"] = floorplan_urls
        except Exception as e:  # noqa: BLE001
            candidate_fields = {}
            candidate_error = (candidate_error or "") + f" parse_failed: {e}"
    else:
        candidate_fields = {}

    # 4. Score candidate vs baseline (vendor-agnostic — no Motie/Firecrawl
    #    references in scoring.py).
    result = scoring.score_against_baseline(
        candidate_fields=candidate_fields,
        baseline_fields=baseline_parsed.fields or {},
    )

    candidate_run = await fetcher_audit.record_run(
        db,
        fetcher_type=FetcherType.BUILD_BENCHMARK.value,
        vendor="motie",
        url=build.url,
        domain=build.domain,
        super_id=request.super_id,
        motie_build_id=build.id,
        completeness_score=result.candidate_score,
        payload_json=candidate_payload or None,
        fields_json=candidate_fields or None,
        succeeded=bool(candidate_fields) and candidate_error is None,
        error_message=candidate_error,
        metadata_json={"role": "build_candidate"},
    )

    diff_payload = {
        "missing_in_candidate": result.diff.missing_in_candidate,
        "extra_in_candidate": result.diff.extra_in_candidate,
        "matched": result.diff.matched,
        "missing_critical_in_candidate": result.missing_critical_in_candidate,
    }
    await motie_build_crud.update_state(
        db,
        build_id,
        benchmark_score=result.candidate_score,
        benchmark_diff_json=diff_payload,
    )
    await db.commit()

    passed = result.candidate_score >= BUILD_PUBLISH_THRESHOLD

    return MotieBuildScoreResponse(
        build_id=build_id,
        candidate_score=result.candidate_score,
        baseline_score=result.baseline_score,
        relative_score=result.relative_score,
        threshold=BUILD_PUBLISH_THRESHOLD,
        passed=passed,
        missing_fields=result.diff.missing_in_candidate,
        missing_critical_fields=result.missing_critical_in_candidate,
        extra_in_candidate=result.diff.extra_in_candidate,
        matched_fields=result.diff.matched,
        candidate_priority_scores=result.candidate_priority_scores,
        baseline_priority_scores=result.baseline_priority_scores,
        baseline_run_id=baseline_run.id,
        candidate_run_id=candidate_run.id,
        baseline_fields=baseline_parsed.fields,
    )


@router.post("/build/{build_id}/publish", response_model=MotieBuildArtefactResponse)
async def publish_build_artefact(
    build_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Return the registry artefact for a deployed build — does NOT write the
    fetchers row.

    Per Rolf's clarification: W3 publishes the Fetcher *on Motie* (which is
    the deploy step, completed before this endpoint is reachable). Adding the
    Fetcher to OUR Db is a separate parent-workflow concern (WF C calls
    /fetchers/register with the artefact this endpoint returns).
    """
    build = await motie_build_crud.get_by_id(db, build_id)
    if not build:
        raise HTTPException(404, f"motie_build {build_id} not found")
    if build.state != MotieBuildState.DEPLOYED.value or not build.api_url:
        raise HTTPException(
            409,
            f"motie_build {build_id} is in state '{build.state}'; "
            "can only publish after state='deployed' with an api_url.",
        )

    project = await db.get(MotieScraperProject, build.project_uuid)
    if project is None:
        raise HTTPException(
            404, f"MotieScraperProject {build.project_uuid} not found"
        )

    try:
        spec = await motie_client.get_openapi_spec(build.api_url)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to fetch OpenAPI spec from {build.api_url}: {e}")
        raise HTTPException(502, f"Failed to fetch OpenAPI spec: {e}")

    routes_raw = _routes_from_openapi(spec)
    if not routes_raw:
        raise HTTPException(
            422,
            f"No callable routes in OpenAPI spec at {build.api_url}",
        )

    routes = [
        MotieArtefactRoute(
            route_path=r["path"],
            http_method=r["method"],
            param_schema=r["param_schema"],
            summary=r.get("summary"),
        )
        for r in routes_raw
    ]

    return MotieBuildArtefactResponse(
        build_id=build.id,
        project_uuid=project.id,
        motie_project_id=project.motie_project_id,
        domain=build.domain,
        api_url=build.api_url,
        routes=routes,
        benchmark_score=build.benchmark_score,
        is_metered=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Legacy single-step endpoints (still wired so the V1 deployed n8n keeps
# working until WF3 is migrated to the encapsulated /build/start flow above).
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/build",
    response_model=MotieBuildResponse,
    status_code=202,
    deprecated=True,
)
async def build_or_repair_legacy(
    request: MotieBuildRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    DEPRECATED: prefer POST /fetcher-builds/motie/build/start which returns a
    `build_id` and encapsulates session+deploy in a single status endpoint.

    Kept for the existing WF3 JSON until that workflow is migrated.
    """
    _ensure_motie_enabled()

    domain = (request.domain or extract_domain(request.url)).lower()
    if not domain:
        raise HTTPException(400, "Could not derive domain from url")

    try:
        project, created_new = await motie_build_orchestrator.ensure_project_for_domain(
            db, domain, spawn_new_on_busy=False
        )
    except motie_build_orchestrator.MotieProjectBusy as exc:
        raise HTTPException(
            409,
            f"Motie project {exc.project.motie_project_id} is busy "
            f"(agent_status={exc.agent_status}, "
            f"active_session={exc.active_session_id}).",
        )

    if request.prompt_kind == "repair":
        if not request.failing_error:
            raise HTTPException(
                400, "failing_error is required for prompt_kind='repair'"
            )
        prompt = build_repair_prompt(
            url=request.url,
            failing_error=request.failing_error,
            benchmark_fields=request.benchmark_fields,
            extra_context=request.extra_prompt_context,
        )
    elif request.prompt_kind == "build":
        prompt = build_initial_prompt(
            url=request.url,
            benchmark_fields=request.benchmark_fields,
            extra_context=request.extra_prompt_context,
        )
    else:
        raise HTTPException(
            400, f"prompt_kind must be 'build' or 'repair', got '{request.prompt_kind}'"
        )

    try:
        invoke = await motie_client.invoke(
            project_id=project.motie_project_id, prompt=prompt
        )
    except Exception as e:
        logger.error(f"Motie invoke failed: {e}", exc_info=True)
        raise HTTPException(502, f"Motie invoke failed: {e}")

    await motie_project_crud.update_deployment(
        db=db, project_id=project.id, last_session_id=invoke.session_id
    )
    await db.commit()

    return MotieBuildResponse(
        project_uuid=project.id,
        motie_project_id=project.motie_project_id,
        session_id=invoke.session_id,
        status=invoke.status,
        created_new_project=created_new,
    )


@router.get("/session/{session_id}", response_model=MotieSessionStatusResponse, deprecated=True)
async def get_session_status(session_id: str):
    """DEPRECATED: prefer GET /fetcher-builds/motie/build/{id}/status."""
    _ensure_motie_enabled()
    try:
        s = await motie_client.get_session(session_id)
    except Exception as e:
        logger.error(f"Motie get_session failed: {e}", exc_info=True)
        raise HTTPException(502, f"Motie get_session failed: {e}")
    return MotieSessionStatusResponse(
        session_id=s.session_id,
        status=s.status,
        result=s.result,
        error=s.error,
        created_at=s.created_at,
        completed_at=s.completed_at,
    )


@router.post("/deploy", response_model=MotieDeployResponse, status_code=202, deprecated=True)
async def deploy_project_legacy(
    request: MotieDeployRequest,
    db: AsyncSession = Depends(get_db),
):
    """DEPRECATED: encapsulated by GET /fetcher-builds/motie/build/{id}/status."""
    _ensure_motie_enabled()

    project = await db.get(MotieScraperProject, request.project_uuid)
    if not project:
        raise HTTPException(
            404, f"MotieScraperProject {request.project_uuid} not found"
        )

    try:
        deploy = await motie_client.deploy(project.motie_project_id)
    except Exception as e:
        logger.error(f"Motie deploy failed: {e}", exc_info=True)
        raise HTTPException(502, f"Motie deploy failed: {e}")

    await motie_project_crud.update_deployment(
        db=db,
        project_id=project.id,
        deployment_id=deploy.deployment_id,
        deployment_status=deploy.status or "pending",
    )
    await db.commit()

    return MotieDeployResponse(
        project_uuid=project.id,
        motie_project_id=project.motie_project_id,
        deployment_id=deploy.deployment_id,
        status=deploy.status,
        api_url=deploy.api_url,
    )


@router.get("/deployment/{deployment_id}", response_model=MotieDeploymentStatusResponse, deprecated=True)
async def get_deployment_status_legacy(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
):
    """DEPRECATED: encapsulated by GET /fetcher-builds/motie/build/{id}/status."""
    _ensure_motie_enabled()
    try:
        d = await motie_client.get_deployment(deployment_id)
    except Exception as e:
        logger.error(f"Motie get_deployment failed: {e}", exc_info=True)
        raise HTTPException(502, f"Motie get_deployment failed: {e}")

    if d.status and d.status.lower() == "deployed" and d.api_url and d.project_id:
        project = await motie_project_crud.get_by_project_id(db, d.project_id)
        if project:
            await motie_project_crud.update_deployment(
                db=db,
                project_id=project.id,
                api_url=d.api_url,
                deployment_id=deployment_id,
                deployment_status="deployed",
            )
            await db.commit()

    return MotieDeploymentStatusResponse(
        deployment_id=d.deployment_id,
        project_id=d.project_id,
        status=d.status,
        api_url=d.api_url,
        error=d.error,
        created_at=d.created_at,
        completed_at=d.completed_at,
    )


@router.post("/publish", response_model=MotiePublishResponse, deprecated=True)
async def publish_project_routes_legacy(
    request: MotiePublishRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    DEPRECATED: V2 splits this into:
      - POST /fetcher-builds/motie/build/{id}/publish  — return artefact (no DB write)
      - POST /fetchers/register                        — WF C inserts the registry row

    This legacy endpoint still writes the row directly so the existing WF3
    keeps working. Remove once WF3 is migrated to the encapsulated flow.
    """
    project = await db.get(MotieScraperProject, request.project_uuid)
    if not project:
        raise HTTPException(
            404, f"MotieScraperProject {request.project_uuid} not found"
        )
    if not project.api_url:
        raise HTTPException(
            409, f"Project {project.id} has no api_url — deploy first"
        )

    domain = (request.domain or project.domain).lower()

    try:
        spec = await motie_client.get_openapi_spec(project.api_url)
    except Exception as e:
        logger.error(f"Failed to fetch OpenAPI spec from {project.api_url}: {e}")
        raise HTTPException(502, f"Failed to fetch OpenAPI spec: {e}")

    routes = _routes_from_openapi(spec)
    if not routes:
        raise HTTPException(
            422, f"No callable routes discovered in OpenAPI spec at {project.api_url}"
        )

    published: List[MotiePublishedFetcher] = []
    for r in routes:
        f = await fetcher_crud.upsert_motie_fetcher(
            db=db,
            domain=domain,
            motie_project_uuid=project.id,
            route_path=r["path"],
            http_method=r["method"],
            param_schema=r["param_schema"],
            is_metered=request.is_metered,
            metadata_json={"openapi_summary": r.get("summary")},
        )
        published.append(
            MotiePublishedFetcher(
                fetcher_id=f.id,
                domain=f.domain,
                route_path=f.route_path,
                http_method=f.http_method,
                param_schema=f.param_schema,
            )
        )

    await db.commit()

    return MotiePublishResponse(
        project_uuid=project.id,
        motie_project_id=project.motie_project_id,
        api_url=project.api_url,
        fetchers=published,
    )


_URL_PARAM_NAMES = frozenset(
    {
        "listing_url",
        "url",
        "property_url",
        "page_url",
        "target_url",
    }
)


def _routes_from_openapi(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract registerable (route_path, http_method, url_param_info) tuples.

    Only routes that declare a URL-shaped parameter (in query, path, or
    requestBody) are returned. This filters out FastAPI meta routes like
    /health, /openapi.json, /docs, /redoc, and any future Motie-built
    endpoints that don't take a property URL — they have no place in the
    fetcher registry.

    Recognised URL parameter names (case-insensitive): listing_url, url,
    property_url, page_url, target_url.
    """
    found: List[Dict[str, Any]] = []
    paths = spec.get("paths", {}) or {}
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for method_name, op in methods.items():
            if method_name.lower() not in ("get", "post"):
                continue
            if not isinstance(op, dict):
                continue

            url_param_info: Optional[Dict[str, Any]] = None

            # 1. parameters[] — query / path / header
            for p in op.get("parameters") or []:
                pname = (p.get("name") or "").lower()
                if pname in _URL_PARAM_NAMES:
                    url_param_info = {
                        "url_param": p.get("name"),
                        "url_location": (p.get("in") or "query").lower(),
                    }
                    break

            # 2. requestBody schema properties — body
            if url_param_info is None:
                req_body = op.get("requestBody") or {}
                content = req_body.get("content") or {}
                for ct_obj in content.values():
                    if not isinstance(ct_obj, dict):
                        continue
                    schema = ct_obj.get("schema") or {}
                    props = schema.get("properties") or {}
                    for prop_name in props.keys():
                        if prop_name.lower() in _URL_PARAM_NAMES:
                            url_param_info = {
                                "url_param": prop_name,
                                "url_location": "body",
                            }
                            break
                    if url_param_info is not None:
                        break

            if url_param_info is None:
                # Route doesn't accept a property URL — skip it.
                continue

            found.append(
                {
                    "path": path,
                    "method": method_name.upper(),
                    "param_schema": url_param_info,
                    "summary": op.get("summary"),
                }
            )
    return found


@router.get("/projects/{project_uuid}", response_model=MotieProjectStatusResponse)
async def get_project_state(
    project_uuid: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Return our stored project + the live Motie agent_status (for session-lock checks)."""
    _ensure_motie_enabled()
    project = await db.get(MotieScraperProject, project_uuid)
    if not project:
        raise HTTPException(404, f"MotieScraperProject {project_uuid} not found")

    motie_agent_status: str = ""
    motie_active_session_id: str = ""
    try:
        live = await motie_client.get_project(project.motie_project_id)
        motie_agent_status = live.agent_status or ""
        motie_active_session_id = live.active_session_id or ""
    except Exception as e:
        logger.warning(
            f"Could not fetch live Motie status for {project.motie_project_id}: {e}"
        )

    return MotieProjectStatusResponse(
        project_uuid=project.id,
        motie_project_id=project.motie_project_id,
        domain=project.domain,
        api_url=project.api_url,
        deployment_status=project.deployment_status,
        last_session_id=project.last_session_id,
        last_deployment_id=project.last_deployment_id,
        motie_agent_status=motie_agent_status or None,
        motie_active_session_id=motie_active_session_id or None,
        is_active=project.is_active,
    )


@router.post(
    "/projects/{project_uuid}/deactivate",
    response_model=MotieProjectDeactivateResponse,
)
async def deactivate_project(
    project_uuid: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a Motie project inactive in our DB so a fresh project can take its
    place for the same domain.

    Use case: a Motie session has become orphaned/stuck and the public Motie
    API exposes no session-cancel endpoint. Deactivating the project in our
    DB releases the slot enforced by the partial unique index
    (uq_motie_scraper_projects_active_domain), letting the next /build/start
    create a new project for the domain instead of returning 409.

    Side effects:
      - data_capture.motie_scraper_projects.is_active flipped to false.
      - Motie's deployed endpoint (if any) is left alive on Motie's side
        (we have no way to delete a project with an active session).
      - Any data_capture.fetchers row pointing at this project keeps
        pointing at it until the next successful build's /fetchers/register
        replaces the pointer (dedupe is by domain+route_path).

    Idempotent: deactivating an already-inactive project is a no-op.
    """
    project = await db.get(MotieScraperProject, project_uuid)
    if not project:
        raise HTTPException(404, f"MotieScraperProject {project_uuid} not found")

    motie_agent_status: Optional[str] = None
    motie_active_session_id: Optional[str] = None
    try:
        live = await motie_client.get_project(project.motie_project_id)
        motie_agent_status = live.agent_status or None
        motie_active_session_id = live.active_session_id or None
    except Exception as e:  # noqa: BLE001
        logger.warning(
            f"Could not probe Motie status during deactivate for "
            f"{project.motie_project_id}: {e}"
        )

    if project.is_active:
        await motie_project_crud.deactivate(db, project.id)
        await db.commit()
        note = (
            "Deactivated. Next /build/start for this domain will create a "
            "fresh Motie project."
        )
    else:
        note = "Already inactive; no change."

    return MotieProjectDeactivateResponse(
        project_uuid=project.id,
        motie_project_id=project.motie_project_id,
        domain=project.domain,
        is_active=False,
        motie_agent_status=motie_agent_status,
        motie_active_session_id=motie_active_session_id,
        note=note,
    )
