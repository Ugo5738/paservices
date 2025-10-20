from typing import Any, Dict, Optional

import httpx
from fastmcp.server.context import Context
from fastmcp.server.dependencies import get_access_token

from ..config import settings
from ..utils.logging_config import logger


async def create_super_id(token: Optional[str], prefix: str = "id_") -> str:
    """
    Creates a super_id by calling the Super ID Service API.

    Args:
        token: The raw JWT bearer token, if authentication is needed.
        prefix: The prefix for the new super_id.
    """

    url = f"{settings.SUPER_ID_SERVICE_URL}/super_ids"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = {"prefix": prefix}
    logger.debug("Calling Super ID Service with payload: %s", payload)

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=headers, timeout=10.0)
            resp.raise_for_status()

            data = resp.json()
            super_id = data.get("super_id")

            if not super_id:
                logger.error("Invalid response from Super ID Service: %s", data)
                raise Exception(f"Invalid response from Super ID Service: {data}")

            logger.info("Successfully generated super_id: %s", super_id)
            return super_id

    except httpx.HTTPError as e:
        logger.error("Failed to contact Super ID Service: %s", str(e), exc_info=True)
        raise Exception(f"Failed to contact Super ID Service: {e}")
    except Exception as e:
        logger.error("Unexpected error in create_super_id: %s", str(e), exc_info=True)
        raise
