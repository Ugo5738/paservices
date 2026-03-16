"""
Per-service n8n workflow trigger functions.

Each function triggers a dedicated n8n webhook workflow for one service.
All follow the same pattern:
  1. POST payload to the service's n8n webhook URL
  2. Extract super_id from the n8n response
  3. Seed analysis_result row with status=pending
  4. Return {super_id, status, context, n8n_response}

The existing callback endpoint (POST /api/analysis/callback) handles
status updates from all services — each service posts with a different
``context`` value so they can be tracked independently under one super_id.
"""

from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.exc import SQLAlchemyError

from ..config import settings
from ..crud import upsert_analysis_result
from ..db import AsyncSessionLocal
from ..utils.logging_config import logger

# ---------------------------------------------------------------------------
# Generic helper
# ---------------------------------------------------------------------------


async def _trigger_n8n_service_workflow(
    client: httpx.AsyncClient,
    webhook_url: str,
    payload: Dict[str, Any],
    super_id: Optional[str],
    context: str,
) -> Dict[str, Any]:
    """
    POST *payload* to an n8n service webhook and seed persistence.

    Parameters
    ----------
    client : httpx.AsyncClient
        Re-usable HTTP client.
    webhook_url : str
        Full URL of the n8n webhook for this service.
    payload : dict
        Service-specific body (property_url, image_urls, etc.).
    super_id : str | None
        Caller-supplied super_id.  If *None*, n8n is expected to generate one.
    context : str
        Discriminator stored alongside status updates (e.g. ``"fetch_combined"``).

    Returns
    -------
    dict
        ``{super_id, status, context, n8n_response}``
    """
    if not webhook_url:
        raise ValueError(
            f"n8n webhook URL for context '{context}' is not configured. "
            f"Set the corresponding PA_MCP_N8N_* environment variable."
        )

    # Always include the callback URL so n8n knows where to POST results
    payload.setdefault("callback_url", settings.WORKFLOW_CALLBACK_URL)
    if super_id:
        payload["super_id"] = super_id

    logger.info(
        "Triggering n8n service workflow",
        extra={"context": context, "webhook_url": webhook_url, "payload": payload},
    )

    try:
        response = await client.post(webhook_url, json=payload, timeout=30)
        response.raise_for_status()
        try:
            n8n_response: Any = response.json()
        except ValueError:
            n8n_response = {"raw": response.text}
    except httpx.HTTPError as exc:
        logger.error(
            "Failed to trigger n8n %s workflow: %s", context, exc, exc_info=True
        )
        raise

    # Extract super_id from the n8n response
    response_super_id: Optional[str] = None
    if isinstance(n8n_response, dict):
        response_super_id = n8n_response.get("super_id")
    elif isinstance(n8n_response, list) and n8n_response:
        item = n8n_response[0]
        if isinstance(item, dict):
            response_super_id = item.get("super_id")

    final_super_id = response_super_id or super_id
    if not final_super_id:
        logger.error(
            "n8n %s workflow did not return a super_id: %r", context, n8n_response
        )
        raise RuntimeError(f"n8n {context} workflow did not return a super_id")

    # Seed persistence with a pending entry
    async with AsyncSessionLocal() as session:
        try:
            await upsert_analysis_result(
                session,
                final_super_id,
                {
                    "status": "pending",
                    "remote_status": "accepted",
                    "n8n_triggered": True,
                },
            )
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.error(
                "Failed to seed analysis result for %s: %s",
                context,
                exc,
                exc_info=True,
            )
            raise

    return {
        "super_id": final_super_id,
        "status": "accepted",
        "context": context,
        "n8n_response": n8n_response,
    }


# ---------------------------------------------------------------------------
# Per-service trigger functions
# ---------------------------------------------------------------------------


async def trigger_rightmove_via_n8n(
    client: httpx.AsyncClient,
    property_url: str,
    super_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Trigger the Rightmove data capture n8n workflow."""
    payload: Dict[str, Any] = {"property_url": property_url}
    return await _trigger_n8n_service_workflow(
        client=client,
        webhook_url=settings.N8N_DATA_CAPTURE_RIGHTMOVE_URL,
        payload=payload,
        super_id=super_id,
        context="fetch_combined",
    )


async def trigger_data_capture_via_n8n(
    client: httpx.AsyncClient,
    url: str,
    super_id: Optional[str] = None,
    skip_baseline: bool = False,
) -> Dict[str, Any]:
    """Trigger the Motie data capture n8n workflow."""
    payload: Dict[str, Any] = {"url": url, "skip_baseline": skip_baseline}
    return await _trigger_n8n_service_workflow(
        client=client,
        webhook_url=settings.N8N_DATA_CAPTURE_MOTIE_URL,
        payload=payload,
        super_id=super_id,
        context="data_capture",
    )


async def trigger_floorplan_via_n8n(
    client: httpx.AsyncClient,
    super_id: str,
    property_id: str,
    floorplans: Dict[str, Any],
) -> Dict[str, Any]:
    """Trigger the floorplan analysis n8n workflow."""
    payload: Dict[str, Any] = {
        "property_id": property_id,
        "floorplans": floorplans,
    }
    return await _trigger_n8n_service_workflow(
        client=client,
        webhook_url=settings.N8N_FLOORPLAN_URL,
        payload=payload,
        super_id=super_id,
        context="floorplan_analysis",
    )


async def trigger_image_condition_via_n8n(
    client: httpx.AsyncClient,
    super_id: str,
    image_urls: List[str],
    property_id: Optional[str] = None,
    notes: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Trigger the image condition analysis n8n workflow."""
    payload: Dict[str, Any] = {"image_urls": image_urls}
    if property_id:
        payload["property_id"] = property_id
    if notes:
        payload["notes"] = notes
    return await _trigger_n8n_service_workflow(
        client=client,
        webhook_url=settings.N8N_IMAGE_CONDITION_URL,
        payload=payload,
        super_id=super_id,
        context="image_condition_analysis",
    )


async def trigger_orchestrator_via_n8n(
    client: httpx.AsyncClient,
    property_url: str,
    services: List[str],
    service_params: Optional[Dict[str, Any]] = None,
    super_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Trigger the orchestrator n8n workflow that runs a sequence of services."""
    payload: Dict[str, Any] = {
        "property_url": property_url,
        "services": services,
    }
    if service_params:
        payload["service_params"] = service_params
    return await _trigger_n8n_service_workflow(
        client=client,
        webhook_url=settings.N8N_ORCHESTRATOR_URL,
        payload=payload,
        super_id=super_id,
        context="orchestrator",
    )
