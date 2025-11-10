# data_capture_rightmove_service/routers/workflow_test_router.py

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urljoin
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from data_capture_rightmove_service.config import settings

router = APIRouter(prefix="/workflow-test", tags=["Workflow Test"])

# ------------------------------------------------------------------------------
# In-memory state (ephemeral; fine for test/dev)
# ------------------------------------------------------------------------------
_RESULTS: Dict[str, Dict[str, Any]] = {}
logger = logging.getLogger("uvicorn.error")  # prints to container logs


class TriggerRequest(BaseModel):
    property_url: HttpUrl
    frontend_callback_url: Optional[HttpUrl] = None


def _build_callback_url(workflow_id: str, override: Optional[str]) -> str:
    if override:
        return override
    base = settings.N8N_TEST_CALLBACK_BASE_URL
    if not base:
        raise HTTPException(
            status_code=500,
            detail=(
                "DATA_CAPTURE_RIGHTMOVE_SERVICE_N8N_TEST_CALLBACK_BASE_URL must be set "
                "so the workflow can call back into this service."
            ),
        )
    root = settings.ROOT_PATH or "/"
    # ensure single slash joining
    return urljoin(
        base.rstrip("/") + "/",
        f"{root.strip('/')}/workflow-test/callback/{workflow_id}",
    )


@router.post("/trigger")
async def trigger_workflow(payload: TriggerRequest):
    """Kick off the n8n workflow and return an id that can be polled later."""
    if not settings.N8N_TEST_WEBHOOK_URL:
        raise HTTPException(
            status_code=500, detail="N8N test webhook URL is not configured."
        )

    workflow_id = str(uuid4())
    callback_url = _build_callback_url(
        workflow_id,
        str(payload.frontend_callback_url) if payload.frontend_callback_url else None,
    )

    body = {
        "property_url": str(payload.property_url),
        "frontend_callback_url": callback_url,
    }

    # Log the trigger
    logger.info(
        "[workflow-test] trigger -> id=%s body=%s", workflow_id, json.dumps(body)
    )

    # Record pending state in-memory
    _RESULTS[workflow_id] = {
        "status": "pending",
        "data": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "callback_url": callback_url,
        "request": body,
    }

    # Fire the n8n webhook
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(str(settings.N8N_TEST_WEBHOOK_URL), json=body)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.exception(
            "[workflow-test] n8n webhook failed for id=%s: %s", workflow_id, exc
        )
        # Mark as failed for visibility, then raise
        _RESULTS[workflow_id]["status"] = "failed"
        _RESULTS[workflow_id]["error"] = str(exc)
        raise HTTPException(
            status_code=502, detail=f"n8n webhook failed: {exc}"
        ) from exc

    return {"workflow_id": workflow_id, "callback_url": callback_url}


@router.post("/callback/{workflow_id}")
async def receive_callback(workflow_id: UUID, payload: Dict[str, Any]):
    """Endpoint n8n should call once the aggregation workflow finishes."""
    key = str(workflow_id)

    # If someone posts back an unknown id, initialize it so we don't lose data.
    if key not in _RESULTS:
        _RESULTS[key] = {
            "status": "pending",
            "data": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "callback_url": None,
            "request": None,
        }

    _RESULTS[key]["status"] = "completed"
    _RESULTS[key]["data"] = payload
    _RESULTS[key]["completed_at"] = datetime.now(timezone.utc).isoformat()

    # Print the final payload nicely to the terminal
    logger.info(
        "[workflow-test] callback -> id=%s payload=\n%s",
        key,
        json.dumps(payload, indent=2),
    )

    return {"acknowledged": True}


@router.get("/results/{workflow_id}")
async def fetch_results(workflow_id: UUID):
    """Return the stored results for the requested workflow."""
    key = str(workflow_id)
    if key not in _RESULTS:
        raise HTTPException(status_code=404, detail="Workflow id not found")
    return _RESULTS[key]
