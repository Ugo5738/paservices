from typing import Any, Dict, Optional

import httpx
from sqlalchemy.exc import SQLAlchemyError

from ..config import settings
from ..crud import get_analysis_result, upsert_analysis_result
from ..db import AsyncSessionLocal
from ..utils.logging_config import logger


async def start_property_analysis_via_n8n(
    client: httpx.AsyncClient,
    property_url: str,
    workflow_callback_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Kick off the long-running property analysis via n8n."""
    if not property_url:
        raise ValueError("property_url is required")

    callback_url = workflow_callback_url or settings.WORKFLOW_CALLBACK_URL

    payload = {
        "property_url": property_url,
        "workflow_callback_url": callback_url,
    }

    logger.info("Triggering n8n workflow", extra={"payload": payload})

    try:
        response = await client.post(
            settings.N8N_SUPERSAMI_TRIGGER_URL,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        try:
            n8n_response: Any = response.json()
        except ValueError:
            n8n_response = {"raw": response.text}
    except httpx.HTTPError as exc:
        logger.error("Failed to trigger n8n workflow: %s", exc, exc_info=True)
        raise

    # --- Extract super_id from the n8n response ---
    super_id: Optional[str] = None
    remote_status: str = "started"

    if isinstance(n8n_response, dict):
        super_id = n8n_response.get("super_id")
        remote_status = n8n_response.get("status", remote_status)
    elif isinstance(n8n_response, list) and n8n_response:
        # just in case you ever switch to array responses
        item = n8n_response[0]
        if isinstance(item, dict):
            super_id = item.get("super_id")
            remote_status = item.get("status", remote_status)

    if not super_id:
        # At this point something is wrong with the workflow config,
        # better to fail loudly than silently.
        logger.error("n8n trigger did not return a super_id: %r", n8n_response)
        raise RuntimeError("n8n workflow did not return a super_id")

    # Seed persistence with a pending entry so fetches have immediate feedback
    async with AsyncSessionLocal() as session:
        try:
            await upsert_analysis_result(
                session,
                super_id,
                {
                    "status": "pending",  # our internal status
                    "remote_status": remote_status,  # what n8n said ("started")
                    "property_url": property_url,
                    "workflow_callback_url": callback_url,
                    "n8n_triggered": True,
                },
            )
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.error("Failed to seed analysis result row: %s", exc, exc_info=True)
            raise

    return {
        "super_id": super_id,
        "status": "started",
        "workflow_callback_url": callback_url,
        "n8n_response": n8n_response,
    }


async def get_property_analysis_result(super_id: str) -> Dict[str, Any]:
    """Fetch the stored analysis result by super_id."""
    async with AsyncSessionLocal() as session:
        existing = await get_analysis_result(session, super_id)
        if existing:
            return existing.to_dict()

    return {"super_id": super_id, "status": "pending"}
