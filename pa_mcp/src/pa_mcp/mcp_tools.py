import json
from urllib.parse import urlparse

import httpx
from mcp.server.fastmcp import FastMCP
from sqlalchemy.exc import SQLAlchemyError

from .config import settings
from .crud import upsert_analysis_result
from .db import AsyncSessionLocal
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
# V2 Orchestrated Tools (primary agent interface)
# ---------------------------------------------------------------------------


@mcp.tool()
async def analyze_property_tool(
    property_url: str = "",
    super_id: str = "",
) -> str:
    """Run the complete property analysis pipeline for a listing URL.

    This triggers all services in the correct order:
    1. Capture property data from the listing
    2. Extract floorplan and image URLs from captured data
    3. Run floorplan analysis and image condition analysis in parallel

    Returns a super_id. Use get_property_analysis_result_tool(super_id) to
    poll progress and retrieve the final combined result.
    """
    if not property_url:
        return "❌ Error: property_url is required"

    # Auto-pick data capture adapter based on domain
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
    """Trigger an orchestrated analysis with a custom combination of services.

    services_json: JSON array of service names, e.g. '["data_capture_motie", "floorplan_analysis"]'.
    Valid service names: data_capture_motie, data_capture_rightmove, floorplan_analysis, image_condition_analysis.

    service_params_json: Optional JSON object with per-service params, e.g.
    '{"floorplan_analysis": {"property_id": "123", "floorplans": {"fp1": {"url": "..."}}}, "image_condition_analysis": {"image_urls": ["..."]}}'.

    Returns a super_id. Use get_property_analysis_result_tool(super_id) to poll progress.
    """
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
    """Trigger property data capture for a listing URL.
    Automatically picks the best adapter based on the domain (Rightmove vs other).
    Returns a super_id for tracking. Use get_property_analysis_result_tool(super_id) to poll.
    """
    if not url:
        return "❌ Error: url is required"

    # Auto-pick adapter based on domain
    domain = urlparse(url).netloc.lower().replace("www.", "")
    if "rightmove.co.uk" in domain:
        # Use orchestrator with rightmove adapter
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
                skip_baseline=skip_baseline.lower() == "true" if skip_baseline else False,
            )
            return f"✅ Data capture triggered: {json.dumps(result)}"


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
# Legacy tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def trigger_full_property_analysis_tool(
    property_url: str = "",
    workflow_callback_url: str = "",
    super_id: str = "",
    external_callback_url: str = "",
) -> str:
    """[Legacy] Trigger the full property analysis workflow via the old SuperSami trigger.
    Prefer analyze_property_tool() for new usage."""
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


# @mcp.tool()
# async def trigger_rightmove_capture_tool(
#     property_url: str = "",
#     super_id: str = "",
# ) -> str:
#     """[Legacy] Trigger Rightmove data capture via its dedicated n8n workflow."""
#     ...


# ---------------------------------------------------------------------------
# Direct API tools (commented out — use orchestrated tools above instead)
# ---------------------------------------------------------------------------

# @mcp.tool()
# async def capture_property_data_tool(url, super_id, skip_baseline): ...
# @mcp.tool()
# async def capture_property_with_motie_tool(url, super_id): ...
# @mcp.tool()
# async def check_property_fields_tool(url): ...
# @mcp.tool()
# async def get_capture_run_status_tool(run_id): ...
# @mcp.tool()
# async def get_capture_run_result_tool(run_id): ...
# @mcp.tool()
# async def retry_capture_run_tool(run_id): ...
# @mcp.tool()
# async def trigger_floorplan_analysis_tool(floorplan_key, ...): ...
@mcp.tool()
async def create_super_id_tool() -> str:
    """Create a new super_id for tracking a property analysis session.
    Call this FIRST before using any other tool. The returned super_id links
    all service results (data capture, floorplan analysis, image condition analysis)
    together under one session.

    Flow: create_super_id_tool() → pass super_id to analyze_property_tool(),
    trigger_floorplan_tool(), trigger_image_condition_tool(), etc."""
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


# @mcp.tool()
# async def list_properties_tool(...): ...
