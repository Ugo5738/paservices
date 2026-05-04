import json

import httpx
from mcp.server.fastmcp import FastMCP
from sqlalchemy.exc import SQLAlchemyError

from .config import settings
from .crud import upsert_analysis_result
from .db import AsyncSessionLocal
from .tools import v2_tools
from .tools.auth_helper import get_m2m_token
from .tools.n8n_service_tools import (
    trigger_floorplan_via_n8n,
    trigger_image_condition_via_n8n,
)
from .tools.n8n_tools import (
    get_property_analysis_result,
    start_property_analysis_via_n8n,
)
from .utils.logging_config import logger

# Create an MCP server
mcp = FastMCP(name=settings.PROJECT_NAME)


# ---------------------------------------------------------------------------
# Tools (current set)
# ---------------------------------------------------------------------------
# Layout follows the V2 proposal's MCP tools section:
#
#   Bottom layer (per-vendor):    firecrawl_fetch_tool, motie_fetch_tool,
#                                 motie_build_tool
#   Middle layer (reusable):      fetch_with_pre_built_tool, fetch_with_ai_tool,
#                                 build_fetcher_tool
#   Top layer (full workflows):   full_analysis_primary_tool,
#                                 full_analysis_fallback_tool
#   Observability:                list_pre_built_fetchers_tool,
#                                 get_fetcher_build_status_tool,
#                                 get_property_analysis_result_tool
#   Helpers:                      create_super_id_tool
#   Downstream-only triggers:     trigger_floorplan_tool, trigger_image_condition_tool
#   Legacy:                       trigger_full_property_analysis_tool
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Bottom-layer tools — per-vendor primitives (full agent control over which
# specific vendor is used). Per Rolf's V2 spec.
# ---------------------------------------------------------------------------


@mcp.tool()
async def firecrawl_fetch_tool(
    url: str = "",
    super_id: str = "",
    prompt: str = "",
) -> str:
    """Single-shot Firecrawl AI fetch for a URL.

    Use when you specifically want Firecrawl (no domain registry lookup, no
    multishot, no fallback). Returns parsed property fields, presence map,
    completeness score, and a `run_id` for the audit trail.

    Optional `prompt` overrides the default Firecrawl extraction prompt.

    Single attempt; for multishot quality use fetch_with_ai_tool.
    """
    if not url:
        return "❌ Error: url is required"
    async with httpx.AsyncClient() as client:
        try:
            result = await v2_tools.firecrawl_fetch(
                client,
                url=url,
                super_id=super_id or None,
                prompt=prompt or None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("firecrawl_fetch_tool failed: %s", exc, exc_info=True)
            return f"❌ Error: {exc}"
    return json.dumps(result)


@mcp.tool()
async def motie_fetch_tool(
    url: str = "",
    super_id: str = "",
) -> str:
    """Call the deployed Motie scraper registered for the URL's domain.

    Looks up the registered fetcher; if it is a Motie source, runs it and
    returns the captured payload. If no Motie fetcher exists for the domain,
    returns `error: no_fetcher_for_domain` so the caller can fall back to
    motie_build_tool or fetch_with_ai_tool.
    """
    if not url:
        return "❌ Error: url is required"
    async with httpx.AsyncClient() as client:
        try:
            result = await v2_tools.motie_fetch(
                client, url=url, super_id=super_id or None
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("motie_fetch_tool failed: %s", exc, exc_info=True)
            return f"❌ Error: {exc}"
    return json.dumps(result)


@mcp.tool()
async def motie_build_tool(
    url: str = "",
    prompt_kind: str = "build",
    failing_error: str = "",
    benchmark_fields_json: str = "",
) -> str:
    """Trigger Motie's agent to build a new scraper for the URL's domain.

    Returns immediately with `build_id` and `state: session_running`. Poll
    progress with get_fetcher_build_status_tool(build_id) until terminal
    (`deployed` | `session_failed` | `deployment_failed`).

    For an end-to-end build that scores, publishes, and registers the result
    in one call use build_fetcher_tool instead.

    `prompt_kind` is `build` (initial) or `repair` (existing project).
    `failing_error` is required when `prompt_kind="repair"`.
    `benchmark_fields_json` (optional) is the AI-fetcher reference data dict.
    """
    if not url:
        return "❌ Error: url is required"
    benchmark_fields = None
    if benchmark_fields_json:
        try:
            benchmark_fields = json.loads(benchmark_fields_json)
        except json.JSONDecodeError:
            return "❌ Error: benchmark_fields_json is not valid JSON"
    async with httpx.AsyncClient() as client:
        try:
            result = await v2_tools.motie_build_start(
                client,
                url=url,
                prompt_kind=prompt_kind or "build",
                failing_error=failing_error or None,
                benchmark_fields=benchmark_fields,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("motie_build_tool failed: %s", exc, exc_info=True)
            return f"❌ Error: {exc}"
    return json.dumps(result)


# ---------------------------------------------------------------------------
# Middle-layer tools — reusable flows
# ---------------------------------------------------------------------------


@mcp.tool()
async def fetch_with_pre_built_tool(
    url: str = "",
    super_id: str = "",
) -> str:
    """Try registered pre-built fetchers in order until one passes.

    Vendor-agnostic: the registry decides which fetcher to use for the URL's
    domain. Returns `status: "no_fetcher"` if no domain match, `status: "pass"`
    when a fetcher's output meets the validation threshold, or `status: "fail"`
    if it ran but the captured data was below threshold.

    Backed by WF1.
    """
    if not url:
        return "❌ Error: url is required"
    async with httpx.AsyncClient() as client:
        try:
            result = await v2_tools.fetch_with_pre_built(
                client, url=url, super_id=super_id or None
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("fetch_with_pre_built_tool failed: %s", exc, exc_info=True)
            return f"❌ Error: {exc}"
    return json.dumps(result)


@mcp.tool()
async def fetch_with_ai_tool(
    url: str = "",
    super_id: str = "",
) -> str:
    """Try AI fetchers via the multishot path (WF B).

    Runs Attempt 1 (default prompt), validates against the schema; if not
    passed, runs Attempt 2 (focused prompt with missing fields), then picks
    the higher-scoring of the two. Returns the winner's data + `attempts: []`
    showing both runs for diagnostics.

    Use when you specifically want AI extraction quality (e.g. domain has no
    pre-built fetcher yet, or pre-built returned weak data).
    """
    if not url:
        return "❌ Error: url is required"
    async with httpx.AsyncClient() as client:
        try:
            result = await v2_tools.fetch_with_ai(
                client, url=url, super_id=super_id or None
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("fetch_with_ai_tool failed: %s", exc, exc_info=True)
            return f"❌ Error: {exc}"
    return json.dumps(result)


@mcp.tool()
async def build_fetcher_tool(
    url: str = "",
    super_id: str = "",
    poll_interval: str = "15",
    poll_timeout: str = "1800",
) -> str:
    """End-to-end fetcher build for a new domain.

    Kicks off Motie's agent build, polls until terminal, scores the deployed
    scraper against the AI-fetcher baseline, publishes the artefact, and
    registers the resulting routes in the fetcher registry. After this
    completes successfully the domain is queryable via list_pre_built_fetchers_tool
    and runnable via fetch_with_pre_built_tool.

    `poll_interval` (sec, default 15) — between status checks.
    `poll_timeout` (sec, default 1800 = 30min) — total wait before giving up.

    This is a long-running call (typical 5–15 min). Consider using
    motie_build_tool + get_fetcher_build_status_tool if you want to
    drive polling yourself.
    """
    if not url:
        return "❌ Error: url is required"
    try:
        interval = float(poll_interval) if poll_interval else 15.0
        timeout = float(poll_timeout) if poll_timeout else 1800.0
    except ValueError:
        return "❌ Error: poll_interval and poll_timeout must be numbers"
    async with httpx.AsyncClient() as client:
        try:
            result = await v2_tools.build_fetcher(
                client,
                url=url,
                super_id=super_id or None,
                poll_interval=interval,
                poll_timeout=timeout,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("build_fetcher_tool failed: %s", exc, exc_info=True)
            return f"❌ Error: {exc}"
    return json.dumps(result)


# ---------------------------------------------------------------------------
# Top-layer tools — full workflows
# ---------------------------------------------------------------------------


@mcp.tool()
async def full_analysis_primary_tool(
    property_url: str = "",
    services_json: str = "",
    super_id: str = "",
    callback_url: str = "",
    service_params_json: str = "",
) -> str:
    """Run the complete property analysis pipeline (V2 orchestrator).

    Sends the URL through Orchestrator V3 which:
      1. Calls WF A — tries the registered pre-built fetcher first, falls
         through to AI fetcher if the coded path is missing or weak.
      2. Forwards the capture result to your `callback_url`.
      3. Fans out to floorplan/image-condition analysis as requested.

    `services_json` is a JSON array of service names. Defaults to all three:
    `["data_capture","floorplan_analysis","image_condition_analysis"]`.
    Backwards-compatible aliases `data_capture_motie` / `data_capture_rightmove`
    are also accepted but route through the same V2 fetcher registry.

    Returns 202 immediately with a super_id. Poll progress with
    get_property_analysis_result_tool(super_id), or set `callback_url` to
    receive the final result asynchronously.
    """
    if not property_url:
        return "❌ Error: property_url is required"

    services = (
        ["data_capture", "floorplan_analysis", "image_condition_analysis"]
        if not services_json
        else None
    )
    if services is None:
        try:
            services = json.loads(services_json)
        except json.JSONDecodeError:
            return "❌ Error: services_json is not valid JSON"

    service_params = None
    if service_params_json:
        try:
            service_params = json.loads(service_params_json)
        except json.JSONDecodeError:
            return "❌ Error: service_params_json is not valid JSON"

    async with httpx.AsyncClient() as client:
        try:
            result = await v2_tools.full_analysis_primary(
                client,
                property_url=property_url,
                services=services,
                super_id=super_id or None,
                callback_url=callback_url or None,
                service_params=service_params,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("full_analysis_primary_tool failed: %s", exc, exc_info=True)
            return f"❌ Error: {exc}"
    return json.dumps(result)


@mcp.tool()
async def full_analysis_fallback_tool(
    property_url: str = "",
    super_id: str = "",
    callback_url: str = "",
) -> str:
    """AI-fetcher-first analysis: skip pre-built attempt, force multishot AI,
    queue a coded-fetcher build for the next request.

    Use when:
      - The domain is brand-new (no registered fetcher yet).
      - You want the higher-quality multishot AI extraction over a quick
        coded-fetcher result.

    Returns the AI fetcher's data immediately, plus a `build_queued` flag
    confirming a build_flag was enqueued for WF C to pick up.
    """
    if not property_url:
        return "❌ Error: property_url is required"
    async with httpx.AsyncClient() as client:
        try:
            result = await v2_tools.full_analysis_fallback(
                client,
                property_url=property_url,
                super_id=super_id or None,
                callback_url=callback_url or None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("full_analysis_fallback_tool failed: %s", exc, exc_info=True)
            return f"❌ Error: {exc}"
    return json.dumps(result)


# ---------------------------------------------------------------------------
# Observability tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_pre_built_fetchers_tool(
    domain: str = "",
    source_type: str = "",
    status: str = "",
) -> str:
    """List registered pre-built fetchers, optionally filtered.

    `domain` (optional) — exact match on the fetcher's domain (case-insensitive).
    `source_type` (optional) — `motie` or `proxy`.
    `status` (optional) — `active` or `disabled`. Default: all.

    Returns each fetcher's id, domain, source_type, route_path, http_method,
    api_url, param_schema, status. Useful for agents to discover what's
    available before deciding between motie_fetch_tool, fetch_with_pre_built_tool,
    or motie_build_tool.
    """
    async with httpx.AsyncClient() as client:
        try:
            result = await v2_tools.list_fetchers(
                client,
                domain=domain or None,
                source_type=source_type or None,
                status=status or None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "list_pre_built_fetchers_tool failed: %s", exc, exc_info=True
            )
            return f"❌ Error: {exc}"
    return json.dumps(result)


@mcp.tool()
async def get_fetcher_build_status_tool(build_id: str = "") -> str:
    """Poll the status of an in-progress Motie fetcher build.

    Returns build_id, state, session_id, deployment_id, api_url (when
    deployed), benchmark_score (when scored), error_message, is_terminal.

    Used after motie_build_tool() returns a build_id, or to inspect
    historical build attempts.
    """
    if not build_id:
        return "❌ Error: build_id is required"
    async with httpx.AsyncClient() as client:
        try:
            result = await v2_tools.get_motie_build_status(client, build_id)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "get_fetcher_build_status_tool failed: %s", exc, exc_info=True
            )
            return f"❌ Error: {exc}"
    return json.dumps(result)


@mcp.tool()
async def get_property_analysis_result_tool(super_id: str = "") -> str:
    """Fetch the status and results for an analysis run by super_id.

    Returns per-service status via latest_status_by_context and the final_result
    when all services have completed."""
    if not super_id:
        return "❌ Error: super_id is required. Call create_super_id_tool() first."
    result = await get_property_analysis_result(super_id)
    if result:
        return json.dumps(result)
    return f'{{"super_id": "{super_id}", "status": "pending"}}'


# ---------------------------------------------------------------------------
# Downstream-only triggers (kept; analysis services need direct access)
# ---------------------------------------------------------------------------


@mcp.tool()
async def trigger_floorplan_tool(
    super_id: str = "",
    property_id: str = "",
    floorplans_json: str = "",
) -> str:
    """Trigger floorplan analysis. Requires super_id, property_id, and a JSON object of floorplans
    (e.g. '{"fp1": {"url": "https://..."}}').
    Use create_super_id_tool() first to get a super_id if you don't have one.
    Use get_property_analysis_result_tool(super_id) to poll."""
    if not super_id:
        return "❌ Error: super_id is required. Call create_super_id_tool() first."
    if not property_id:
        return "❌ Error: property_id is required"
    if not floorplans_json:
        return "❌ Error: floorplans_json is required"

    try:
        floorplans = json.loads(floorplans_json)
    except json.JSONDecodeError:
        return "❌ Error: floorplans_json is not valid JSON"

    async with httpx.AsyncClient() as client:
        result = await trigger_floorplan_via_n8n(
            client=client,
            super_id=super_id,
            property_id=property_id,
            floorplans=floorplans,
        )
        return f"✅ Floorplan analysis triggered: {json.dumps(result)}"


@mcp.tool()
async def trigger_image_condition_tool(
    super_id: str = "",
    image_urls_json: str = "",
    property_id: str = "",
    bedrooms: str = "",
) -> str:
    """Trigger image condition analysis. Requires super_id and a JSON array of image URLs.
    Use create_super_id_tool() first to get a super_id if you don't have one.
    Use get_property_analysis_result_tool(super_id) to poll."""
    if not super_id:
        return "❌ Error: super_id is required. Call create_super_id_tool() first."
    if not image_urls_json:
        return "❌ Error: image_urls_json is required"

    try:
        image_urls = json.loads(image_urls_json)
    except json.JSONDecodeError:
        return "❌ Error: image_urls_json is not valid JSON"

    notes = {}
    if bedrooms:
        try:
            notes["bedrooms"] = int(bedrooms)
        except ValueError:
            pass

    async with httpx.AsyncClient() as client:
        result = await trigger_image_condition_via_n8n(
            client=client,
            super_id=super_id,
            image_urls=image_urls,
            property_id=property_id if property_id else None,
            notes=notes if notes else None,
        )
        return f"✅ Image condition analysis triggered: {json.dumps(result)}"


# ---------------------------------------------------------------------------
# Helpers + legacy
# ---------------------------------------------------------------------------


@mcp.tool()
async def create_super_id_tool() -> str:
    """Create a new super_id for tracking a property analysis session.
    Call this FIRST before using any other tool. The returned super_id links
    all service results (data capture, floorplan analysis, image condition analysis)
    together under one session."""
    try:
        async with httpx.AsyncClient() as client:
            token = await get_m2m_token(client)
            url = f"{settings.SUPER_ID_SERVICE_URL}/super_ids"
            resp = await client.post(
                url,
                json={"count": 1, "metadata": {}},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            super_id = str(data.get("super_id", ""))
            if not super_id:
                return f"❌ Error: Super ID service returned invalid response: {data}"
    except Exception as exc:
        logger.error("Failed to create super_id: %s", exc, exc_info=True)
        return f"❌ Error creating super_id: {exc}"

    # Seed local analysis_result row so polling works immediately
    async with AsyncSessionLocal() as session:
        try:
            await upsert_analysis_result(
                session,
                super_id,
                {"status": "pending", "n8n_triggered": False},
            )
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.error("Failed to seed analysis result: %s", exc, exc_info=True)

    return json.dumps({"super_id": super_id, "status": "created"})


@mcp.tool()
async def trigger_full_property_analysis_tool(
    property_url: str = "",
    workflow_callback_url: str = "",
    super_id: str = "",
    external_callback_url: str = "",
) -> str:
    """[Legacy] Trigger the full property analysis workflow via the old SuperSami trigger.
    Prefer full_analysis_primary_tool() for new usage."""
    if not property_url:
        return "❌ Error: property_url is required"

    async with httpx.AsyncClient() as client:
        result = await start_property_analysis_via_n8n(
            client=client,
            property_url=property_url,
            workflow_callback_url=(
                workflow_callback_url if workflow_callback_url else None
            ),
            super_id=(super_id if super_id else None),
            external_callback_url=(
                external_callback_url if external_callback_url else None
            ),
        )
        return f"✅ Analysis started: {json.dumps(result)}"
