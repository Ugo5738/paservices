import json
from urllib.parse import urlparse

import httpx
from mcp.server.fastmcp import FastMCP
from sqlalchemy.exc import SQLAlchemyError

from .config import settings
from .crud import upsert_analysis_result
from .db import AsyncSessionLocal
from .tools import v2_tools
from .tools.auth_helper import get_m2m_token
from .tools.n8n_service_tools import (
    trigger_data_capture_via_n8n,
    trigger_floorplan_via_n8n,
    trigger_image_condition_via_n8n,
    trigger_orchestrator_via_n8n,
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
# Grouped by what an external agent (ChatGPT, Claude, etc.) is trying to do:
#
#   Common case — full property analysis:
#     run_property_analysis_tool         (registry-first, AI fallback)
#     analyze_new_domain_property_tool   (force AI now + queue a coded build)
#     get_property_analysis_result_tool  (poll by super_id)
#
#   Just capture data, no downstream services:
#     fetch_with_registered_fetcher_tool (use the coded fetcher if registered)
#     fetch_with_ai_tool                 (multishot AI extraction)
#     firecrawl_fetch_tool               (single-shot Firecrawl, no fallback)
#     motie_fetch_tool                   (specific vendor: deployed Motie fetcher)
#
#   Manage / inspect coded fetchers:
#     list_registered_fetchers_tool      (which domains we already support)
#     build_fetcher_tool                 (end-to-end build for a new domain)
#     get_fetcher_build_status_tool      (poll an in-progress build)
#     motie_build_tool                   (vendor-specific: kick a Motie build)
#
#   Helpers:
#     create_super_id_tool               (start a session — call this FIRST)
#
#   Downstream-only triggers (when you already have media to analyse):
#     trigger_floorplan_tool
#     trigger_image_condition_tool
#
#   Legacy / deprecated (banner in the description tells the agent to switch):
#     trigger_full_property_analysis_tool
#     analyze_property_tool
#     trigger_orchestrated_analysis_tool
#     trigger_data_capture_tool
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Vendor-specific primitives — call these when you specifically want one
# vendor (no registry lookup, no fallback).
# ---------------------------------------------------------------------------


# @mcp.tool()
# async def firecrawl_fetch_tool(
#     url: str = "",
#     super_id: str = "",
#     prompt: str = "",
# ) -> str:
#     """Single-shot Firecrawl AI extraction for a property URL.

#     Calls the Firecrawl FIRE-1 agent directly — no domain registry lookup,
#     no multishot, no fallback to other vendors. Returns parsed property
#     fields, a presence map, a completeness score, and a `run_id` for the
#     audit trail.

#     Optional `prompt` overrides the default extraction prompt.

#     Single attempt only — for higher-quality multishot extraction (two
#     attempts with focused retry, picks the better result), use
#     `fetch_with_ai_tool`.
#     """
#     if not url:
#         return "❌ Error: url is required"
#     async with httpx.AsyncClient() as client:
#         try:
#             result = await v2_tools.firecrawl_fetch(
#                 client,
#                 url=url,
#                 super_id=super_id or None,
#                 prompt=prompt or None,
#             )
#         except Exception as exc:  # noqa: BLE001
#             logger.error("firecrawl_fetch_tool failed: %s", exc, exc_info=True)
#             return f"❌ Error: {exc}"
#     return json.dumps(result)


# @mcp.tool()
# async def motie_fetch_tool(
#     url: str = "",
#     super_id: str = "",
# ) -> str:
#     """Run the deployed Motie-built fetcher for this URL's domain.

#     Motie is the AI-coding-agent vendor we use to autogenerate property
#     fetchers. If a Motie fetcher has already been built and registered
#     for this domain, this runs it and returns the captured fields.

#     Returns `error: no_fetcher_for_domain` if there is no Motie fetcher
#     registered for the domain — in that case use `build_fetcher_tool`
#     (end-to-end build) or `fetch_with_ai_tool` (one-shot AI extraction).
#     """
#     if not url:
#         return "❌ Error: url is required"
#     async with httpx.AsyncClient() as client:
#         try:
#             result = await v2_tools.motie_fetch(
#                 client, url=url, super_id=super_id or None
#             )
#         except Exception as exc:  # noqa: BLE001
#             logger.error("motie_fetch_tool failed: %s", exc, exc_info=True)
#             return f"❌ Error: {exc}"
#     return json.dumps(result)


# @mcp.tool()
# async def motie_build_tool(
#     url: str = "",
#     prompt_kind: str = "build",
#     failing_error: str = "",
#     benchmark_fields_json: str = "",
# ) -> str:
#     """Kick off a Motie agent run to build a new fetcher for this URL's domain.

#     Returns immediately with `build_id` and `state: session_running`. Poll
#     progress with `get_fetcher_build_status_tool(build_id)` until terminal
#     (`deployed` | `session_failed` | `deployment_failed`).

#     For a one-call end-to-end build that scores, publishes, and registers
#     the result automatically, use `build_fetcher_tool` instead.

#     `prompt_kind`:
#       - `build` (default) — initial build for a brand-new domain.
#       - `repair` — fix an existing fetcher that's failing; requires
#         `failing_error` describing what went wrong.

#     `benchmark_fields_json` (optional) is a JSON dict of reference fields
#     extracted by the AI fetcher — Motie uses these to verify the fetcher
#     it builds actually returns the right shape.
#     """
#     if not url:
#         return "❌ Error: url is required"
#     benchmark_fields = None
#     if benchmark_fields_json:
#         try:
#             benchmark_fields = json.loads(benchmark_fields_json)
#         except json.JSONDecodeError:
#             return "❌ Error: benchmark_fields_json is not valid JSON"
#     async with httpx.AsyncClient() as client:
#         try:
#             result = await v2_tools.motie_build_start(
#                 client,
#                 url=url,
#                 prompt_kind=prompt_kind or "build",
#                 failing_error=failing_error or None,
#                 benchmark_fields=benchmark_fields,
#             )
#         except Exception as exc:  # noqa: BLE001
#             logger.error("motie_build_tool failed: %s", exc, exc_info=True)
#             return f"❌ Error: {exc}"
#     return json.dumps(result)


# ---------------------------------------------------------------------------
# Reusable capture flows — vendor-agnostic.
# ---------------------------------------------------------------------------


# @mcp.tool()
# async def fetch_with_registered_fetcher_tool(
#     url: str = "",
#     super_id: str = "",
# ) -> str:
#     """Capture property data using whichever coded fetcher is registered for
#     this URL's domain.

#     Vendor-agnostic — the system picks which fetcher to run based on the
#     URL's domain. Returns:
#       - `status: "no_fetcher"` — no fetcher registered for this domain
#         (try `analyze_new_domain_property_tool` or `build_fetcher_tool`)
#       - `status: "pass"` — captured data met the quality threshold
#       - `status: "fail"` — fetcher ran but the captured data was below
#         threshold (consider AI extraction via `fetch_with_ai_tool`)
#     """
#     if not url:
#         return "❌ Error: url is required"
#     async with httpx.AsyncClient() as client:
#         try:
#             result = await v2_tools.fetch_with_pre_built(
#                 client, url=url, super_id=super_id or None
#             )
#         except Exception as exc:  # noqa: BLE001
#             logger.error(
#                 "fetch_with_registered_fetcher_tool failed: %s", exc, exc_info=True
#             )
#             return f"❌ Error: {exc}"
#     return json.dumps(result)


# @mcp.tool()
# async def fetch_with_ai_tool(
#     url: str = "",
#     super_id: str = "",
# ) -> str:
#     """Capture property data with AI multishot extraction.

#     Two-attempt strategy: runs the default extraction prompt first; if the
#     output doesn't meet the quality threshold, runs a second focused prompt
#     naming the missing fields, then returns whichever attempt scored higher.
#     Response includes both `data` (the winner) and `attempts: [...]` so the
#     caller can inspect both runs for diagnostics.

#     Use when you want AI-extraction quality directly — e.g. the domain has
#     no registered fetcher yet, or a registered fetcher returned weak data.
#     """
#     if not url:
#         return "❌ Error: url is required"
#     async with httpx.AsyncClient() as client:
#         try:
#             result = await v2_tools.fetch_with_ai(
#                 client, url=url, super_id=super_id or None
#             )
#         except Exception as exc:  # noqa: BLE001
#             logger.error("fetch_with_ai_tool failed: %s", exc, exc_info=True)
#             return f"❌ Error: {exc}"
#     return json.dumps(result)


# @mcp.tool()
# async def build_fetcher_tool(
#     url: str = "",
#     super_id: str = "",
#     poll_interval: str = "15",
#     poll_timeout: str = "1800",
# ) -> str:
#     """End-to-end coded-fetcher build for a brand-new domain.

#     One call kicks off the build, polls until terminal, scores the deployed
#     fetcher against an AI baseline, publishes the artefact, and registers
#     the resulting routes. After it completes successfully the domain is
#     listed by `list_registered_fetchers_tool` and runnable via
#     `fetch_with_registered_fetcher_tool`.

#     `poll_interval` (sec, default 15) — between status checks.
#     `poll_timeout` (sec, default 1800 = 30min) — total wait before giving up.

#     Long-running (typical 5–15 min, sometimes longer). If you'd rather drive
#     polling yourself, use `motie_build_tool` + `get_fetcher_build_status_tool`
#     instead.
#     """
#     if not url:
#         return "❌ Error: url is required"
#     try:
#         interval = float(poll_interval) if poll_interval else 15.0
#         timeout = float(poll_timeout) if poll_timeout else 1800.0
#     except ValueError:
#         return "❌ Error: poll_interval and poll_timeout must be numbers"
#     async with httpx.AsyncClient() as client:
#         try:
#             result = await v2_tools.build_fetcher(
#                 client,
#                 url=url,
#                 super_id=super_id or None,
#                 poll_interval=interval,
#                 poll_timeout=timeout,
#             )
#         except Exception as exc:  # noqa: BLE001
#             logger.error("build_fetcher_tool failed: %s", exc, exc_info=True)
#             return f"❌ Error: {exc}"
#     return json.dumps(result)


# ---------------------------------------------------------------------------
# Top-level entry points — full property analysis pipelines.
# These are what an external agent (ChatGPT, Claude) will use 90% of the time.
# ---------------------------------------------------------------------------


@mcp.tool()
async def run_property_analysis_tool(
    property_url: str = "",
    services_json: str = "",
    super_id: str = "",
    callback_url: str = "",
    service_params_json: str = "",
) -> str:
    """Run the full property analysis pipeline for a listing URL.

    This is the default end-to-end entry point. The system:
      1. Tries the registered coded fetcher for the URL's domain first.
      2. Falls through to AI extraction if no coded fetcher exists or the
         coded fetcher returned weak data.
      3. Forwards the captured property data to your `callback_url` (if
         supplied) and to the result store.
      4. Fans out to floorplan analysis and image-condition analysis on the
         captured media (when those services are requested).

    `services_json` (optional) — JSON array of services to run. Defaults to
    all three: `["data_capture","floorplan_analysis","image_condition_analysis"]`.
    Pass a subset (e.g. `["data_capture"]`) to skip downstream services.
    Legacy aliases `data_capture_motie` / `data_capture_rightmove` are also
    accepted; both route through the vendor-agnostic fetcher registry.

    `service_params_json` (optional) — per-service parameter overrides.

    `super_id` (optional) — supply one from `create_super_id_tool` if you
    want to attach this analysis to an existing session; otherwise one is
    generated for you and returned.

    `callback_url` (optional) — final results are POSTed here when ready.

    Returns 202 immediately with a `super_id`. Poll progress with
    `get_property_analysis_result_tool(super_id)`, or set `callback_url`
    to receive the final result asynchronously.
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
            logger.error("run_property_analysis_tool failed: %s", exc, exc_info=True)
            return f"❌ Error: {exc}"
    return json.dumps(result)


@mcp.tool()
async def analyze_new_domain_property_tool(
    property_url: str = "",
    super_id: str = "",
    callback_url: str = "",
) -> str:
    """Analyse a property on a domain that doesn't have a coded fetcher yet.

    Skips the registry lookup and goes straight to multishot AI extraction
    so you get usable data right now. As a side-effect, queues a build
    request so the system can autogenerate a coded fetcher for this domain
    in the background — next time the same domain is analysed, the cheaper
    coded path will already exist.

    Use this when you know the domain is new (e.g. a portal we haven't
    onboarded), or when you specifically want AI-quality extraction over
    a quick coded-fetcher result.

    Returns the AI extraction result immediately, plus `build_queued: true`
    confirming the coded-fetcher build was queued.
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
            logger.error(
                "analyze_new_domain_property_tool failed: %s", exc, exc_info=True
            )
            return f"❌ Error: {exc}"
    return json.dumps(result)


# ---------------------------------------------------------------------------
# Inspection / discovery tools
# ---------------------------------------------------------------------------


# @mcp.tool()
# async def list_registered_fetchers_tool(
#     domain: str = "",
#     source_type: str = "",
#     status: str = "",
# ) -> str:
#     """List the coded fetchers currently registered in the system.

#     Lets an agent discover which property domains we already support before
#     deciding whether to call `fetch_with_registered_fetcher_tool`,
#     `analyze_new_domain_property_tool`, or `build_fetcher_tool`.

#     Filters (all optional):
#       - `domain` — exact match on the fetcher's domain (case-insensitive).
#       - `source_type` — `motie` (Motie-built code) or `proxy` (a domain
#         proxy service like the Rightmove API wrapper).
#       - `status` — `active` or `disabled`. Defaults to all.

#     Returns each fetcher's id, domain, source_type, route_path, http_method,
#     api_url, param_schema, and status.
#     """
#     async with httpx.AsyncClient() as client:
#         try:
#             result = await v2_tools.list_fetchers(
#                 client,
#                 domain=domain or None,
#                 source_type=source_type or None,
#                 status=status or None,
#             )
#         except Exception as exc:  # noqa: BLE001
#             logger.error("list_registered_fetchers_tool failed: %s", exc, exc_info=True)
#             return f"❌ Error: {exc}"
#     return json.dumps(result)


# @mcp.tool()
# async def get_fetcher_build_status_tool(build_id: str = "") -> str:
#     """Poll the status of an in-progress fetcher build.

#     Returns `build_id`, `state`, `session_id`, `deployment_id`, `api_url`
#     (once deployed), `benchmark_score` (once scored), `error_message`,
#     `is_terminal`.

#     Use this after `motie_build_tool` returns a `build_id`, or to inspect
#     historical build attempts. Terminal states: `deployed`, `session_failed`,
#     `deployment_failed`.
#     """
#     if not build_id:
#         return "❌ Error: build_id is required"
#     async with httpx.AsyncClient() as client:
#         try:
#             result = await v2_tools.get_motie_build_status(client, build_id)
#         except Exception as exc:  # noqa: BLE001
#             logger.error("get_fetcher_build_status_tool failed: %s", exc, exc_info=True)
#             return f"❌ Error: {exc}"
#     return json.dumps(result)


@mcp.tool()
async def get_property_analysis_result_tool(super_id: str = "") -> str:
    """Fetch the status and results for an analysis run by `super_id`.

    `super_id` is the session ID returned by `run_property_analysis_tool`,
    `analyze_new_domain_property_tool`, or `create_super_id_tool`.

    Returns:
      - `status` — `pending` while services are still running, `completed`
        when all requested services have reported back.
      - `latest_status_by_context` — per-service rollup
        (`data_capture`, `floorplan_analysis`, `image_condition_analysis`).
      - `final_result` — the merged property data, populated once data
        capture completes; downstream service results are merged in as
        they arrive.

    Safe to poll repeatedly — typical end-to-end takes 30–90 seconds.
    """
    if not super_id:
        return "❌ Error: super_id is required. Call create_super_id_tool() first."
    result = await get_property_analysis_result(super_id)
    if result:
        return json.dumps(result)
    return f'{{"super_id": "{super_id}", "status": "pending"}}'


# ---------------------------------------------------------------------------
# Downstream-only triggers — use these when you already have property media
# (e.g. from a prior analysis or a manual upload) and just want one of the
# downstream analysis services without re-capturing the listing.
# ---------------------------------------------------------------------------


@mcp.tool()
async def trigger_floorplan_tool(
    super_id: str = "",
    property_id: str = "",
    floorplans_json: str = "",
) -> str:
    """Trigger floorplan analysis on a set of floorplan images.

    Requires `super_id`, `property_id`, and `floorplans_json` — a JSON
    object mapping floorplan keys to `{url}` dicts, e.g.
    `'{"fp1": {"url": "https://..."}, "fp2": {"url": "https://..."}}'`.

    Use `create_super_id_tool` first to get a `super_id` if you don't
    already have one, and `get_property_analysis_result_tool` to poll
    for the result.
    """
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
    """Trigger image condition analysis on a list of property image URLs.

    Requires `super_id` and `image_urls_json` (JSON array of image URL
    strings). Optional: `property_id`, `bedrooms`.

    Use `create_super_id_tool` first to get a `super_id` if you don't
    already have one, and `get_property_analysis_result_tool` to poll
    for the result.
    """
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
# Session helpers + legacy/deprecated tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def create_super_id_tool() -> str:
    """Create a new session ID (`super_id`) for tracking a property analysis.

    A `super_id` is the system's session identifier — every analysis call
    is tagged with one, and every result (data capture, floorplan analysis,
    image condition analysis) is keyed by it so they can all be retrieved
    together.

    Most top-level tools (`run_property_analysis_tool`,
    `analyze_new_domain_property_tool`) will create a `super_id` for you
    automatically if you don't pass one. Call this tool explicitly when
    you want to start a session up front (e.g. so you can pass the same
    `super_id` to multiple downstream services that you want grouped under
    one analysis).
    """
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

    # Chunk 4.5: record the initial mint as an activity event on the
    # SuperID Metadata store. This is the first event in the SuperID's
    # life — every downstream service's activity record will reference
    # the same super_id, giving a complete audit trail in one place.
    # Non-blocking — failure here doesn't undo the mint.
    from .tools.super_id_service_tools import record_activity

    await record_activity(
        super_id=super_id,
        used_by="pa_mcp",
        source="pa_mcp/super_id_created",
        metadata={"tool": "create_super_id_tool"},
    )

    return json.dumps({"super_id": super_id, "status": "created"})


@mcp.tool()
async def trigger_full_property_analysis_tool(
    property_url: str = "",
    workflow_callback_url: str = "",
    super_id: str = "",
    external_callback_url: str = "",
) -> str:
    """[DEPRECATED] Old entry point for full property analysis.

    Use `run_property_analysis_tool` instead. Kept for backwards
    compatibility with existing callers.
    """
    logger.warning(
        "trigger_full_property_analysis_tool is deprecated; "
        "prefer run_property_analysis_tool"
    )
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


@mcp.tool()
async def analyze_property_tool(
    property_url: str = "",
    super_id: str = "",
) -> str:
    """[DEPRECATED] Run the complete property analysis pipeline for a listing URL.

    Use `run_property_analysis_tool` instead. This older tool hardcodes
    vendor selection by domain string (e.g. picks the Rightmove proxy for
    rightmove.co.uk and Motie otherwise), bypassing the vendor-agnostic
    fetcher registry. Kept for backwards compatibility with existing callers.

    Returns a `super_id`. Use `get_property_analysis_result_tool(super_id)`
    to poll for the result.
    """
    logger.warning(
        "analyze_property_tool is deprecated (vendor-coupled routing); "
        "prefer run_property_analysis_tool"
    )
    if not property_url:
        return "❌ Error: property_url is required"

    domain = urlparse(property_url).netloc.lower().replace("www.", "")
    if "rightmove.co.uk" in domain:
        data_capture_service = "data_capture_rightmove"
    else:
        data_capture_service = "data_capture_motie"

    async with httpx.AsyncClient() as client:
        result = await trigger_orchestrator_via_n8n(
            client=client,
            property_url=property_url,
            services=[
                data_capture_service,
                "floorplan_analysis",
                "image_condition_analysis",
            ],
            super_id=super_id if super_id else None,
        )
        return f"✅ Full analysis started: {json.dumps(result)}"


@mcp.tool()
async def trigger_orchestrated_analysis_tool(
    property_url: str = "",
    services_json: str = "",
    service_params_json: str = "",
    super_id: str = "",
) -> str:
    """[DEPRECATED] Trigger an orchestrated analysis with a custom combination of services.

    Use `run_property_analysis_tool` instead — same shape, but uses the
    current vendor-agnostic fetcher registry rather than the older
    vendor-coupled routing this tool used. Kept for backwards compatibility.

    `services_json`: JSON array of service names, e.g.
    `'["data_capture_motie", "floorplan_analysis"]'`. Valid names:
    `data_capture_motie`, `data_capture_rightmove`, `floorplan_analysis`,
    `image_condition_analysis`.
    """
    logger.warning(
        "trigger_orchestrated_analysis_tool is deprecated; "
        "prefer run_property_analysis_tool"
    )
    if not property_url:
        return "❌ Error: property_url is required"
    if not services_json:
        return "❌ Error: services_json is required"

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
        result = await trigger_orchestrator_via_n8n(
            client=client,
            property_url=property_url,
            services=services,
            service_params=service_params,
            super_id=super_id if super_id else None,
        )
        return f"✅ Orchestrated analysis triggered: {json.dumps(result)}"


@mcp.tool()
async def trigger_data_capture_tool(
    url: str = "",
    super_id: str = "",
    skip_baseline: str = "",
) -> str:
    """[DEPRECATED] Trigger property data capture for a listing URL with vendor-by-domain routing.

    Use `fetch_with_registered_fetcher_tool` (registry-driven, vendor-agnostic)
    or `motie_fetch_tool` / `firecrawl_fetch_tool` (explicit vendor) instead.
    This older tool hardcodes "rightmove → Rightmove proxy, else → Motie",
    bypassing the vendor-agnostic registry. Kept for backwards compatibility.
    """
    logger.warning(
        "trigger_data_capture_tool is deprecated (vendor-coupled routing); "
        "prefer fetch_with_registered_fetcher_tool, motie_fetch_tool, or "
        "firecrawl_fetch_tool"
    )
    if not url:
        return "❌ Error: url is required"

    domain = urlparse(url).netloc.lower().replace("www.", "")
    if "rightmove.co.uk" in domain:
        async with httpx.AsyncClient() as client:
            result = await trigger_orchestrator_via_n8n(
                client=client,
                property_url=url,
                services=["data_capture_rightmove"],
                super_id=super_id if super_id else None,
            )
            return f"✅ Data capture triggered: {json.dumps(result)}"
    else:
        async with httpx.AsyncClient() as client:
            result = await trigger_data_capture_via_n8n(
                client=client,
                url=url,
                super_id=super_id if super_id else None,
                skip_baseline=(
                    skip_baseline.lower() == "true" if skip_baseline else False
                ),
            )
            return f"✅ Data capture triggered: {json.dumps(result)}"
