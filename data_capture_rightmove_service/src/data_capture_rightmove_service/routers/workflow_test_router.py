"""Endpoints for triggering the n8n workflow test path."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from data_capture_rightmove_service.config import settings

router = APIRouter(prefix="/workflow-test", tags=["Workflow Test"])

RESULT_DIR = Path(settings.WORKFLOW_TEST_RESULTS_DIR)
RESULT_DIR.mkdir(parents=True, exist_ok=True)


class TriggerRequest(BaseModel):
    property_url: HttpUrl
    frontend_callback_url: Optional[HttpUrl] = None


def _result_path(workflow_id: str) -> Path:
    return RESULT_DIR / f"{workflow_id}.json"


def _write_result(workflow_id: str, payload: Dict[str, Any]) -> None:
    path = _result_path(workflow_id)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_result(workflow_id: str) -> Dict[str, Any]:
    path = _result_path(workflow_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Workflow id not found")
    return json.loads(path.read_text(encoding="utf-8"))


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
    return f"{base.rstrip('/')}{settings.ROOT_PATH}/workflow-test/callback/{workflow_id}"


@router.post("/trigger")
async def trigger_workflow(payload: TriggerRequest):
    """Kick off the n8n workflow and return an id that can be polled later."""

    if not settings.N8N_TEST_WEBHOOK_URL:
        raise HTTPException(
            status_code=500,
            detail="N8N test webhook URL is not configured.",
        )

    workflow_id = str(uuid4())
    callback_url = _build_callback_url(
        workflow_id, str(payload.frontend_callback_url) if payload.frontend_callback_url else None
    )

    body = {
        "property_url": str(payload.property_url),
        "frontend_callback_url": callback_url,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(settings.N8N_TEST_WEBHOOK_URL, json=body)
            response.raise_for_status()
    except httpx.HTTPError as exc:  # pragma: no cover - network failures
        raise HTTPException(status_code=502, detail=f"n8n webhook failed: {exc}") from exc

    _write_result(workflow_id, {"status": "pending", "data": None})
    return {"workflow_id": workflow_id, "callback_url": callback_url}


@router.post("/callback/{workflow_id}")
async def receive_callback(workflow_id: UUID, payload: Dict[str, Any]):
    """Endpoint n8n should call once the aggregation workflow finishes."""

    key = str(workflow_id)
    _write_result(key, {"status": "completed", "data": payload})
    return {"acknowledged": True}


@router.get("/results/{workflow_id}")
async def fetch_results(workflow_id: UUID):
    """Return the stored results for the requested workflow."""

    return _read_result(str(workflow_id))
