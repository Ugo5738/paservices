import argparse

import httpx
from fastmcp.server.dependencies import get_access_token

from ..config import settings
from ..utils.logging_config import logger

FLOORPLAN_SERVICE_URL = "http://floorplan_service:8000/api/v1"


def print_color(text, color):
    colors = {
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "reset": "\033[0m",
    }
    print(f"{colors.get(color, '')}{text}{colors['reset']}")


async def trigger_floorplan_analysis(
    client: httpx.AsyncClient,
    token: str | None,
    floorplan_key: str,
    floorplan_url: str,
    super_id: str,
    property_id: str,
) -> bool:
    """Trigger floorplan analysis for a single floorplan image.

    Args:
        client: an httpx.AsyncClient to reuse connections
        token: optional raw bearer token string
        floorplan_key: a client-chosen key for this floorplan (e.g., 'fp1')
        floorplan_url: URL of the floorplan image
        super_id: super_id UUID string used for tracing
        property_id: property identifier string

    Returns:
        True if the request was accepted (202), False otherwise
    """
    print_color("   - Triggering floorplan analysis...", "blue")
    url = f"{FLOORPLAN_SERVICE_URL}/analyze"

    headers = {"X-Super-ID": super_id}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = {
        "super_id": super_id,
        "property_id": property_id,
        "floorplans": {floorplan_key: {"url": floorplan_url}},
    }

    try:
        response = await client.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        print_color("   - ✅ Floorplan analysis initiated.", "green")
        return True
    except httpx.HTTPStatusError as e:
        print_color(
            f"   - ❌ Floorplan analysis failed. Status: {e.response.status_code}, Details: {e.response.text}",
            "red",
        )
        return False
    except httpx.HTTPError as e:
        logger.error("Failed to contact Floorplan Service: %s", str(e), exc_info=True)
        raise Exception(f"Failed to contact Floorplan Service: {e}")
