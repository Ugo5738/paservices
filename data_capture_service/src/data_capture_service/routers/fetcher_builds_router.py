"""
V2 primitive endpoints for Motie-based coded fetcher builds.

POST /fetcher-builds/motie/build              — create project (if needed) + invoke session
GET  /fetcher-builds/motie/session/{id}       — poll session status
POST /fetcher-builds/motie/deploy             — deploy the project
GET  /fetcher-builds/motie/deployment/{id}    — poll deployment status
POST /fetcher-builds/motie/publish            — write deployed routes into fetchers registry
GET  /fetcher-builds/motie/projects/{uuid}    — current project state + Motie agent status

n8n drives the polling loops; the service exposes single-shot calls only.
"""

import logging
from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.adapters.motie.motie_client import motie_client
from data_capture_service.config import settings
from data_capture_service.crud import fetcher_crud, motie_project_crud
from data_capture_service.db import get_db
from data_capture_service.models.motie_scraper_project import MotieScraperProject
from data_capture_service.schemas.v2_schemas import (
    MotieBuildRequest,
    MotieBuildResponse,
    MotieDeploymentStatusResponse,
    MotieDeployRequest,
    MotieDeployResponse,
    MotieProjectStatusResponse,
    MotiePublishedFetcher,
    MotiePublishRequest,
    MotiePublishResponse,
    MotieSessionStatusResponse,
)
from data_capture_service.services.motie_prompts import (
    build_initial_prompt,
    build_repair_prompt,
)
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


@router.post("/build", response_model=MotieBuildResponse, status_code=202)
async def build_or_repair(
    request: MotieBuildRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a Motie project for the URL's domain (if none exists yet) and invoke
    an agent session. Returns project + session id immediately — caller polls
    /fetcher-builds/motie/session/{id} until terminal.

    `prompt_kind='build'`  → initial build prompt (uses benchmark_fields if given)
    `prompt_kind='repair'` → repair prompt referencing failing_error
    """
    _ensure_motie_enabled()

    domain = (request.domain or extract_domain(request.url)).lower()
    if not domain:
        raise HTTPException(400, "Could not derive domain from url")

    # 1) Ensure we have a Motie project for this domain.
    project = await motie_project_crud.get_by_domain(db, domain)
    created_new = False

    if not project:
        # Create on Motie first, then mirror in our DB.
        project_name = _project_name_for(domain)
        try:
            create_resp = await motie_client.create_project(
                name=project_name,
                description=f"Property data capture scraper for {domain}",
            )
        except Exception as e:
            logger.error(f"Motie create_project failed: {e}", exc_info=True)
            raise HTTPException(502, f"Motie create_project failed: {e}")

        try:
            project = await motie_project_crud.create(
                db=db,
                domain=domain,
                motie_project_id=create_resp.id,
                motie_project_name=project_name,
            )
            await db.commit()
            created_new = True
        except IntegrityError:
            await db.rollback()
            project = await motie_project_crud.get_by_domain(db, domain)
            if not project:
                raise HTTPException(
                    500, f"Race creating MotieScraperProject for {domain}"
                )
    else:
        # Active project exists — guard against Motie's one-session-per-project lock.
        try:
            current = await motie_client.get_project(project.motie_project_id)
            if current.agent_status and current.agent_status != "idle":
                raise HTTPException(
                    409,
                    f"Motie project {project.motie_project_id} is busy "
                    f"(agent_status={current.agent_status}, "
                    f"active_session={current.active_session_id}). Try again later.",
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(
                f"Could not fetch Motie project status for {project.motie_project_id}: {e}"
            )

    # 2) Build the prompt.
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

    # 3) Invoke the agent session.
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


@router.get("/session/{session_id}", response_model=MotieSessionStatusResponse)
async def get_session_status(session_id: str):
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


@router.post("/deploy", response_model=MotieDeployResponse, status_code=202)
async def deploy_project(
    request: MotieDeployRequest,
    db: AsyncSession = Depends(get_db),
):
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


@router.get("/deployment/{deployment_id}", response_model=MotieDeploymentStatusResponse)
async def get_deployment_status(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
):
    _ensure_motie_enabled()
    try:
        d = await motie_client.get_deployment(deployment_id)
    except Exception as e:
        logger.error(f"Motie get_deployment failed: {e}", exc_info=True)
        raise HTTPException(502, f"Motie get_deployment failed: {e}")

    # When the deployment reports 'deployed' with an api_url, sync our project row.
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


def _routes_from_openapi(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract (route_path, http_method, url_param_info) from an OpenAPI spec."""
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
            url_param: Dict[str, Any] = {
                "url_param": "listing_url",
                "url_location": "query",
            }
            # Inspect parameters list for a url-shaped query/body param.
            params = op.get("parameters") or []
            for p in params:
                pname = (p.get("name") or "").lower()
                if pname in ("listing_url", "url", "property_url", "page_url"):
                    url_param = {
                        "url_param": p.get("name"),
                        "url_location": (p.get("in") or "query").lower(),
                    }
                    break
            found.append(
                {
                    "path": path,
                    "method": method_name.upper(),
                    "param_schema": url_param,
                    "summary": op.get("summary"),
                }
            )
    return found


@router.post("/publish", response_model=MotiePublishResponse)
async def publish_project_routes(
    request: MotiePublishRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Read the deployed project's OpenAPI spec and register every callable route
    in the fetchers table so /fetchers/lookup picks them up.

    No Motie API call — this is a pure registry write step.
    """
    project = await db.get(MotieScraperProject, request.project_uuid)
    if not project:
        raise HTTPException(
            404, f"MotieScraperProject {request.project_uuid} not found"
        )
    if not project.api_url:
        raise HTTPException(409, f"Project {project.id} has no api_url — deploy first")

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
