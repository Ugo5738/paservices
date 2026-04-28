"""
Fetcher Runner — invokes one fetcher against one URL.

Reads the fetcher row's source_type, route, http_method, and param_schema, then
builds the right outbound HTTP request. Supports two source types:

- 'motie': GET/POST against the deployed Motie FastAPI ({api_url}{route_path}),
  authenticated with the MOTIE_API_TOKEN as Bearer.
- 'proxy': GET/POST against an external service ({api_url_override}{route_path}),
  authenticated with an M2M JWT from auth_service for paservices internal services.

URL injection follows param_schema, e.g.
  {"url_param": "listing_url", "url_location": "query"} → ?listing_url=<URL>
  {"url_param": "url", "url_location": "body"} → JSON body {"url": "<URL>"}
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.clients.auth_service_client import auth_service_client
from data_capture_service.config import settings
from data_capture_service.crud import fetcher_crud
from data_capture_service.models.fetcher import Fetcher

logger = logging.getLogger(__name__)


@dataclass
class FetcherRunResult:
    """Outcome of running a fetcher once against a URL."""

    fetcher_id: str
    url: str
    status: str  # "success" | "http_error" | "no_url" | "exception"
    http_status_code: Optional[int] = None
    payload: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    duration_ms: int = 0
    is_metered: bool = False


def _inject_url(
    param_schema: Dict[str, Any],
    listing_url: str,
    extra_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build params/json from the schema, with the URL injected at the right spot."""
    url_param = (param_schema or {}).get("url_param", "url")
    url_location = (param_schema or {}).get("url_location", "query").lower()

    query_params: Dict[str, Any] = dict(
        (param_schema or {}).get("query_extras", {}) or {}
    )
    body_params: Dict[str, Any] = dict(
        (param_schema or {}).get("body_extras", {}) or {}
    )

    if url_location == "query":
        query_params[url_param] = listing_url
    elif url_location == "body":
        body_params[url_param] = listing_url
    else:
        # Default to query if param_schema is malformed
        query_params[url_param] = listing_url

    if extra_params:
        # Caller-provided overrides go where they say to go via "_location" suffixes,
        # otherwise default to body.
        for k, v in extra_params.items():
            body_params[k] = v

    return {"query": query_params, "body": body_params}


async def _build_motie_headers() -> Dict[str, str]:
    headers = {"Accept": "application/json"}
    if settings.MOTIE_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.MOTIE_API_TOKEN}"
    return headers


async def _build_proxy_headers() -> Dict[str, str]:
    """Get an M2M JWT for calling a paservices internal service."""
    headers = await auth_service_client.get_auth_header()
    headers["Accept"] = "application/json"
    return headers


async def run_fetcher(
    db: AsyncSession,
    fetcher: Fetcher,
    listing_url: str,
    extra_params: Optional[Dict[str, Any]] = None,
    timeout: float = 60.0,
) -> FetcherRunResult:
    """Invoke a single fetcher against a URL. Returns the outcome verbatim."""
    start = time.time()
    api_url = await fetcher_crud.resolve_api_url(db, fetcher)
    if not api_url:
        return FetcherRunResult(
            fetcher_id=str(fetcher.id),
            url=listing_url,
            status="no_url",
            error_message=(
                f"Fetcher {fetcher.id} has no resolvable api_url "
                f"(source_type={fetcher.source_type})"
            ),
            duration_ms=int((time.time() - start) * 1000),
            is_metered=fetcher.is_metered,
        )

    target = f"{api_url.rstrip('/')}{fetcher.route_path}"
    method = (fetcher.http_method or "GET").upper()
    params = _inject_url(fetcher.param_schema or {}, listing_url, extra_params)

    if fetcher.source_type == "motie":
        headers = await _build_motie_headers()
    else:
        headers = await _build_proxy_headers()
    headers.setdefault("Content-Type", "application/json")

    logger.info(
        f"Running fetcher {fetcher.id} ({fetcher.source_type}): "
        f"{method} {target} (url_param={params['query'] or params['body']})"
    )

    try:
        async with httpx.AsyncClient() as client:
            if method == "GET":
                resp = await client.request(
                    method=method,
                    url=target,
                    params=params["query"] or None,
                    headers=headers,
                    timeout=timeout,
                )
            else:
                resp = await client.request(
                    method=method,
                    url=target,
                    params=params["query"] or None,
                    json=params["body"] or None,
                    headers=headers,
                    timeout=timeout,
                )

        duration_ms = int((time.time() - start) * 1000)

        if resp.status_code >= 400:
            return FetcherRunResult(
                fetcher_id=str(fetcher.id),
                url=listing_url,
                status="http_error",
                http_status_code=resp.status_code,
                error_message=resp.text[:512],
                duration_ms=duration_ms,
                is_metered=fetcher.is_metered,
            )

        payload: Optional[Dict[str, Any]]
        try:
            payload = resp.json()
            if not isinstance(payload, dict):
                payload = {"data": payload}
        except ValueError:
            payload = {"raw_text": resp.text}

        return FetcherRunResult(
            fetcher_id=str(fetcher.id),
            url=listing_url,
            status="success",
            http_status_code=resp.status_code,
            payload=payload,
            duration_ms=duration_ms,
            is_metered=fetcher.is_metered,
        )

    except Exception as e:
        logger.error(f"Fetcher {fetcher.id} failed: {e}", exc_info=True)
        return FetcherRunResult(
            fetcher_id=str(fetcher.id),
            url=listing_url,
            status="exception",
            error_message=str(e),
            duration_ms=int((time.time() - start) * 1000),
            is_metered=fetcher.is_metered,
        )
