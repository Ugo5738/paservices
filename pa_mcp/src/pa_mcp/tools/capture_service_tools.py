"""
Data Capture Service HTTP helper functions for MCP tool registration.

Provides async functions that call the Data Capture Service endpoints.
Each function maps to one MCP tool.
"""

import json
from typing import Any, Dict, Optional

import httpx

from ..utils.logging_config import logger

DATA_CAPTURE_SERVICE_URL = "http://data_capture_service:8000/api/v1"


async def start_property_capture(
    url: str,
    super_id: Optional[str] = None,
    adapter_name: Optional[str] = None,
    skip_baseline: bool = False,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """Start an orchestrated property data capture pipeline."""
    endpoint = f"{DATA_CAPTURE_SERVICE_URL}/data_capture/start"
    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload: Dict[str, Any] = {"url": url, "skip_baseline": skip_baseline}
    if super_id:
        payload["super_id"] = super_id
    if adapter_name:
        payload["adapter_name"] = adapter_name

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                endpoint, headers=headers, json=payload, timeout=30
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logger.error(f"Failed to start property capture: {e}", exc_info=True)
        raise Exception(f"Failed to start property capture: {e}")


async def capture_with_motie(
    url: str,
    super_id: Optional[str] = None,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """Extract property data using the Motie AI adapter (includes baseline validation)."""
    endpoint = f"{DATA_CAPTURE_SERVICE_URL}/data_capture/adapters/motie"
    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload: Dict[str, Any] = {"url": url}
    if super_id:
        payload["super_id"] = super_id

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                endpoint, headers=headers, json=payload, timeout=30
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logger.error(f"Failed to invoke Motie extraction: {e}", exc_info=True)
        raise Exception(f"Failed to invoke Motie extraction: {e}")


async def check_property_fields(
    url: str,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """Quick baseline field-presence check for a property URL."""
    endpoint = f"{DATA_CAPTURE_SERVICE_URL}/data_capture/adapters/firecrawl"
    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload: Dict[str, Any] = {"url": url}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                endpoint, headers=headers, json=payload, timeout=30
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logger.error(f"Failed to invoke baseline field check: {e}", exc_info=True)
        raise Exception(f"Failed to invoke baseline field check: {e}")


async def get_capture_run_status(
    run_id: str,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """Poll the status of a property data capture run."""
    endpoint = f"{DATA_CAPTURE_SERVICE_URL}/data_capture/runs/{run_id}"
    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(endpoint, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logger.error(f"Failed to get capture run status: {e}", exc_info=True)
        raise Exception(f"Failed to get capture run status: {e}")


async def get_capture_run_result(
    run_id: str,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """Get the canonical result of a completed property data capture run."""
    endpoint = f"{DATA_CAPTURE_SERVICE_URL}/data_capture/runs/{run_id}/result"
    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(endpoint, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logger.error(f"Failed to get capture run result: {e}", exc_info=True)
        raise Exception(f"Failed to get capture run result: {e}")


async def retry_capture_run(
    run_id: str,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """Retry a failed property data capture run."""
    endpoint = f"{DATA_CAPTURE_SERVICE_URL}/data_capture/runs/{run_id}/retry"
    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(endpoint, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logger.error(f"Failed to retry capture run: {e}", exc_info=True)
        raise Exception(f"Failed to retry capture run: {e}")
