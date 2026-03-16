import argparse
import json

import httpx
from fastmcp.server.dependencies import get_access_token
from mcp.server.fastmcp import FastMCP

from .config import settings
from .tools.capture_service_tools import (
    capture_with_motie,
    check_property_fields,
    get_capture_run_result,
    get_capture_run_status,
    retry_capture_run,
    start_property_capture,
)
from .tools.data_capture_tools import list_properties, trigger_detailed_capture
from .tools.floorplan_tools import trigger_floorplan_analysis
from .tools.n8n_service_tools import (
    trigger_data_capture_via_n8n,
    trigger_floorplan_via_n8n,
    trigger_image_condition_via_n8n,
    trigger_orchestrator_via_n8n,
    trigger_rightmove_via_n8n,
)
from .tools.n8n_tools import (
    get_property_analysis_result,
    start_property_analysis_via_n8n,
)
from .tools.super_id_service_tools import create_super_id
from .utils.logging_config import logger

# Create an MCP server
mcp = FastMCP(name=settings.PROJECT_NAME)


@mcp.tool()
async def trigger_floorplan_analysis_tool(
    floorplan_key: str = "",
    floorplan_url: str = "",
    super_id: str = "",
    property_id: str = "",
) -> str:
    """Trigger the Floorplan Service to analyze a single floorplan image."""
    if not floorplan_key:
        return "❌ Error: floorplan_key is required"

    access_token = None
    try:
        access_token = get_access_token()
    except Exception:
        access_token = None

    raw_token = None
    if isinstance(access_token, str):
        raw_token = access_token
    elif access_token is not None:
        raw_token = getattr(access_token, "token", None) or getattr(
            access_token, "encoded", None
        )

    # If no super_id provided, create one
    if not super_id:
        super_id = await create_super_id(prefix="fp_", token=raw_token)

    async with httpx.AsyncClient() as client:
        result = await trigger_floorplan_analysis(
            client=client,
            token=raw_token,
            floorplan_key=floorplan_key,
            floorplan_url=floorplan_url,
            super_id=super_id,
            property_id=property_id,
        )
        return f"✅ Analysis triggered: {result}"


@mcp.tool()
async def create_super_id_tool(prefix: str = "") -> str:
    """Create a super_id via the Super ID Service."""
    if not prefix:
        prefix = "id_"

    access_token = None
    try:
        access_token = get_access_token()
    except Exception:
        pass

    raw_token = None
    if access_token:
        # Check for permissions if we have a token
        claims = getattr(access_token, "claims", {}) or {}
        perms = claims.get("permissions", []) or claims.get("scopes", [])
        if "super_id:generate" not in perms:
            logger.warning("Permission denied: Missing 'super_id:generate' permission.")
            return "❌ Error: insufficient_permissions"

        raw_token = getattr(access_token, "token", None) or getattr(
            access_token, "encoded", None
        )

    result = await create_super_id(token=raw_token, prefix=prefix)
    return f"✅ Super ID created: {result}"


@mcp.tool()
async def list_properties_tool(
    on_date: str = "",
    from_time: str = "",
    to_time: str = "",
    min_bedrooms: str = "",
    max_bedrooms: str = "",
    min_bathrooms: str = "",
    max_bathrooms: str = "",
) -> str:
    """List properties using the Data Capture service."""
    # Convert string args to appropriate types for Namespace
    args = argparse.Namespace(
        date=on_date if on_date else None,
        from_time=from_time if from_time else None,
        to_time=to_time if to_time else None,
        min_bedrooms=int(min_bedrooms) if min_bedrooms.strip() else None,
        max_bedrooms=int(max_bedrooms) if max_bedrooms.strip() else None,
        min_bathrooms=int(min_bathrooms) if min_bathrooms.strip() else None,
        max_bathrooms=int(max_bathrooms) if max_bathrooms.strip() else None,
    )

    properties = await list_properties(args)
    return f"✅ Properties found: {len(properties)}"  # Simplified summary return


# @mcp.tool()
# async def trigger_property_capture_tool(
#     property_url: str,
#     super_id: str = "",
# ) -> str:
#     """Trigger the Data Capture Rightmove Service to capture a property URL."""
#     access_token = None
#     try:
#         access_token = get_access_token()
#     except Exception:
#         access_token = None

#     raw_token = None
#     if isinstance(access_token, str):
#         raw_token = access_token
#     elif access_token is not None:
#         # Try common attributes used by FastMCP access token wrappers
#         raw_token = getattr(access_token, "token", None) or getattr(
#             access_token, "encoded", None
#         )

#     # If no super_id provided, create one
#     if not super_id:
#         super_id = await create_super_id(prefix="fp_", token=raw_token)

#     async with httpx.AsyncClient() as client:
#         return await trigger_detailed_capture(
#             client=client,
#             token=raw_token,
#             property_url=property_url,
#             capture_super_id=super_id,
#         )


@mcp.tool()
async def trigger_full_property_analysis_tool(
    property_url: str = "",
    workflow_callback_url: str = "",
    super_id: str = "",
    external_callback_url: str = "",
) -> str:
    """Trigger the full property analysis workflow."""
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
async def get_property_analysis_result_tool(super_id: str = "") -> str:
    """Fetch the stored property analysis result for a given super_id."""
    if not super_id:
        return "❌ Error: super_id is required"

    result = await get_property_analysis_result(super_id)
    if result:
        return json.dumps(result)
    return f'{{"super_id": "{super_id}", "status": "pending"}}'


# --- Property Data Capture Tools ---


def _get_raw_token():
    """Extract raw token string from FastMCP access token."""
    try:
        access_token = get_access_token()
    except Exception:
        return None

    if isinstance(access_token, str):
        return access_token
    if access_token is not None:
        return getattr(access_token, "token", None) or getattr(
            access_token, "encoded", None
        )
    return None


@mcp.tool()
async def capture_property_data_tool(
    url: str = "",
    super_id: str = "",
    skip_baseline: str = "",
) -> str:
    """Start the full property data capture pipeline for a listing URL. Returns a run_id for polling."""
    if not url:
        return "❌ Error: url is required"

    token = _get_raw_token()
    result = await start_property_capture(
        url=url,
        super_id=super_id if super_id else None,
        skip_baseline=skip_baseline.lower() == "true" if skip_baseline else False,
        token=token,
    )
    return f"✅ Capture started: {json.dumps(result)}"


@mcp.tool()
async def capture_property_with_motie_tool(
    url: str = "",
    super_id: str = "",
) -> str:
    """Extract property data from a listing URL using the Motie AI adapter (includes baseline validation)."""
    if not url:
        return "❌ Error: url is required"

    token = _get_raw_token()
    result = await capture_with_motie(
        url=url,
        super_id=super_id if super_id else None,
        token=token,
    )
    return f"✅ Motie extraction started: {json.dumps(result)}"


@mcp.tool()
async def check_property_fields_tool(url: str = "") -> str:
    """Quick baseline field-presence check for a property listing URL. Returns which data fields are available."""
    if not url:
        return "❌ Error: url is required"

    token = _get_raw_token()
    result = await check_property_fields(url=url, token=token)
    return f"✅ Field check complete: {json.dumps(result)}"


@mcp.tool()
async def get_capture_run_status_tool(run_id: str = "") -> str:
    """Poll the status of a property data capture run by its run_id."""
    if not run_id:
        return "❌ Error: run_id is required"

    token = _get_raw_token()
    result = await get_capture_run_status(run_id=run_id, token=token)
    return json.dumps(result)


@mcp.tool()
async def get_capture_run_result_tool(run_id: str = "") -> str:
    """Get the canonical property data result of a completed capture run."""
    if not run_id:
        return "❌ Error: run_id is required"

    token = _get_raw_token()
    result = await get_capture_run_result(run_id=run_id, token=token)
    return json.dumps(result)


@mcp.tool()
async def retry_capture_run_tool(run_id: str = "") -> str:
    """Retry a failed or warning-status property data capture run."""
    if not run_id:
        return "❌ Error: run_id is required"

    token = _get_raw_token()
    result = await retry_capture_run(run_id=run_id, token=token)
    return f"✅ Retry started: {json.dumps(result)}"


# ---------------------------------------------------------------------------
# Per-service n8n workflow tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def trigger_rightmove_capture_tool(
    property_url: str = "",
    super_id: str = "",
) -> str:
    """Trigger the Rightmove data capture via its dedicated n8n workflow. Returns a super_id for tracking."""
    if not property_url:
        return "❌ Error: property_url is required"

    async with httpx.AsyncClient() as client:
        result = await trigger_rightmove_via_n8n(
            client=client,
            property_url=property_url,
            super_id=super_id if super_id else None,
        )
        return f"✅ Rightmove capture triggered: {json.dumps(result)}"


@mcp.tool()
async def trigger_data_capture_tool(
    url: str = "",
    super_id: str = "",
    skip_baseline: str = "",
) -> str:
    """Trigger property data capture (Motie) via its dedicated n8n workflow. Use for non-Rightmove URLs. Returns a super_id for tracking."""
    if not url:
        return "❌ Error: url is required"

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
    """Trigger floorplan analysis via its dedicated n8n workflow. Requires super_id, property_id, and a JSON object of floorplans (e.g. '{"fp1": {"url": "https://..."}}')."""
    if not super_id:
        return "❌ Error: super_id is required"
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
    """Trigger image condition analysis via its dedicated n8n workflow. Requires super_id and a JSON array of image URLs."""
    if not super_id:
        return "❌ Error: super_id is required"
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
async def trigger_orchestrated_analysis_tool(
    property_url: str = "",
    services_json: str = "",
    service_params_json: str = "",
    super_id: str = "",
) -> str:
    """Trigger an orchestrated analysis that runs multiple services in sequence under one super_id.

    services_json: JSON array of service names, e.g. '["data_capture_rightmove", "floorplan_analysis", "image_condition_analysis"]'.
    Valid service names: data_capture_rightmove, data_capture_motie, floorplan_analysis, image_condition_analysis.

    service_params_json: Optional JSON object with per-service params, e.g.
    '{"floorplan_analysis": {"property_id": "123", "floorplans": {"fp1": {"url": "..."}}}, "image_condition_analysis": {"image_urls": ["..."]}}'.
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
