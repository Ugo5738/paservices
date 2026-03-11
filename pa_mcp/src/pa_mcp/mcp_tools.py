import argparse
import json

import httpx
from fastmcp.server.dependencies import get_access_token
from mcp.server.fastmcp import FastMCP

from .config import settings
from .tools.data_capture_tools import list_properties, trigger_detailed_capture
from .tools.floorplan_tools import trigger_floorplan_analysis
from .tools.n8n_tools import (
    get_property_analysis_result,
    start_property_analysis_via_n8n,
)
from .tools.capture_service_tools import (
    capture_with_motie,
    check_property_fields,
    get_capture_run_result,
    get_capture_run_status,
    retry_capture_run,
    start_property_capture,
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
