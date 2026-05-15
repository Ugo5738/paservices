from typing import Any, Dict, Optional

import httpx
from fastmcp.server.context import Context
from fastmcp.server.dependencies import get_access_token

from ..config import settings
from ..utils.logging_config import logger
from .auth_helper import get_m2m_token


async def record_activity(
    super_id: str,
    used_by: str,
    source: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Record one activity entry on the SuperID Metadata store. Non-blocking:
    any failure (auth, network, missing permission, 5xx, …) is logged and
    the method returns None. Activity records are observability metadata —
    losing one record must not break pa_mcp's operational path.

    See docs/superid_principles.md section 5 and
    docs/superid_data_capture_design.md section 3.3.
    """
    payload: Dict[str, Any] = {
        "super_id": super_id,
        "used_by": used_by,
        "source": source,
    }
    if metadata is not None:
        payload["metadata"] = metadata
    try:
        token = await get_m2m_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.SUPER_ID_SERVICE_URL}/activity_records",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.warning(
            "pa_mcp: failed to record activity for super_id=%s used_by=%s source=%s: %s",
            super_id,
            used_by,
            source,
            exc,
        )
        return None


async def record_link(
    super_id_a: str,
    super_id_b: str,
    created_by: str,
    source: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Record one link entry on the SuperID Metadata store between two
    SuperIDs. Bidirectional — order is not semantically meaningful.
    Non-blocking (see `record_activity`).
    """
    payload: Dict[str, Any] = {
        "super_id_a": super_id_a,
        "super_id_b": super_id_b,
        "created_by": created_by,
        "source": source,
    }
    if metadata is not None:
        payload["metadata"] = metadata
    try:
        token = await get_m2m_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.SUPER_ID_SERVICE_URL}/link_records",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.warning(
            "pa_mcp: failed to record link super_id_a=%s super_id_b=%s created_by=%s source=%s: %s",
            super_id_a,
            super_id_b,
            created_by,
            source,
            exc,
        )
        return None


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
