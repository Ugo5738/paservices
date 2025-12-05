import argparse
from typing import Optional
from urllib.parse import urlparse

import httpx
from fastmcp.server.dependencies import get_access_token
from mcp.server.fastmcp import FastMCP

from .config import settings
from .tools.data_capture_tools import list_properties  # , trigger_detailed_scrape
from .tools.floorplan_tools import trigger_floorplan_analysis
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
    floorplan_key: str, floorplan_url: str, super_id: Optional[str], property_id: str
) -> bool:
    """Trigger the Floorplan Service to analyze a single floorplan image.

    Uses FastMCP context to get an access token if available and forwards it.
    """
    access_token = None
    try:
        access_token = get_access_token()
    except Exception:
        access_token = None

    raw_token: Optional[str] = None
    if isinstance(access_token, str):
        raw_token = access_token
    elif access_token is not None:
        # Try common attributes used by FastMCP access token wrappers
        raw_token = getattr(access_token, "token", None) or getattr(
            access_token, "encoded", None
        )

    # If no super_id provided, create one
    if not super_id:
        super_id = await create_super_id(prefix="fp_", token=raw_token)

    async with httpx.AsyncClient() as client:
        return await trigger_floorplan_analysis(
            client=client,
            token=raw_token,
            floorplan_key=floorplan_key,
            floorplan_url=floorplan_url,
            super_id=super_id,
            property_id=property_id,
        )


@mcp.tool()
async def create_super_id_tool(prefix: str = "id_") -> str:
    """
    Create a super_id via the Super ID Service.
    This wrapper handles authentication and permission checks before calling the pure tool.
    """
    access_token = None
    try:
        access_token = get_access_token()
    except Exception:
        # Continue without authentication for internal calls
        pass

    raw_token: Optional[str] = None
    if access_token:
        # Check for permissions if we have a token
        claims = getattr(access_token, "claims", {}) or {}
        perms = claims.get("permissions", []) or claims.get("scopes", [])
        if "super_id:generate" not in perms:
            logger.warning("Permission denied: Missing 'super_id:generate' permission.")
            raise Exception("insufficient_permissions")

        # Extract the raw token string to pass to the tool
        raw_token = getattr(access_token, "token", None) or getattr(
            access_token, "encoded", None
        )

    # Call the pure, refactored tool with the token
    return await create_super_id(token=raw_token, prefix=prefix)


@mcp.tool()
async def list_properties_tool(
    on_date: Optional[str] = None,
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
    min_bedrooms: Optional[int] = None,
    max_bedrooms: Optional[int] = None,
    min_bathrooms: Optional[int] = None,
    max_bathrooms: Optional[int] = None,
) -> list:
    """List properties using the Data Capture service. Builds a small argparse.Namespace and calls the internal tool."""
    args = argparse.Namespace(
        date=on_date,
        from_time=from_time,
        to_time=to_time,
        min_bedrooms=min_bedrooms,
        max_bedrooms=max_bedrooms,
        min_bathrooms=min_bathrooms,
        max_bathrooms=max_bathrooms,
    )

    return await list_properties(args)


# @mcp.tool()
# async def trigger_property_scrape(
#     property_url: str,
#     super_id: Optional[str],
# ) -> bool:
#     """Trigger the get details to analyze a single floorplan image."""
#     # """Trigger the Data Capture Rightmove Service to scrape a property URL."""
#     access_token = None
#     try:
#         access_token = get_access_token()
#     except Exception:
#         access_token = None

#     raw_token: Optional[str] = None
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
#         return await trigger_detailed_scrape(
#             client=client,
#             token=raw_token,
#             property_url=property_url,
#             scrape_super_id=super_id,
#         )


@mcp.tool()
async def start_property_analysis_via_n8n_tool(
    property_url: str,
    workflow_callback_url: Optional[str] = None,
) -> dict:
    """Trigger the full property analysis workflow via n8n."""
    async with httpx.AsyncClient() as client:
        return await start_property_analysis_via_n8n(
            client=client,
            property_url=property_url,
            workflow_callback_url=workflow_callback_url,
        )


@mcp.tool()
async def get_property_analysis_result_tool(super_id: str) -> dict:
    """Fetch the stored property analysis result for a given super_id."""
    result = await get_property_analysis_result(super_id)
    if result:
        return result
    return {"super_id": super_id, "status": "pending"}
