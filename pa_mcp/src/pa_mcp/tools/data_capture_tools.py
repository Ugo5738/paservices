import argparse
from typing import Any, Dict, List, Optional

import httpx
from fastmcp.server.dependencies import get_access_token

from ..config import settings
from ..utils.logging_config import logger

DATA_CAPTURE_RIGHTMOVE_SERVICE_URL = "http://data_capture_rightmove_service:8000/api/v1"
# DATA_CAPTURE_RIGHTMOVE_SERVICE_URL = (
#     "https://data-capture-rightmove.supersami.com/api/v1"
# )


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


async def list_properties(
    token: str,
    on_date: Optional[str] = None,
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
    min_bedrooms: Optional[int] = None,
    max_bedrooms: Optional[int] = None,
    min_bathrooms: Optional[int] = None,
    max_bathrooms: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Asynchronously lists properties from the Data Capture Service.

    Args:
        token: The bearer token for authorization.
        on_date: The specific date to filter properties on (e.g., "YYYY-MM-DD").
        from_time: The start of the time window (e.g., "HH:MM:SS").
        to_time: The end of the time window (e.g., "HH:MM:SS").
        min_bedrooms: The minimum number of bedrooms.
        max_bedrooms: The maximum number of bedrooms.
        min_bathrooms: The minimum number of bathrooms.
        max_bathrooms: The maximum number of bathrooms.

    Returns:
        A list of properties matching the criteria.

    Raises:
        Exception: If the request to the service fails.
    """

    url = f"{DATA_CAPTURE_RIGHTMOVE_SERVICE_URL}/properties/listings"

    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "on_date": on_date,
        "from_time": from_time,
        "to_time": to_time,
        "min_bedrooms": min_bedrooms,
        "max_bedrooms": max_bedrooms,
        "min_bathrooms": min_bathrooms,
        "max_bathrooms": max_bathrooms,
    }
    params = {k: v for k, v in params.items() if v is not None}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, params=params, timeout=60)
            resp.raise_for_status()

            properties = resp.json().get("properties", [])
            print_color(
                f"✅ SUCCESS: Found {len(properties)} properties matching criteria.",
                "green",
            )
            return properties
    except httpx.HTTPError as e:
        logger.error(
            "Failed to contact Data Capture Service: %s", str(e), exc_info=True
        )
        raise Exception(f"Failed to contact Data Capture Service: {e}")
    except Exception as e:
        logger.error(
            "Failed to contact Data Capture Service: %s", str(e), exc_info=True
        )
        raise Exception(f"Failed to contact Data Capture Service: {e}")


async def trigger_detailed_scrape(
    client: httpx.AsyncClient,
    token: str | None,
    property_url: str,
    scrape_super_id: str,
) -> str:
    """Triggers the detailed property scrape task"""
    print_color("   - Triggering detailed scrape...", "blue")
    url = f"{DATA_CAPTURE_RIGHTMOVE_SERVICE_URL}/properties/fetch/combined"
    headers = {"X-Super-ID": scrape_super_id}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = {"property_url": property_url, "super_id": scrape_super_id}
    try:
        response = await client.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        success_message = f"✅ Scrape successfully initiated for {property_url} with super_id {scrape_super_id}."
        print_color(f"   - {success_message}", "green")
        return success_message
    except httpx.HTTPStatusError as e:
        error_message = f"❌ Scrape failed. Status: {e.response.status_code}, Details: {e.response.text}"
        print_color(f"   - {error_message}", "red")
        return error_message
